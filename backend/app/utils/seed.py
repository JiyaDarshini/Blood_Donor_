"""
Blood SOS Seed Data Script.
Creates default administrator, verified donors across blood groups,
sample emergency requests, and initial reward records.
"""

from datetime import datetime, date, timedelta
from app.database import SessionLocal, Base, engine
from app.models import (
    User, DonorProfile, PatientProfile, BloodRequest,
    DonorInvitation, Donation, RewardTransaction, Notification, RequestStatusHistory, AuditLog
)
from app.security.auth import get_password_hash


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if admin already exists
        admin = db.query(User).filter(User.email == "admin@bloodsos.org").first()
        if not admin:
            print("[SEED] Creating initial Administrator account...")
            admin = User(
                full_name="Emergency Response Administrator",
                email="admin@bloodsos.org",
                phone="+1 (555) 019-2834",
                password_hash=get_password_hash("Admin@12345"),
                role="admin",
                account_status="active"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print("[SEED] Administrator created: admin@bloodsos.org / Admin@12345")

        # Check if sample donors exist
        donor_count = db.query(User).filter(User.role == "donor").count()
        if donor_count < 3:
            print("[SEED] Seeding realistic sample donors and test patient...")

            sample_donors = [
                {
                    "name": "Sarah Connor",
                    "email": "sarah.connor@example.com",
                    "phone": "+1 (555) 111-2222",
                    "blood": "O-",
                    "city": "Austin",
                    "state": "TX",
                    "lat": 30.2672,
                    "lon": -97.7431,
                    "verified": True,
                    "status": "available",
                    "dob": date(1992, 5, 14)
                },
                {
                    "name": "David Miller",
                    "email": "david.miller@example.com",
                    "phone": "+1 (555) 222-3333",
                    "blood": "O+",
                    "city": "Austin",
                    "state": "TX",
                    "lat": 30.2850,
                    "lon": -97.7340,
                    "verified": True,
                    "status": "available",
                    "dob": date(1988, 11, 23)
                },
                {
                    "name": "Elena Rostova",
                    "email": "elena.rostova@example.com",
                    "phone": "+1 (555) 333-4444",
                    "blood": "A+",
                    "city": "Austin",
                    "state": "TX",
                    "lat": 30.3072,
                    "lon": -97.7560,
                    "verified": True,
                    "status": "available",
                    "dob": date(1995, 2, 8)
                },
                {
                    "name": "Marcus Vance",
                    "email": "marcus.vance@example.com",
                    "phone": "+1 (555) 444-5555",
                    "blood": "B+",
                    "city": "Austin",
                    "state": "TX",
                    "lat": 30.2500,
                    "lon": -97.7600,
                    "verified": True,
                    "status": "available",
                    "dob": date(1990, 8, 19)
                },
                {
                    "name": "Chloe Bennett",
                    "email": "chloe.bennett@example.com",
                    "phone": "+1 (555) 555-6666",
                    "blood": "AB+",
                    "city": "Houston",
                    "state": "TX",
                    "lat": 29.7604,
                    "lon": -95.3698,
                    "verified": True,
                    "status": "available",
                    "dob": date(1994, 9, 30)
                },
                {
                    "name": "Johnathan Reed",
                    "email": "john.donor@example.com",
                    "phone": "+1 (555) 666-7777",
                    "blood": "A-",
                    "city": "Austin",
                    "state": "TX",
                    "lat": 30.2700,
                    "lon": -97.7200,
                    "verified": True,
                    "status": "available",
                    "dob": date(1991, 4, 12)
                }
            ]

            created_donors = []
            for d in sample_donors:
                user = User(
                    full_name=d["name"],
                    email=d["email"],
                    phone=d["phone"],
                    password_hash=get_password_hash("Donor@12345"),
                    role="donor",
                    account_status="active"
                )
                db.add(user)
                db.flush()

                prof = DonorProfile(
                    user_id=user.id,
                    blood_group=d["blood"],
                    date_of_birth=d["dob"],
                    city=d["city"],
                    state=d["state"],
                    latitude=d["lat"],
                    longitude=d["lon"],
                    availability_status=d["status"],
                    is_verified=d["verified"],
                    last_donation_date=date.today() - timedelta(days=45),
                    consent_to_share=True
                )
                db.add(prof)
                created_donors.append(user)

            # Create test Patient
            patient = User(
                full_name="Robert Langdon",
                email="patient@example.com",
                phone="+1 (555) 999-0000",
                password_hash=get_password_hash("Patient@12345"),
                role="patient",
                account_status="active"
            )
            db.add(patient)
            db.flush()

            patient_prof = PatientProfile(
                user_id=patient.id,
                city="Austin",
                state="TX",
                preferred_contact_method="phone"
            )
            db.add(patient_prof)
            db.commit()

            # Create sample Critical SOS request
            print("[SEED] Creating sample Emergency SOS Blood Request...")
            req1 = BloodRequest(
                requester_id=patient.id,
                blood_group="O+",
                units_required=2,
                urgency="critical",
                hospital_name="St. David's Medical Center",
                hospital_address="919 E 32nd St",
                city="Austin",
                state="TX",
                latitude=30.2925,
                longitude=-97.7275,
                description="Urgent surgery scheduled. Platelets and O+ blood units critically needed.",
                recipient_name="Robert Langdon",
                preferred_contact_method="phone",
                status="searching",
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.add(req1)
            db.flush()

            # Invitations for req1 (O- and O+ donors)
            for d in created_donors:
                if d.donor_profile.blood_group in ["O+", "O-"]:
                    inv = DonorInvitation(
                        blood_request_id=req1.id,
                        donor_id=d.id,
                        status="pending"
                    )
                    db.add(inv)
                    notif = Notification(
                        user_id=d.id,
                        title="🚨 CRITICAL SOS: O+ Blood required at St. David's",
                        message=f"Urgent O+ blood needed at St. David's Medical Center, Austin. Please respond immediately.",
                        notification_type="sos_alert",
                        related_request_id=req1.id
                    )
                    db.add(notif)

            # Create sample fulfilled donation & reward points
            sarah = created_donors[0]
            donation = Donation(
                donor_id=sarah.id,
                requester_id=patient.id,
                blood_request_id=req1.id,
                donation_date=date.today() - timedelta(days=20),
                donation_status="verified",
                verified_by=admin.id,
                verified_at=datetime.utcnow() - timedelta(days=19),
                units_donated=1,
                hospital_name="St. David's Medical Center",
                notes="Verified by hospital blood bank supervisor."
            )
            db.add(donation)
            db.flush()

            reward = RewardTransaction(
                user_id=sarah.id,
                donation_id=donation.id,
                points=100,
                transaction_type="donation_reward",
                description="Reward for verified blood donation on " + str(donation.donation_date)
            )
            db.add(reward)

            db.commit()
            print("[SEED] Sample data populated successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
