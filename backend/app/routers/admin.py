from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.models import (
    User, DonorProfile, PatientProfile, BloodRequest, Donation,
    RewardTransaction, AuditLog
)
from app.schemas import (
    AdminDashboardStats, AdminUserStatusUpdate, AdminAnalyticsOut, UserOut
)
from app.security.auth import require_role
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/admin", tags=["Administrator"])


@router.get("/dashboard", response_model=AdminDashboardStats)
def get_admin_dashboard(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    # 1. User stats grouped by role in a single SQL query
    user_counts = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())
    total_donors = user_counts.get("donor", 0)
    total_patients = user_counts.get("patient", 0)
    total_users = sum(user_counts.values())

    # 2. Donor Profile stats in a single conditional aggregation query
    donor_stats = (
        db.query(
            func.sum(case((DonorProfile.is_verified == True, 1), else_=0)),
            func.sum(case((DonorProfile.availability_status == "available", 1), else_=0))
        )
        .join(User, DonorProfile.user_id == User.id)
        .filter(User.account_status == "active")
        .first()
    )
    verified_donors = int(donor_stats[0] or 0) if donor_stats else 0
    available_donors = int(donor_stats[1] or 0) if donor_stats else 0

    # 3. Blood Request stats in a single conditional aggregation query
    req_stats = (
        db.query(
            func.count(BloodRequest.id),
            func.sum(case((
                (BloodRequest.urgency == "critical") &
                (BloodRequest.status.in_(["submitted", "searching", "responses_received", "assistance_arranged"])), 1
            ), else_=0)),
            func.sum(case((BloodRequest.status == "fulfilled", 1), else_=0)),
            func.sum(case((BloodRequest.status.in_(["cancelled", "expired"]), 1), else_=0))
        )
        .first()
    )
    total_requests = int(req_stats[0] or 0) if req_stats else 0
    critical_active = int(req_stats[1] or 0) if req_stats else 0
    fulfilled_requests = int(req_stats[2] or 0) if req_stats else 0
    cancelled_requests = int(req_stats[3] or 0) if req_stats else 0

    # 4. Verified Donations and Total Points
    verified_donations = db.query(Donation).filter(Donation.donation_status == "verified").count()
    total_points = db.query(func.coalesce(func.sum(RewardTransaction.points), 0)).scalar() or 0

    return AdminDashboardStats(
        total_users=total_users,
        total_donors=total_donors,
        total_patients=total_patients,
        verified_donors=verified_donors,
        available_donors=available_donors,
        total_requests=total_requests,
        critical_active_requests=critical_active,
        fulfilled_requests=fulfilled_requests,
        cancelled_requests=cancelled_requests,
        verified_donations=verified_donations,
        total_points_awarded=int(total_points)
    )


@router.get("/users")
def get_admin_users(
    role: Optional[str] = None,
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    query = db.query(User).options(
        joinedload(User.donor_profile),
        joinedload(User.patient_profile)
    )

    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.account_status == status)
    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.phone.ilike(f"%{search}%"))
        )

    users = query.order_by(User.created_at.desc()).all()
    results = []

    for u in users:
        bg = "N/A"
        is_verified = False
        user_city = "N/A"
        avail = "N/A"

        if u.role == "donor" and u.donor_profile:
            bg = u.donor_profile.blood_group
            is_verified = u.donor_profile.is_verified
            user_city = u.donor_profile.city or "N/A"
            avail = u.donor_profile.availability_status
        elif u.role == "patient" and u.patient_profile:
            user_city = u.patient_profile.city or "N/A"

        # Apply blood group & city filters if specified
        if blood_group and bg.upper() != blood_group.upper():
            continue
        if city and user_city.lower() != city.lower():
            continue

        results.append({
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone": u.phone,
            "role": u.role,
            "account_status": u.account_status,
            "blood_group": bg,
            "is_verified": is_verified,
            "city": user_city,
            "availability_status": avail,
            "created_at": u.created_at
        })

    return results


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    status_in: AdminUserStatusUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Administrators cannot modify their own active account status.")

    if status_in.account_status:
        target_user.account_status = status_in.account_status

    if status_in.is_verified is not None and target_user.donor_profile:
        target_user.donor_profile.is_verified = status_in.is_verified

    db.commit()
    db.refresh(target_user)

    create_audit_log(
        db,
        action="admin_update_user_status",
        entity_type="user",
        actor_user_id=current_user.id,
        entity_id=target_user.id,
        metadata={"account_status": status_in.account_status, "is_verified": status_in.is_verified}
    )

    return {"message": "User status updated successfully.", "user_id": target_user.id, "status": target_user.account_status}


@router.get("/requests")
def get_admin_requests(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    query = db.query(BloodRequest)
    if status:
        query = query.filter(BloodRequest.status == status)
    if urgency:
        query = query.filter(BloodRequest.urgency == urgency)
    if blood_group:
        query = query.filter(BloodRequest.blood_group == blood_group.upper())
    if city:
        query = query.filter(BloodRequest.city.ilike(f"%{city}%"))

    requests = query.order_by(BloodRequest.created_at.desc()).all()
    results = []
    for r in requests:
        results.append({
            "id": r.id,
            "requester_id": r.requester_id,
            "requester_name": r.requester.full_name if r.requester else "Unknown",
            "blood_group": r.blood_group,
            "units_required": r.units_required,
            "urgency": r.urgency,
            "hospital_name": r.hospital_name,
            "hospital_address": r.hospital_address,
            "city": r.city,
            "state": r.state,
            "status": r.status,
            "created_at": r.created_at,
            "fulfilled_at": r.fulfilled_at
        })
    return results


@router.get("/analytics", response_model=AdminAnalyticsOut)
def get_admin_analytics(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    # 1. Requests by Blood Group
    bg_counts = (
        db.query(BloodRequest.blood_group, func.count(BloodRequest.id))
        .group_by(BloodRequest.blood_group)
        .all()
    )
    requests_by_bg = {bg: count for bg, count in bg_counts}
    # Ensure all groups present
    for grp in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
        if grp not in requests_by_bg:
            requests_by_bg[grp] = 0

    # 2. Requests by Status
    status_counts = (
        db.query(BloodRequest.status, func.count(BloodRequest.id))
        .group_by(BloodRequest.status)
        .all()
    )
    requests_by_status = {st: count for st, count in status_counts}

    # 3. Donations over time (by month or donation_date)
    donations_query = (
        db.query(Donation.donation_date, func.count(Donation.id))
        .filter(Donation.donation_status == "verified")
        .group_by(Donation.donation_date)
        .order_by(Donation.donation_date)
        .limit(10)
        .all()
    )
    donations_over_time = {str(d_date): count for d_date, count in donations_query}

    # 4. Requests by City
    city_counts = (
        db.query(BloodRequest.city, func.count(BloodRequest.id))
        .group_by(BloodRequest.city)
        .order_by(func.count(BloodRequest.id).desc())
        .limit(10)
        .all()
    )
    requests_by_city = {city: count for city, count in city_counts if city}

    # 5. Donor Availability Distribution
    avail_counts = (
        db.query(DonorProfile.availability_status, func.count(DonorProfile.id))
        .group_by(DonorProfile.availability_status)
        .all()
    )
    donor_availability = {st: count for st, count in avail_counts}

    return AdminAnalyticsOut(
        requests_by_blood_group=requests_by_bg,
        requests_by_status=requests_by_status,
        donations_over_time=donations_over_time,
        requests_by_city=requests_by_city,
        donor_availability_distribution=donor_availability
    )
