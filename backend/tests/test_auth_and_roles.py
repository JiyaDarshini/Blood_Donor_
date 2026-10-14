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
