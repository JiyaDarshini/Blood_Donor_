import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Date, Float, Boolean, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), default="donor", nullable=False)  # admin, donor, patient
    account_status = Column(String(50), default="active", nullable=False)  # active, pending, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    donor_profile = relationship("DonorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    patient_profile = relationship("PatientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    requests = relationship("BloodRequest", back_populates="requester", foreign_keys="BloodRequest.requester_id")
    invitations = relationship("DonorInvitation", back_populates="donor", foreign_keys="DonorInvitation.donor_id")
    donations = relationship("Donation", back_populates="donor", foreign_keys="Donation.donor_id")
    reward_transactions = relationship("RewardTransaction", back_populates="user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class DonorProfile(Base):
    __tablename__ = "donor_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    blood_group = Column(String(10), index=True, nullable=False)  # A+, A-, B+, B-, AB+, AB-, O+, O-
    address = Column(Text, nullable=True)  # Private, never exposed publicly
    city = Column(String(100), index=True, nullable=True)
    state = Column(String(100), index=True, nullable=True)
    postal_code = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    availability_status = Column(String(50), default="available", index=True)  # available, unavailable, temporarily_unavailable, suspended
    is_verified = Column(Boolean, default=False)
    last_donation_date = Column(Date, nullable=True)
    consent_to_share = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="donor_profile")


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    preferred_contact_method = Column(String(50), default="phone")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="patient_profile")


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    requester_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    blood_group = Column(String(10), index=True, nullable=False)
    units_required = Column(Integer, default=1, nullable=False)
    urgency = Column(String(20), default="normal", index=True)  # critical, high, normal
    hospital_name = Column(String(255), nullable=False)
    hospital_address = Column(Text, nullable=False)
    city = Column(String(100), index=True, nullable=False)
    state = Column(String(100), index=True, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    recipient_name = Column(String(255), nullable=True)
    preferred_contact_method = Column(String(50), default="phone")
    status = Column(String(50), default="submitted", index=True)  # submitted, searching, responses_received, assistance_arranged, fulfilled, cancelled, expired
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)

    # Relationships
    requester = relationship("User", back_populates="requests", foreign_keys=[requester_id])
    invitations = relationship("DonorInvitation", back_populates="blood_request", cascade="all, delete-orphan")
    donations = relationship("Donation", back_populates="blood_request")
    status_history = relationship("RequestStatusHistory", back_populates="blood_request", cascade="all, delete-orphan")


class DonorInvitation(Base):
    __tablename__ = "donor_invitations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    blood_request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    donor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="pending")  # pending, accepted, declined
    invited_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("blood_request_id", "donor_id", name="uq_request_donor_invitation"),
    )

    # Relationships
    blood_request = relationship("BloodRequest", back_populates="invitations")
    donor = relationship("User", back_populates="invitations", foreign_keys=[donor_id])


class Donation(Base):
    __tablename__ = "donations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    blood_request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    donor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    donation_date = Column(Date, nullable=False)
    donation_status = Column(String(50), default="completed_pending_verification")  # completed_pending_verification, verified, rejected
    verified_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    units_donated = Column(Integer, default=1)
    hospital_name = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    blood_request = relationship("BloodRequest", back_populates="donations")
    donor = relationship("User", back_populates="donations", foreign_keys=[donor_id])
    reward_transaction = relationship("RewardTransaction", back_populates="donation", uselist=False)


class RewardTransaction(Base):
    __tablename__ = "reward_transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    donation_id = Column(String(36), ForeignKey("donations.id", ondelete="SET NULL"), nullable=True, index=True)
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # donation_reward, admin_adjustment
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "donation_id", name="uq_user_donation_reward"),
    )

    # Relationships
    user = relationship("User", back_populates="reward_transactions")
    donation = relationship("Donation", back_populates="reward_transaction")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)  # sos_alert, invitation, response, status_change, reward, verification
    related_request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="SET NULL"), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="notifications")
    blood_request = relationship("BloodRequest")


class RequestStatusHistory(Base):
    __tablename__ = "request_status_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    blood_request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    blood_request = relationship("BloodRequest", back_populates="status_history")
    user = relationship("User", foreign_keys=[changed_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(64), nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON-serialized audit data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    actor = relationship("User", foreign_keys=[actor_user_id])
