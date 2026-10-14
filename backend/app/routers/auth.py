from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.database import get_db
from app.models import User, DonorProfile, PatientProfile
from app.schemas import UserRegister, UserLogin, Token, UserOut, DonorProfileOut, PatientProfileOut
from app.security.auth import get_password_hash, verify_password, create_access_token, get_current_active_user
from app.services.notification_service import create_notification
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check if email exists
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    # Disallow direct admin registration from public form
    role = user_in.role.lower()
    if role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be registered publicly."
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email.lower(),
        phone=user_in.phone,
        password_hash=hashed_pw,
        role=role,
        account_status="active"
    )
    db.add(new_user)
    db.flush()

    # Create role-specific profile
    if role == "donor":
        blood_grp = (user_in.blood_group or "O+").upper()
        donor_prof = DonorProfile(
            user_id=new_user.id,
            blood_group=blood_grp,
            date_of_birth=user_in.date_of_birth,
            address=user_in.address,
            city=user_in.city,
            state=user_in.state,
            postal_code=user_in.postal_code,
            latitude=user_in.latitude,
            longitude=user_in.longitude,
            availability_status=user_in.availability_status or "available",
            consent_to_share=user_in.consent_to_share,
            is_verified=False
        )
        db.add(donor_prof)
    elif role == "patient":
        patient_prof = PatientProfile(
            user_id=new_user.id,
            city=user_in.city,
            state=user_in.state,
            preferred_contact_method=user_in.preferred_contact_method or "phone"
        )
        db.add(patient_prof)

    db.commit()
    db.refresh(new_user)

    # Welcome notification
    create_notification(
        db,
        user_id=new_user.id,
        title="Welcome to Blood SOS!",
        message=f"Hello {new_user.full_name}, thank you for joining Blood SOS. Complete your profile and stay ready to save lives.",
        notification_type="welcome"
    )

    create_audit_log(
        db,
        action="user_registered",
        entity_type="user",
        actor_user_id=new_user.id,
        entity_id=new_user.id,
        metadata={"role": new_user.role, "email": new_user.email}
    )

    access_token = create_access_token(
        data={"sub": new_user.id, "role": new_user.role, "name": new_user.full_name}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=new_user.id,
        role=new_user.role,
        full_name=new_user.full_name,
        email=new_user.email
    )


@router.post("/login", response_model=Token)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_in.email.lower()).first()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if user.account_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended by an administrator."
        )

    access_token = create_access_token(
        data={"sub": user.id, "role": user.role, "name": user.full_name}
    )

    create_audit_log(
        db,
        action="user_login",
        entity_type="user",
        actor_user_id=user.id,
        entity_id=user.id
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        role=user.role,
        full_name=user.full_name,
        email=user.email
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    profile_data = None
    if current_user.role == "donor" and current_user.donor_profile:
        dp = current_user.donor_profile
        profile_data = {
            "id": dp.id,
            "blood_group": dp.blood_group,
            "date_of_birth": str(dp.date_of_birth) if dp.date_of_birth else None,
            "address": dp.address,
            "city": dp.city,
            "state": dp.state,
            "postal_code": dp.postal_code,
            "latitude": dp.latitude,
            "longitude": dp.longitude,
            "availability_status": dp.availability_status,
            "is_verified": dp.is_verified,
            "last_donation_date": str(dp.last_donation_date) if dp.last_donation_date else None,
            "consent_to_share": dp.consent_to_share
        }
    elif current_user.role == "patient" and current_user.patient_profile:
        pp = current_user.patient_profile
        profile_data = {
            "id": pp.id,
            "city": pp.city,
            "state": pp.state,
            "preferred_contact_method": pp.preferred_contact_method
        }

    return {
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "role": current_user.role,
            "account_status": current_user.account_status,
            "created_at": current_user.created_at
        },
        "profile": profile_data
    }
