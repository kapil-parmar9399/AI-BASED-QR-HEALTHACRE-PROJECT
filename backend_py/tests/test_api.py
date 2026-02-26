import os
import pytest
from fastapi.testclient import TestClient

from main import app
from config import config

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data


def test_registration_and_login():
    # use unique username to avoid collisions
    username = f"pytestuser_{int(os.times()[4] * 1000)}"
    payload = {
        "username": username,
        "password": "testpass123",
        "name": "PyTest User",
        "role": "patient",
    }
    resp = client.post("/register", data=payload, allow_redirects=False)
    assert resp.status_code in (200, 303)

    # attempt login
    resp2 = client.post("/login", data={"username": username, "password": "testpass123"}, allow_redirects=False)
    assert resp2.status_code in (200, 303)


def test_admin_protected_routes():
    # unauthenticated request should be 403
    r = client.get("/api/config/info")
    assert r.status_code == 403

    # login as admin (assuming an admin user exists or create one manually)
    # for the sake of the test, try to register admin if not exist
    admin_username = os.getenv("TEST_ADMIN_USER", "admin")
    admin_password = os.getenv("TEST_ADMIN_PASS", "adminpass")
    client.post("/register", data={
        "username": admin_username,
        "password": admin_password,
        "name": "Administrator",
        "role": "admin",
    })
    login_resp = client.post("/login", data={"username": admin_username, "password": admin_password}, allow_redirects=False)
    assert login_resp.status_code in (200, 303)
    
    # now access config info should succeed
    r2 = client.get("/api/config/info")
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("app_name")


def test_admin_stats_endpoint():
    """The API should expose a non‑conflicting stats endpoint for the dashboard"""
    # ensure we're logged in as admin first
    admin_username = os.getenv("TEST_ADMIN_USER", "admin")
    admin_password = os.getenv("TEST_ADMIN_PASS", "adminpass")
    client.post("/login", data={"username": admin_username, "password": admin_password}, allow_redirects=False)

    r = client.get("/admin/stats")
    assert r.status_code == 200
    stats = r.json()
    # basic sanity checks on returned keys
    assert "total_users" in stats
    assert "total_patients" in stats
    assert isinstance(stats.get("total_doctors"), int)


def test_doctor_registration_and_approval():
    # register a new doctor user
    doc_username = f"doc_{int(os.times()[4] * 1000)}"
    payload = {
        "username": doc_username,
        "password": "docpass123",
        "name": "Dr. Test",
        "role": "doctor",
    }
    resp = client.post("/register", data=payload, allow_redirects=False)
    assert resp.status_code in (200, 303)

    # the public doctors page should NOT list the new doctor yet
    public = client.get("/doctors")
    assert "Dr. Test" not in public.text

    # login as admin to approve
    admin_username = os.getenv("TEST_ADMIN_USER", "admin")
    admin_password = os.getenv("TEST_ADMIN_PASS", "adminpass")
    client.post("/login", data={"username": admin_username, "password": admin_password}, allow_redirects=False)
    pending = client.get("/admin/doctors")
    assert pending.status_code == 200
    assert "Dr. Test" in pending.text
    # approve via POST form
    # extract the hidden id (crudely by searching pattern)
    import re
    m = re.search(r'name="doctor_id" value="([0-9a-fA-F]+)"', pending.text)
    if m:
        doc_id = m.group(1)
        client.post("/admin/doctors/approve", data={"doctor_id": doc_id})
    else:
        pytest.skip("couldn't find doctor id in admin page")

    # after approval, public listing should show doctor
    pub2 = client.get("/doctors")
    assert "Dr. Test" in pub2.text

    # API endpoint should also list approved doctors
    api_resp = client.get("/api/doctors")
    assert api_resp.status_code == 200
    dlist = api_resp.json()
    assert any(d.get("name") == "Dr. Test" for d in dlist)

    # as a doctor, dashboard should list the approved doctor names
    # login as doctor user we just created
    client.post("/login", data={"username": doc_username, "password": "docpass123"}, allow_redirects=False)
    dash = client.get("/doctor/dashboard")
    assert dash.status_code == 200
    assert "Doctor Directory" in dash.text
    assert "Dr. Test" in dash.text
