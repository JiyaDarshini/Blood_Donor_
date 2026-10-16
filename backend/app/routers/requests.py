from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from datetime import datetime, timedelta
from typing import Optional, List
from app.database import get_db
from app.models import (
    User, BloodRequest, DonorProfile, DonorInvitation,
    RequestStatusHistory, Donation
)
from app.schemas import (
    BloodRequestCreate, BloodRequestOut, BloodRequestStatusUpdate
)
from app.security.auth import get_current_active_user, require_role
from app.services.compatibility import get_compatible_donor_groups
from app.services.distance import haversine_distance
from app.services.notification_service import create_notification
from app.services.audit_service import create_audit_log
from app.config import settings

router = APIRouter(prefix="/requests", tags=["Blood Requests"])


def format_requests_out_batch(requests: List[BloodRequest], current_user: User, db: Session) -> List[BloodRequestOut]:
    if not requests:
        return []

    req_ids = [r.id for r in requests]

    # Batch compute accepted count and matched count in a single SQL query
    inv_stats = (
        db.query(
            DonorInvitation.blood_request_id,
            func.count(DonorInvitation.id).label("matched_count"),
            func.sum(case((DonorInvitation.status == "accepted", 1), else_=0)).label("accepted_count")
        )
        .filter(DonorInvitation.blood_request_id.in_(req_ids))
        .group_by(DonorInvitation.blood_request_id)
        .all()
    )
    stats_map = {row[0]: (row[1], int(row[2] or 0)) for row in inv_stats}

    # Batch check accepted status for current_user if donor
    user_accepted_req_ids = set()
    if current_user.role not in ("admin",):
        accepted_rows = (
            db.query(DonorInvitation.blood_request_id)
            .filter(
                DonorInvitation.blood_request_id.in_(req_ids),
                DonorInvitation.donor_id == current_user.id,
                DonorInvitation.status == "accepted"
            )
            .all()
        )
        user_accepted_req_ids = {row[0] for row in accepted_rows}

    out = []
    for req in requests:
        matched_count, accepted_count = stats_map.get(req.id, (0, 0))
        is_authorized = (
            current_user.id == req.requester_id or
            current_user.role == "admin" or
            req.id in user_accepted_req_ids
        )

        requester_user = req.requester
        req_name = requester_user.full_name if requester_user else "Requester"
        req_phone = requester_user.phone if (is_authorized and requester_user) else "Protected (Accept Request to Reveal)"
        req_email = requester_user.email if (is_authorized and requester_user) else "Protected"

        out.append(BloodRequestOut(
            id=req.id,
            requester_id=req.requester_id,
            requester_name=req_name,
            requester_phone=req_phone,
            requester_email=req_email,
            blood_group=req.blood_group,
            units_required=req.units_required,
            urgency=req.urgency,
            hospital_name=req.hospital_name,
            hospital_address=req.hospital_address,
            city=req.city,
            state=req.state,
            latitude=req.latitude,
            longitude=req.longitude,
            description=req.description,
            recipient_name=req.recipient_name,
            preferred_contact_method=req.preferred_contact_method,
            status=req.status,
            expires_at=req.expires_at,
            created_at=req.created_at,
            updated_at=req.updated_at,
            fulfilled_at=req.fulfilled_at,
            matched_donors_count=matched_count,
            accepted_donors_count=accepted_count
        ))
    return out


def format_request_out(req: BloodRequest, current_user: User, db: Session) -> BloodRequestOut:
    return format_requests_out_batch([req], current_user, db)[0]


