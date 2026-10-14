from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from app.database import get_db
from app.models import (
    User, Donation, DonorProfile, BloodRequest, RewardTransaction
)
from app.schemas import DonationCreate, DonationVerify, DonationOut
from app.security.auth import get_current_active_user, require_role
from app.services.notification_service import create_notification
from app.services.audit_service import create_audit_log
from app.config import settings

router = APIRouter(tags=["Donations"])


def format_donation_out(d: Donation, db: Session) -> DonationOut:
    donor = d.donor
    points_awarded = None
    if d.reward_transaction:
        points_awarded = d.reward_transaction.points

    return DonationOut(
        id=d.id,
        blood_request_id=d.blood_request_id,
        donor_id=d.donor_id,
        donor_name=donor.full_name if donor else "Unknown Donor",
        donor_blood_group=donor.donor_profile.blood_group if (donor and donor.donor_profile) else "N/A",
        requester_id=d.requester_id,
        donation_date=d.donation_date,
        donation_status=d.donation_status,
        verified_by=d.verified_by,
        verified_at=d.verified_at,
        units_donated=d.units_donated,
        hospital_name=d.hospital_name,
        notes=d.notes,
        created_at=d.created_at,
        points_awarded=points_awarded
    )


@router.post("/donations", response_model=DonationOut, status_code=status.HTTP_201_CREATED)
def record_donation(
    donation_in: DonationCreate,
    current_user: User = Depends(require_role(["donor", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Submit a donation record for administrator verification.
    Points are NOT awarded immediately; an admin must verify the donation first.
    """
    requester_id = None
    if donation_in.blood_request_id:
        req = db.query(BloodRequest).filter(BloodRequest.id == donation_in.blood_request_id).first()
        if req:
            requester_id = req.requester_id
            if not donation_in.hospital_name:
                donation_in.hospital_name = req.hospital_name

    new_donation = Donation(
        donor_id=current_user.id,
        blood_request_id=donation_in.blood_request_id,
        requester_id=requester_id,
        donation_date=donation_in.donation_date,
        donation_status="completed_pending_verification",
        units_donated=donation_in.units_donated,
        hospital_name=donation_in.hospital_name,
        notes=donation_in.notes
    )
    db.add(new_donation)
    db.commit()
    db.refresh(new_donation)

    # Notify admins about pending donation
    admins = db.query(User).filter(User.role == "admin").all()
    for admin in admins:
        create_notification(
            db,
            user_id=admin.id,
            title="Donation Pending Verification",
            message=f"Donor {current_user.full_name} submitted a completed donation record for verification.",
            notification_type="verification"
        )

    create_notification(
        db,
        user_id=current_user.id,
        title="Donation Record Submitted",
        message="Thank you! Your donation record is awaiting administrative verification. Reward points will be awarded upon approval.",
        notification_type="verification"
    )

    create_audit_log(
        db,
        action="submit_donation_record",
        entity_type="donation",
        actor_user_id=current_user.id,
        entity_id=new_donation.id
    )

    return format_donation_out(new_donation, db)


@router.get("/donations/me", response_model=List[DonationOut])
def get_my_donations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    donations = (
        db.query(Donation)
        .filter(Donation.donor_id == current_user.id)
        .order_by(Donation.donation_date.desc())
        .all()
    )
    return [format_donation_out(d, db) for d in donations]


@router.get("/admin/donations", response_model=List[DonationOut])
def list_admin_donations(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    donations = db.query(Donation).order_by(Donation.created_at.desc()).all()
    return [format_donation_out(d, db) for d in donations]


@router.patch("/admin/donations/{donation_id}/verify", response_model=DonationOut)
def verify_donation(
    donation_id: str,
    verify_in: DonationVerify,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Administrator verifies or rejects a donation record.
    On verification, awards reward points in an immutable points ledger atomically.
    Prevents duplicate reward awards using database checks.
    """
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation record not found.")

    if verify_in.action == "reject":
        donation.donation_status = "rejected"
        donation.verified_by = current_user.id
        donation.verified_at = datetime.utcnow()
        if verify_in.notes:
            donation.notes = f"{donation.notes or ''}\nAdmin note: {verify_in.notes}".strip()
        db.commit()
        db.refresh(donation)

        create_notification(
            db,
            user_id=donation.donor_id,
            title="Donation Verification Notice",
            message=f"Your donation record from {donation.donation_date} could not be verified.",
            notification_type="verification"
        )
        return format_donation_out(donation, db)

    # Verification workflow
    donation.donation_status = "verified"
    donation.verified_by = current_user.id
    donation.verified_at = datetime.utcnow()

    # Award points safely in points ledger
    existing_reward = db.query(RewardTransaction).filter(
        RewardTransaction.donation_id == donation.id
    ).first()

    points_to_award = verify_in.points_override or settings.POINTS_PER_VERIFIED_DONATION
    if not existing_reward:
        reward = RewardTransaction(
            user_id=donation.donor_id,
            donation_id=donation.id,
            points=points_to_award,
            transaction_type="donation_reward",
            description=f"Reward for verified blood donation on {donation.donation_date}"
        )
        db.add(reward)

    # Update donor profile last donation date & verified status
    donor_prof = db.query(DonorProfile).filter(DonorProfile.user_id == donation.donor_id).first()
    if donor_prof:
        donor_prof.last_donation_date = donation.donation_date
        donor_prof.is_verified = True

    # If associated with a blood request, check and update request status to fulfilled
    if donation.blood_request_id:
        req = db.query(BloodRequest).filter(BloodRequest.id == donation.blood_request_id).first()
        if req and req.status != "fulfilled":
            req.status = "fulfilled"
            req.fulfilled_at = datetime.utcnow()

    db.commit()
    db.refresh(donation)

    # Notify donor
    create_notification(
        db,
        user_id=donation.donor_id,
        title="🎉 Donation Verified! Reward Points Added!",
        message=(
            f"Your donation on {donation.donation_date} has been officially verified! "
            f"You earned +{points_to_award} LifePoints in your rewards wallet."
        ),
        notification_type="reward"
    )

    create_audit_log(
        db,
        action="verify_donation",
        entity_type="donation",
        actor_user_id=current_user.id,
        entity_id=donation.id,
        metadata={"points_awarded": points_to_award}
    )

    return format_donation_out(donation, db)
