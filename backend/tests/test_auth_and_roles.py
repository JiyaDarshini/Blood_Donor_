import pytest
from app.models import User, DonorProfile


def test_register_donor_success(client):
    payload = {
        "full_name": "Test Donor",
        "email": "test.donor@example.com",
        "password": "Password123!",
        "phone": "+1234567890",
        "role": "donor",
        "blood_group": "A+",
        "city": "Austin",
        "state": "TX"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "donor"
    assert data["email"] == "test.donor@example.com"


def test_prevent_public_admin_registration(client):
    payload = {
        "full_name": "Hacker Admin",
        "email": "hacker@example.com",
        "password": "Password123!",
        "role": "admin"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 403


def test_prevent_duplicate_email(client):
    payload = {
        "full_name": "User 1",
        "email": "duplicate@example.com",
        "password": "Password123!",
        "role": "patient"
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_login_invalid_password(client):
    payload = {
        "full_name": "Login User",
        "email": "login.test@example.com",
        "password": "CorrectPassword123",
        "role": "patient"
    }
    client.post("/api/auth/register", json=payload)

    login_fail = client.post("/api/auth/login", json={
        "email": "login.test@example.com",
        "password": "WrongPassword"
    })
    assert login_fail.status_code == 401

    login_success = client.post("/api/auth/login", json={
        "email": "login.test@example.com",
        "password": "CorrectPassword123"
    })
    assert login_success.status_code == 200
    assert "access_token" in login_success.json()


def test_role_based_access_control(client):
    # Register as donor
    client.post("/api/auth/register", json={
        "full_name": "Normal Donor",
        "email": "normal.donor@example.com",
        "password": "Password123!",
        "role": "donor",
        "blood_group": "O+"
    })
    login_res = client.post("/api/auth/login", json={
        "email": "normal.donor@example.com",
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Donor trying to access admin dashboard
    admin_res = client.get("/api/admin/dashboard", headers=headers)
    assert admin_res.status_code == 403


def test_send_and_verify_phone_otp(client, db_session):
    phone = "+919876543210"
    
    # 1. Send OTP
    send_res = client.post("/api/auth/send-otp", json={"phone": phone})
    assert send_res.status_code == 200
    data = send_res.json()
    assert data["success"] is True
    assert "Verification SMS sent" in data["message"]
    
    # Find OTP from DB
    from app.models import PhoneVerification
    record = db_session.query(PhoneVerification).filter(PhoneVerification.phone == phone).first()
    assert record is not None
    assert record.is_verified is False
    otp_code = record.otp_code

    # 2. Try invalid OTP
    bad_verify = client.post("/api/auth/verify-otp", json={"phone": phone, "otp_code": "000000"})
    assert bad_verify.status_code == 400
    assert "Invalid verification code" in bad_verify.json()["detail"]

    # 3. Verify with correct OTP
    good_verify = client.post("/api/auth/verify-otp", json={"phone": phone, "otp_code": otp_code})
    assert good_verify.status_code == 200
    assert good_verify.json()["success"] is True

    # 4. Check DB status
    db_session.refresh(record)
    assert record.is_verified is True


def test_registration_with_verified_phone(client, db_session):
    phone = "+919999988888"
    
    # Send and verify OTP
    send_res = client.post("/api/auth/send-otp", json={"phone": phone})
    assert send_res.status_code == 200

    from app.models import PhoneVerification
    record = db_session.query(PhoneVerification).filter(PhoneVerification.phone == phone).order_by(PhoneVerification.created_at.desc()).first()
    verify_res = client.post("/api/auth/verify-otp", json={"phone": phone, "otp_code": record.otp_code})
    assert verify_res.status_code == 200

    # Register user with verified phone
    reg_payload = {
        "full_name": "Verified Donor",
        "email": "verified.donor@example.com",
        "password": "Password123!",
        "phone": phone,
        "role": "donor",
        "blood_group": "B+",
        "city": "Chennai",
        "state": "TN"
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    
    # Verify user's phone status in DB
    user = db_session.query(User).filter(User.email == "verified.donor@example.com").first()
    assert user is not None
    assert user.is_phone_verified is True

