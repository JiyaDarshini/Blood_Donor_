from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models import User, RewardTransaction, Donation
from app.schemas import RewardSummaryOut, RewardTransactionOut
from app.security.auth import get_current_active_user

router = APIRouter(prefix="/rewards", tags=["Rewards & Points"])


@router.get("/me", response_model=RewardSummaryOut)
def get_my_rewards(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Total points from ledger
    total_pts = (
        db.query(func.coalesce(func.sum(RewardTransaction.points), 0))
        .filter(RewardTransaction.user_id == current_user.id)
        .scalar()
    )

    # Total verified donations
    verified_donations = (
        db.query(Donation)
        .filter(Donation.donor_id == current_user.id, Donation.donation_status == "verified")
        .count()
    )

    # Determine badges
    badges = []
    if verified_donations >= 1:
        badges.append("First Responder: 1 Verified Donation")
    if verified_donations >= 3:
        badges.append("Guardian Angel: 3 Donations")
    if verified_donations >= 5:
        badges.append("Silver Hero: 5 Donations")
    if verified_donations >= 10:
        badges.append("Legendary Life Saver: 10+ Donations")
    if total_pts >= 500:
        badges.append("Elite Contributor (500+ Pts)")

    # Milestone calculation
    milestones = [
        (100, "Bronze Saver (100 Pts)"),
        (300, "Silver Hero (300 Pts)"),
        (500, "Gold Guardian (500 Pts)"),
        (1000, "Platinum Legend (1000 Pts)"),
    ]
    next_milestone = "Maximum Tier Achieved!"
    points_to_next = 0
    for pts, title in milestones:
        if total_pts < pts:
            next_milestone = title
            points_to_next = pts - total_pts
            break

    transactions = (
        db.query(RewardTransaction)
        .filter(RewardTransaction.user_id == current_user.id)
        .order_by(RewardTransaction.created_at.desc())
        .all()
    )

    return RewardSummaryOut(
        total_points=int(total_pts),
        total_verified_donations=verified_donations,
        badges=badges,
        next_milestone=next_milestone,
        points_to_next_milestone=points_to_next,
        transactions=[
            RewardTransactionOut(
                id=t.id,
                user_id=t.user_id,
                donation_id=t.donation_id,
                points=t.points,
                transaction_type=t.transaction_type,
                description=t.description,
                created_at=t.created_at
            )
            for t in transactions
        ]
    )


@router.get("/me/transactions", response_model=List[RewardTransactionOut])
def get_transactions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    transactions = (
        db.query(RewardTransaction)
        .filter(RewardTransaction.user_id == current_user.id)
        .order_by(RewardTransaction.created_at.desc())
        .all()
    )
    return transactions