@router.post("", response_model=BloodRequestOut, status_code=status.HTTP_201_CREATED)
def create_blood_request(
    request_in: BloodRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit an Emergency SOS Blood Request.
    - Saves request to database.
    - Matches active, available, compatible donors within search radius.
    - Sends donor invitations and push notifications.
    """
    # Calculate expiration based on urgency
    expire_hours = 24 if request_in.urgency == "critical" else (48 if request_in.urgency == "high" else 72)
    expires_at = datetime.utcnow() + timedelta(hours=expire_hours)

    new_request = BloodRequest(
        requester_id=current_user.id,
        blood_group=request_in.blood_group.upper(),
        units_required=request_in.units_required,
        urgency=request_in.urgency.lower(),
        hospital_name=request_in.hospital_name,
        hospital_address=request_in.hospital_address,
        city=request_in.city,
        state=request_in.state,
        latitude=request_in.latitude,
        longitude=request_in.longitude,
        description=request_in.description,
        recipient_name=request_in.recipient_name or current_user.full_name,
        preferred_contact_method=request_in.preferred_contact_method,
        status="searching",
        expires_at=expires_at
    )
    db.add(new_request)
    db.flush()

    # Log initial status history
    history = RequestStatusHistory(
        blood_request_id=new_request.id,
        previous_status=None,
        new_status="searching",
        changed_by=current_user.id,
        change_reason=f"Emergency SOS initiated with urgency {request_in.urgency}"
    )
    db.add(history)

    # Find compatible donor groups
    compatible_groups = get_compatible_donor_groups(new_request.blood_group)

    # Query active, available donors with compatible blood group
    donor_query = (
        db.query(DonorProfile, User)
        .join(User, DonorProfile.user_id == User.id)
        .filter(User.account_status == "active")
        .filter(DonorProfile.availability_status == "available")
        .filter(DonorProfile.blood_group.in_(compatible_groups))
        .filter(User.id != current_user.id)  # Requester shouldn't invite themselves
    )

    matched_donors = donor_query.all()
    invitation_count = 0

    for dp, u in matched_donors:
        # Distance check if both have coordinates
        is_in_range = True
        if new_request.latitude and new_request.longitude and dp.latitude and dp.longitude:
            dist = haversine_distance(new_request.latitude, new_request.longitude, dp.latitude, dp.longitude)
            if dist is not None and dist > settings.DONOR_SEARCH_RADIUS_KM:
                is_in_range = False
        elif dp.city and new_request.city:
            # Fallback to city match if coordinates not available
            if dp.city.strip().lower() != new_request.city.strip().lower():
                is_in_range = False

        if is_in_range:
            invitation = DonorInvitation(
                blood_request_id=new_request.id,
                donor_id=u.id,
                status="pending"
            )
            db.add(invitation)
            invitation_count += 1

            # Dispatch notification to matching donor
            urgency_prefix = "🚨 CRITICAL SOS:" if new_request.urgency == "critical" else "Urgent Blood Request:"
            create_notification(
                db,
                user_id=u.id,
                title=f"{urgency_prefix} {new_request.blood_group} required at {new_request.hospital_name}",
                message=(
                    f"A patient urgently requires {new_request.units_required} unit(s) of {new_request.blood_group} "
                    f"blood in {new_request.city}, {new_request.state} at {new_request.hospital_name}. "
                    f"Please review and respond if you are able to donate."
                ),
                notification_type="sos_alert",
                related_request_id=new_request.id
            )

    db.commit()
    db.refresh(new_request)

    # Notify requester
    create_notification(
        db,
        user_id=current_user.id,
        title="SOS Blood Request Broadcasted",
        message=(
            f"Your SOS request for {new_request.blood_group} blood has been broadcasted to "
            f"{invitation_count} compatible donor(s) nearby. Monitor responses in your dashboard."
        ),
        notification_type="status_change",
        related_request_id=new_request.id
    )

    create_audit_log(
        db,
        action="create_blood_request",
        entity_type="blood_request",
        actor_user_id=current_user.id,
        entity_id=new_request.id,
        metadata={"urgency": new_request.urgency, "matched_donors": invitation_count}
    )

    return format_request_out(new_request, current_user, db)


@router.get("", response_model=List[BloodRequestOut])
def list_requests(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    only_mine: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(BloodRequest).options(joinedload(BloodRequest.requester))

    if current_user.role == "patient" or only_mine:
        query = query.filter(BloodRequest.requester_id == current_user.id)
    elif current_user.role == "donor":
        # Donors see open requests they were invited to or compatible requests in active status
        invitation_req_ids = db.query(DonorInvitation.blood_request_id).filter(
            DonorInvitation.donor_id == current_user.id
        ).subquery()
        query = query.filter(
            (BloodRequest.id.in_(invitation_req_ids)) |
            (BloodRequest.status.in_(["submitted", "searching", "responses_received"]))
        )

    if status:
        query = query.filter(BloodRequest.status == status)
    if urgency:
        query = query.filter(BloodRequest.urgency == urgency)
    if blood_group:
        query = query.filter(BloodRequest.blood_group == blood_group.upper())
    if city:
        query = query.filter(BloodRequest.city.ilike(f"%{city}%"))

    requests = query.order_by(BloodRequest.created_at.desc()).all()
    return format_requests_out_batch(requests, current_user, db)


@router.get("/{request_id}", response_model=BloodRequestOut)
def get_request(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    req = db.query(BloodRequest).options(joinedload(BloodRequest.requester)).filter(BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    return format_request_out(req, current_user, db)


@router.patch("/{request_id}/status", response_model=BloodRequestOut)
def update_request_status(
    request_id: str,
    status_in: BloodRequestStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    req = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Blood request not found.")

    # Authorization check
    if current_user.role != "admin" and req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this request.")

    old_status = req.status
    new_status = status_in.status

    req.status = new_status
    if new_status == "fulfilled":
        req.fulfilled_at = datetime.utcnow()

    history = RequestStatusHistory(
        blood_request_id=req.id,
        previous_status=old_status,
        new_status=new_status,
        changed_by=current_user.id,
        change_reason=status_in.change_reason or f"Status updated to {new_status}"
    )
    db.add(history)
    db.commit()
    db.refresh(req)

    # Notify requester if changed by admin
    if current_user.id != req.requester_id:
        create_notification(
            db,
            user_id=req.requester_id,
            title=f"Blood Request Status: {new_status.title()}",
            message=f"Your blood request status for {req.blood_group} has changed from {old_status} to {new_status}.",
            notification_type="status_change",
            related_request_id=req.id
        )

    create_audit_log(
        db,
        action="update_request_status",
        entity_type="blood_request",
        actor_user_id=current_user.id,
        entity_id=req.id,
        metadata={"old_status": old_status, "new_status": new_status}
    )

    return format_request_out(req, current_user, db)


@router.post("/{request_id}/cancel", response_model=BloodRequestOut)
def cancel_request(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    req = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Blood request not found.")

    if current_user.role != "admin" and req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this request.")

    old_status = req.status
    req.status = "cancelled"

    history = RequestStatusHistory(
        blood_request_id=req.id,
        previous_status=old_status,
        new_status="cancelled",
        changed_by=current_user.id,
        change_reason="Request cancelled by user or administrator."
    )
    db.add(history)
    db.commit()
    db.refresh(req)

    # Notify invited donors who accepted that assistance is no longer needed
    accepted_invites = db.query(DonorInvitation).filter(
        DonorInvitation.blood_request_id == req.id,
        DonorInvitation.status == "accepted"
    ).all()

    for inv in accepted_invites:
        create_notification(
            db,
            user_id=inv.donor_id,
            title="Blood Request Cancelled",
            message=f"The blood request at {req.hospital_name} for {req.blood_group} was cancelled as blood is no longer required.",
            notification_type="status_change",
            related_request_id=req.id
        )

    create_audit_log(
        db,
        action="cancel_blood_request",
        entity_type="blood_request",
        actor_user_id=current_user.id,
        entity_id=req.id
    )

    return format_request_out(req, current_user, db)
