import pytest
from datetime import date
from app.models import User
from app.security.auth import get_password_hash


def test_donation_verification_and_reward_minting(client, db_session):
    # 1. Create an admin user directly
    admin = User(
        full_name="Admin Boss",
        email="admin.boss@example.com",
        password_hash=get_password_hash("AdminPass123!"),
        role="admin",
        account_status="active"
    )
    db_session.add(admin)
    db_session.commit()

    admin_login = client.post("/api/auth/login", json={
        "email": "admin.boss@example.com",
        "password": "AdminPass123!"
    })
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Register Donor
    donor_res = client.post("/api/auth/register", json={
        "full_name": "Generous Donor",
        "email": "generous.donor@example.com",
        "password": "Password123!",
        "role": "donor",
        "blood_group": "B+"
    })
    donor_token = donor_res.json()["access_token"]
    donor_headers = {"Authorization": f"Bearer {donor_token}"}

    # 3. Donor submits donation record
    donation_payload = {
        "donation_date": str(date.today()),
        "hospital_name": "City Health Hospital",
        "units_donated": 1,
        "notes": "Regular blood drive"
    }
    submit_res = client.post("/api/donations", json=donation_payload, headers=donor_headers)
    assert submit_res.status_code == 201
    donation_id = submit_res.json()["id"]
    assert submit_res.json()["donation_status"] == "completed_pending_verification"
    assert submit_res.json()["points_awarded"] is None

    # Verify donor points are still 0
    rewards_before = client.get("/api/rewards/me", headers=donor_headers)
    assert rewards_before.json()["total_points"] == 0

    # 4. Admin verifies the donation
    verify_res = client.patch(
        f"/api/admin/donations/{donation_id}/verify",
        json={"action": "verify", "points_override": 100},
        headers=admin_headers
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["donation_status"] == "verified"
    assert verify_res.json()["points_awarded"] == 100

    # 5. Check donor points are now 100 with milestone and badge
    rewards_after = client.get("/api/rewards/me", headers=donor_headers)
    assert rewards_after.status_code == 200
    rewards_data = rewards_after.json()
    assert rewards_data["total_points"] == 100
    assert rewards_data["total_verified_donations"] == 1
    assert len(rewards_data["badges"]) >= 1

    # 6. Admin attempts duplicate verification on same donation -> points must NOT duplicate
    client.patch(
        f"/api/admin/donations/{donation_id}/verify",
        json={"action": "verify"},
        headers=admin_headers
    )
    rewards_duplicate_check = client.get("/api/rewards/me", headers=donor_headers)
    assert rewards_duplicate_check.json()["total_points"] == 100  # Stays 100!
