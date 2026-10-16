from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import math
from typing import Optional, List
from app.database import get_db
from app.models import User, DonorProfile, Donation
from app.schemas import (
    DonorProfileOut, DonorProfileUpdate, DonorAvailabilityUpdate, DonorPublicOut
)
from app.security.auth import get_current_active_user, require_role
from app.services.compatibility import get_compatible_donor_groups, is_compatible
from app.services.distance import haversine_distance
from app.config import settings
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/donors", tags=["Donors"])


@router.get("", response_model=List[DonorPublicOut])
def list_donors(
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    availability_status: Optional[str] = "available",
    verified_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    List potential donors with privacy-safe public attributes.
    Exact home addresses and private phones are never revealed publicly.
    """
    query = (
        db.query(DonorProfile, User)
        .join(User, DonorProfile.user_id == User.id)
        .filter(User.account_status == "active")
        .filter(DonorProfile.consent_to_share == True)
    )

    if blood_group:
        query = query.filter(DonorProfile.blood_group == blood_group.upper())

    if city:
        query = query.filter(DonorProfile.city.ilike(f"%{city}%"))

    if state:
        query = query.filter(DonorProfile.state.ilike(f"%{state}%"))

    if availability_status:
        query = query.filter(DonorProfile.availability_status == availability_status)

    if verified_only:
        query = query.filter(DonorProfile.is_verified == True)

    results = query.all()
    user_ids = [u.id for dp, u in results]
    donation_counts = {}
    if user_ids:
        counts = (
            db.query(Donation.donor_id, func.count(Donation.id))
            .filter(Donation.donor_id.in_(user_ids), Donation.donation_status == "verified")
            .group_by(Donation.donor_id)
            .all()
        )
        donation_counts = dict(counts)

    out = []
    for dp, u in results:
        out.append(DonorPublicOut(
            donor_id=dp.id,
            user_id=u.id,
            full_name=u.full_name,
            blood_group=dp.blood_group,
            city=dp.city,
            state=dp.state,
            availability_status=dp.availability_status,
            is_verified=dp.is_verified,
            last_donation_date=dp.last_donation_date,
            total_donations=donation_counts.get(u.id, 0),
            latitude=dp.latitude,
            longitude=dp.longitude
        ))
    return out


@router.get("/nearby", response_model=List[DonorPublicOut])
def get_nearby_donors(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    blood_group: Optional[str] = None,
    compatible_for: Optional[str] = None,
    radius_km: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Find nearby active, available donors within specified radius (default 25km).
    Supports filtering by compatible blood groups for a given recipient.
    Uses geographic bounding box in SQL before computing precise haversine distance.
    """
    max_radius = radius_km or settings.DONOR_SEARCH_RADIUS_KM

    # Geographic bounding box pre-filter in SQL using indexed lat/lon columns
    lat_delta = max_radius / 111.0
    lon_delta = max_radius / (111.0 * max(0.1, math.cos(math.radians(lat))))

    query = (
        db.query(DonorProfile, User)
        .join(User, DonorProfile.user_id == User.id)
        .filter(User.account_status == "active")
        .filter(DonorProfile.availability_status == "available")
        .filter(DonorProfile.consent_to_share == True)
        .filter(DonorProfile.latitude.isnot(None))
        .filter(DonorProfile.longitude.isnot(None))
        .filter(DonorProfile.latitude.between(lat - lat_delta, lat + lat_delta))
        .filter(DonorProfile.longitude.between(lon - lon_delta, lon + lon_delta))
    )

    if compatible_for:
        try:
            compatible_groups = get_compatible_donor_groups(compatible_for)
            query = query.filter(DonorProfile.blood_group.in_(compatible_groups))
        except ValueError:
            pass
    elif blood_group:
        query = query.filter(DonorProfile.blood_group == blood_group.upper())

    records = query.all()
    candidate_matches = []

    for dp, u in records:
        dist = haversine_distance(lat, lon, dp.latitude, dp.longitude)
        if dist is not None and dist <= max_radius:
            candidate_matches.append((dp, u, dist))

    # Batch fetch verified donation counts for matched candidate donors
    matched_user_ids = [u.id for dp, u, dist in candidate_matches]
    donation_counts = {}
    if matched_user_ids:
        counts = (
            db.query(Donation.donor_id, func.count(Donation.id))
            .filter(Donation.donor_id.in_(matched_user_ids), Donation.donation_status == "verified")
            .group_by(Donation.donor_id)
            .all()
        )
        donation_counts = dict(counts)

    nearby_donors = [
        DonorPublicOut(
            donor_id=dp.id,
            user_id=u.id,
            full_name=u.full_name,
            blood_group=dp.blood_group,
            city=dp.city,
            state=dp.state,
            availability_status=dp.availability_status,
            is_verified=dp.is_verified,
            last_donation_date=dp.last_donation_date,
            distance_km=dist,
            latitude=dp.latitude,
            longitude=dp.longitude,
            total_donations=donation_counts.get(u.id, 0)
        )
        for dp, u, dist in candidate_matches
    ]

    # Sort by distance
    nearby_donors.sort(key=lambda x: x.distance_km or 999999.0)
    return nearby_donors


@router.get("/me", response_model=DonorProfileOut)
def get_donor_me(
    current_user: User = Depends(require_role(["donor", "admin"])),
    db: Session = Depends(get_db)
):
    profile = db.query(DonorProfile).filter(DonorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    return profile


@router.put("/me", response_model=DonorProfileOut)
def update_donor_me(
    profile_in: DonorProfileUpdate,
    current_user: User = Depends(require_role(["donor", "admin"])),
    db: Session = Depends(get_db)
):
    profile = db.query(DonorProfile).filter(DonorProfile.user_id == current_user.id).first()
    if not profile:
        # Create profile if not already present
        profile = DonorProfile(
            user_id=current_user.id,
            blood_group="O+",
            availability_status="available"
        )
        db.add(profile)
        db.flush()

    data = profile_in.dict(exclude_unset=True)
    for field, val in data.items():
        setattr(profile, field, val)

    db.commit()
    db.refresh(profile)

    create_audit_log(
        db,
        action="update_donor_profile",
        entity_type="donor_profile",
        actor_user_id=current_user.id,
        entity_id=profile.id
    )

    return profile


@router.patch("/me/availability", response_model=DonorProfileOut)
def update_availability(
    status_in: DonorAvailabilityUpdate,
    current_user: User = Depends(require_role(["donor", "admin"])),
    db: Session = Depends(get_db)
):
    profile = db.query(DonorProfile).filter(DonorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Donor profile not found.")

    profile.availability_status = status_in.availability_status
    db.commit()
    db.refresh(profile)

    create_audit_log(
        db,
        action="toggle_availability",
        entity_type="donor_profile",
        actor_user_id=current_user.id,
        entity_id=profile.id,
        metadata={"new_status": status_in.availability_status}
    )

    return profile
