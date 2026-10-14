import pytest


def test_sos_request_creation_and_donor_invitation(client):
    # 1. Register Donor with O- blood group (Universal Donor) in Austin
    res_donor = client.post("/api/auth/register", json={
        "full_name": "Universal Donor O-",
        "email": "donor.ominus@example.com",
        "password": "Password123!",
        "role": "donor",
        "blood_group": "O-",
        "city": "Austin",
        "state": "TX",
        "latitude": 30.2672,
        "longitude": -97.7431
    })
    assert res_donor.status_code == 201

    # 2. Register Patient
    res_patient = client.post("/api/auth/register", json={
        "full_name": "Emergency Patient",
        "email": "emergency.patient@example.com",
        "password": "Password123!",
        "role": "patient",
        "city": "Austin",
        "state": "TX"
    })
    assert res_patient.status_code == 201
    patient_token = res_patient.json()["access_token"]
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    # 3. Patient posts Critical Emergency SOS Request for A+ blood
    req_payload = {
        "blood_group": "A+",
        "units_required": 2,
        "urgency": "critical",
        "hospital_name": "Austin General Hospital",
        "hospital_address": "100 Medical Pkwy",
        "city": "Austin",
        "state": "TX",
        "latitude": 30.2700,
        "longitude": -97.7400,
        "description": "Critical emergency transfusion needed."
    }
    create_res = client.post("/api/requests", json=req_payload, headers=patient_headers)
    assert create_res.status_code == 201
    req_data = create_res.json()
    req_id = req_data["id"]
    assert req_data["status"] == "searching"
    assert req_data["matched_donors_count"] >= 1  # O- donor is compatible with A+ recipient

    # 4. Donor logs in and views their invitations
    donor_token = res_donor.json()["access_token"]
    donor_headers = {"Authorization": f"Bearer {donor_token}"}

    inv_res = client.get("/api/invitations/me", headers=donor_headers)
    assert inv_res.status_code == 200
    invitations = inv_res.json()
    assert len(invitations) >= 1
    target_inv = next(i for i in invitations if i["blood_request_id"] == req_id)
    assert target_inv["status"] == "pending"

    # 5. Donor accepts invitation
    respond_res = client.post(
        f"/api/invitations/{target_inv['id']}/respond",
        json={"response": "accepted"},
        headers=donor_headers
    )
    assert respond_res.status_code == 200
    assert respond_res.json()["status"] == "accepted"

    # 6. Check request status updated to responses_received
    req_check = client.get(f"/api/requests/{req_id}", headers=patient_headers)
    assert req_check.status_code == 200
    assert req_check.json()["status"] == "responses_received"
    assert req_check.json()["accepted_donors_count"] == 1

    # 7. Patient cancels request
    cancel_res = client.post(f"/api/requests/{req_id}/cancel", headers=patient_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"
