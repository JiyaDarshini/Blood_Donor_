from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import re
from app.database import get_db
from app.models import User, DonorProfile, PatientProfile, PhoneVerification
from app.schemas import (
    UserRegister, UserLogin, Token, UserOut, DonorProfileOut, PatientProfileOut,
    SendOtpRequest, SendOtpResponse, VerifyOtpRequest, VerifyOtpResponse
)
from app.security.auth import get_password_hash, verify_password, create_access_token, get_current_active_user
from app.services.notification_service import create_notification
from app.services.audit_service import create_audit_log
from app.services.sms_service import generate_otp, send_otp_sms, normalize_phone_number
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/send-otp", response_model=SendOtpResponse)
def send_otp(req: SendOtpRequest, db: Session = Depends(get_db)):
    clean_phone = normalize_phone_number(req.phone)
    raw_digits = re.sub(r"[^\d]", "", clean_phone)
    if len(raw_digits) < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid phone number (at least 7 digits)."
        )

    # Rate limiting: 30 seconds cooldown between requests for the same number
    cooldown_cutoff = datetime.utcnow() - timedelta(seconds=30)
    recent_req = (
        db.query(PhoneVerification)
        .filter(PhoneVerification.phone == clean_phone, PhoneVerification.created_at > cooldown_cutoff)
        .first()
    )
    if recent_req:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 30 seconds before requesting another verification code."
        )

    otp = generate_otp(6)
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    verification = PhoneVerification(
        phone=clean_phone,
        otp_code=otp,
        is_verified=False,
        attempts=0,
        expires_at=expires_at
    )
    db.add(verification)
    db.commit()

    sms_res = send_otp_sms(clean_phone, otp)

    dev_otp = otp if (settings.ENVIRONMENT == "development" or settings.SMS_PROVIDER == "none") else None

    return SendOtpResponse(
        success=True,
        message=f"Verification SMS sent to {clean_phone}.",
        phone=clean_phone,
        dev_otp=dev_otp
    )


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    clean_phone = normalize_phone_number(req.phone)
    otp_input = req.otp_code.strip()

    verification = (
        db.query(PhoneVerification)
        .filter(PhoneVerification.phone == clean_phone, PhoneVerification.is_verified == False)
        .order_by(PhoneVerification.created_at.desc())
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending verification code found for this phone number. Please request a new OTP."
        )

    if verification.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many incorrect attempts. Please request a new verification code."
        )

    if datetime.utcnow() > verification.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new OTP."
        )

    if verification.otp_code != otp_input:
        verification.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check and try again."
        )

    verification.is_verified = True
    db.commit()

    return VerifyOtpResponse(
        success=True,
        message="Phone number verified successfully!",
        phone=clean_phone
    )


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

    # Phone number verification validation
    is_phone_verified = False
    if user_in.phone:
        clean_phone = normalize_phone_number(user_in.phone)
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        verified_rec = (
            db.query(PhoneVerification)
            .filter(
                PhoneVerification.phone == clean_phone,
                PhoneVerification.is_verified == True,
                PhoneVerification.created_at >= cutoff
            )
            .order_by(PhoneVerification.created_at.desc())
            .first()
        )

        if verified_rec:
            is_phone_verified = True
        elif user_in.otp_code:
            active_rec = (
                db.query(PhoneVerification)
                .filter(
                    PhoneVerification.phone == clean_phone,
                    PhoneVerification.otp_code == user_in.otp_code.strip(),
                    PhoneVerification.is_verified == False,
                    PhoneVerification.expires_at >= datetime.utcnow()
                )
                .order_by(PhoneVerification.created_at.desc())
                .first()
            )
            if active_rec:
                active_rec.is_verified = True
                is_phone_verified = True
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired SMS OTP code provided."
                )
        elif settings.REQUIRE_PHONE_VERIFICATION and settings.ENVIRONMENT != "test":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number verification required. Please verify with SMS OTP before completing registration."
            )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email.lower(),
        phone=normalize_phone_number(user_in.phone) if user_in.phone else None,
        is_phone_verified=is_phone_verified,
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
            "is_phone_verified": getattr(current_user, "is_phone_verified", False),
            "role": current_user.role,
            "account_status": current_user.account_status,
            "created_at": current_user.created_at
        },
        "profile": profile_data
    }
