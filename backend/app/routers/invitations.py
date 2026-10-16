from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import List
from app.database import get_db
from app.models import User, DonorInvitation, BloodRequest
from app.schemas import InvitationRespond, DonorInvitationOut, BloodRequestOut
from app.security.auth import get_current_active_user, require_role
from app.services.notification_service import create_notification
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/invitations", tags=["Donor Invitations"])


@router.get("/me", response_model=List[DonorInvitationOut])
def get_my_invitations(
    current_user: User = Depends(require_role(["donor", "admin"])),
    db: Session = Depends(get_db)
):
    invitations = (
        db.query(DonorInvitation)
        .options(joinedload(DonorInvitation.blood_request).joinedload(BloodRequest.requester))
        .filter(DonorInvitation.donor_id == current_user.id)
        .order_by(DonorInvitation.invited_at.desc())
        .all()
    )

    result = []
    for inv in invitations:
        req = inv.blood_request
        req_out = None
        if req:
            req_out = BloodRequestOut(
                id=req.id,
                requester_id=req.requester_id,
                requester_name=req.requester.full_name if req.requester else "Requester",
                requester_phone=req.requester.phone if (inv.status == "accepted" and req.requester) else "Hidden until accepted",
                requester_email=req.requester.email if (inv.status == "accepted" and req.requester) else "Hidden",
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
                fulfilled_at=req.fulfilled_at
            )

        result.append(DonorInvitationOut(
            id=inv.id,
            blood_request_id=inv.blood_request_id,
            donor_id=inv.donor_id,
            status=inv.status,
            invited_at=inv.invited_at,
            responded_at=inv.responded_at,
            request_details=req_out
        ))

    return result


@router.post("/{invitation_id}/respond", response_model=DonorInvitationOut)
def respond_invitation(
    invitation_id: str,
    response_in: InvitationRespond,
    current_user: User = Depends(require_role(["donor", "admin"])),
    db: Session = Depends(get_db)
):
    inv = db.query(DonorInvitation).filter(DonorInvitation.id == invitation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if inv.donor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to respond to this invitation.")

    inv.status = response_in.response
    inv.responded_at = datetime.utcnow()

    req = inv.blood_request
    if req:
        if response_in.response == "accepted":
            # Upgrade request status if in searching
            if req.status == "searching":
                req.status = "responses_received"

            # Notify requester
            create_notification(
                db,
                user_id=req.requester_id,
                title="🩸 A Donor Accepted Your Request!",
                message=(
                    f"Good news! Donor {current_user.full_name} ({current_user.phone or 'Contact in app'}) "
                    f"has accepted your request for {req.blood_group} blood at {req.hospital_name}. "
                    f"Please contact them to coordinate."
                ),
                notification_type="response",
                related_request_id=req.id
            )
        else:
            # Donor declined
            create_notification(
                db,
                user_id=req.requester_id,
                title="Donor Update",
                message=f"A potential donor was unavailable to fulfill your request for {req.blood_group}. Other donors are still being matched.",
                notification_type="response",
                related_request_id=req.id
            )

    db.commit()
    db.refresh(inv)

    create_audit_log(
        db,
        action="respond_donor_invitation",
        entity_type="donor_invitation",
        actor_user_id=current_user.id,
        entity_id=inv.id,
        metadata={"response": response_in.response}
    )

    req_out = None
    if req:
        req_out = BloodRequestOut(
            id=req.id,
            requester_id=req.requester_id,
            requester_name=req.requester.full_name if req.requester else "Requester",
            requester_phone=req.requester.phone if (inv.status == "accepted" and req.requester) else "Hidden",
            requester_email=req.requester.email if (inv.status == "accepted" and req.requester) else "Hidden",
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
            fulfilled_at=req.fulfilled_at
        )

    return DonorInvitationOut(
        id=inv.id,
        blood_request_id=inv.blood_request_id,
        donor_id=inv.donor_id,
        status=inv.status,
        invited_at=inv.invited_at,
        responded_at=inv.responded_at,
        request_details=req_out
    )
