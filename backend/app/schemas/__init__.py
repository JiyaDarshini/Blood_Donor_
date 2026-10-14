from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime, date


# ===================== USER & AUTH SCHEMAS =====================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str
    email: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = None
    role: str = Field(default="donor", pattern="^(donor|patient|admin)$")
    
    # Optional fields for donor profile creation at registration
    blood_group: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    consent_to_share: bool = True
    availability_status: str = "available"

    # Optional fields for patient profile creation at registration
    preferred_contact_method: Optional[str] = "phone"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    account_status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== DONOR SCHEMAS =====================

VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}

class DonorProfileBase(BaseModel):
    blood_group: str
    date_of_birth: Optional[date] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability_status: str = "available"
    consent_to_share: bool = True

    @field_validator("blood_group")
    def validate_blood_group(cls, v):
        group = v.strip().upper()
        if group not in VALID_BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: {v}. Must be one of {', '.join(sorted(VALID_BLOOD_GROUPS))}")
        return group


class DonorProfileCreate(DonorProfileBase):
    address: Optional[str] = None


class DonorProfileUpdate(BaseModel):
    blood_group: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability_status: Optional[str] = None
    consent_to_share: Optional[bool] = None

    @field_validator("blood_group")
    def validate_blood_group(cls, v):
        if v is not None:
            group = v.strip().upper()
            if group not in VALID_BLOOD_GROUPS:
                raise ValueError(f"Invalid blood group: {v}")
            return group
        return v


class DonorAvailabilityUpdate(BaseModel):
    availability_status: str = Field(..., pattern="^(available|unavailable|temporarily_unavailable)$")


class DonorProfileOut(BaseModel):
    id: str
    user_id: str
    blood_group: str
    date_of_birth: Optional[date] = None
    address: Optional[str] = None  # Full address only returned to the donor themselves
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability_status: str
    is_verified: bool
    last_donation_date: Optional[date] = None
    consent_to_share: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DonorPublicOut(BaseModel):
    """Masked donor profile for nearby searches and requester views (privacy preserved)."""
    donor_id: str
    user_id: str
    full_name: str
    blood_group: str
    city: Optional[str] = None
    state: Optional[str] = None
    availability_status: str
    is_verified: bool
    last_donation_date: Optional[date] = None
    distance_km: Optional[float] = None
    latitude: Optional[float] = None  # Approximate/jittered or authorized
    longitude: Optional[float] = None
    total_donations: int = 0


# ===================== PATIENT SCHEMAS =====================

class PatientProfileCreate(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    preferred_contact_method: str = "phone"


class PatientProfileOut(BaseModel):
    id: str
    user_id: str
    city: Optional[str] = None
    state: Optional[str] = None
    preferred_contact_method: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== BLOOD REQUEST SCHEMAS =====================

VALID_URGENCY_LEVELS = {"critical", "high", "normal"}
VALID_REQUEST_STATUSES = {
    "submitted", "searching", "responses_received",
    "assistance_arranged", "fulfilled", "cancelled", "expired"
}

class BloodRequestCreate(BaseModel):
    blood_group: str
    units_required: int = Field(default=1, ge=1, le=20)
    urgency: str = Field(default="normal")
    hospital_name: str = Field(..., min_length=2, max_length=255)
    hospital_address: str = Field(..., min_length=3)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    recipient_name: Optional[str] = None
    preferred_contact_method: str = "phone"

    @field_validator("blood_group")
    def validate_blood_group(cls, v):
        group = v.strip().upper()
        if group not in VALID_BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: {v}")
        return group

    @field_validator("urgency")
    def validate_urgency(cls, v):
        urg = v.strip().lower()
        if urg not in VALID_URGENCY_LEVELS:
            raise ValueError(f"Urgency must be one of {VALID_URGENCY_LEVELS}")
        return urg


class BloodRequestStatusUpdate(BaseModel):
    status: str
    change_reason: Optional[str] = None

    @field_validator("status")
    def validate_status(cls, v):
        s = v.strip().lower()
        if s not in VALID_REQUEST_STATUSES:
            raise ValueError(f"Status must be one of {VALID_REQUEST_STATUSES}")
        return s


class BloodRequestOut(BaseModel):
    id: str
    requester_id: str
    requester_name: Optional[str] = None
    requester_phone: Optional[str] = None
    requester_email: Optional[str] = None
    blood_group: str
    units_required: int
    urgency: str
    hospital_name: str
    hospital_address: str
    city: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    recipient_name: Optional[str] = None
    preferred_contact_method: str
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    matched_donors_count: Optional[int] = 0
    accepted_donors_count: Optional[int] = 0

    class Config:
        from_attributes = True


# ===================== INVITATION SCHEMAS =====================

class InvitationRespond(BaseModel):
    response: str = Field(..., pattern="^(accepted|declined)$")


class DonorInvitationOut(BaseModel):
    id: str
    blood_request_id: str
    donor_id: str
    status: str
    invited_at: datetime
    responded_at: Optional[datetime] = None
    request_details: Optional[BloodRequestOut] = None

    class Config:
        from_attributes = True


# ===================== DONATION SCHEMAS =====================

class DonationCreate(BaseModel):
    blood_request_id: Optional[str] = None
    donation_date: date
    hospital_name: Optional[str] = None
    units_donated: int = Field(default=1, ge=1, le=5)
    notes: Optional[str] = None


class DonationVerify(BaseModel):
    action: str = Field(..., pattern="^(verify|reject)$")
    notes: Optional[str] = None
    points_override: Optional[int] = None


class DonationOut(BaseModel):
    id: str
    blood_request_id: Optional[str] = None
    donor_id: str
    donor_name: Optional[str] = None
    donor_blood_group: Optional[str] = None
    requester_id: Optional[str] = None
    donation_date: date
    donation_status: str
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    units_donated: int
    hospital_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    points_awarded: Optional[int] = None

    class Config:
        from_attributes = True


# ===================== REWARD SCHEMAS =====================

class RewardTransactionOut(BaseModel):
    id: str
    user_id: str
    donation_id: Optional[str] = None
    points: int
    transaction_type: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


class RewardSummaryOut(BaseModel):
    total_points: int
    total_verified_donations: int
    badges: List[str]
    next_milestone: str
    points_to_next_milestone: int
    transactions: List[RewardTransactionOut]


# ===================== NOTIFICATION SCHEMAS =====================

class NotificationOut(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    notification_type: str
    related_request_id: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===================== ADMIN SCHEMAS =====================

class AdminUserStatusUpdate(BaseModel):
    account_status: Optional[str] = Field(None, pattern="^(active|pending|suspended)$")
    is_verified: Optional[bool] = None


class AdminDashboardStats(BaseModel):
    total_users: int
    total_donors: int
    total_patients: int
    verified_donors: int
    available_donors: int
    total_requests: int
    critical_active_requests: int
    fulfilled_requests: int
    cancelled_requests: int
    verified_donations: int
    total_points_awarded: int


class AdminAnalyticsOut(BaseModel):
    requests_by_blood_group: Dict[str, int]
    requests_by_status: Dict[str, int]
    donations_over_time: Dict[str, int]
    requests_by_city: Dict[str, int]
    donor_availability_distribution: Dict[str, int]
