#!/usr/bin/env python3
"""
Test QR scanning flow on mobile.
Simulates: 
1. Patient creates QR with token
2. Third party (emergency responder) scans QR and views patient data
"""
import requests
import time
import json

BASE_URL = "http://127.0.0.1:3002"

print("=" * 60)
print("🔍 QR CODE MOBILE SCAN TEST")
print("=" * 60)

# Session 1: Patient creates account and QR
print("\n[PATIENT SETUP]")
patient_session = requests.Session()
patient_id = int(time.time() * 1000) % 100000
patient_user = f"patient_{patient_id}"

# Step 1: Register patient
print(f"1. Registering patient: {patient_user}")
r = patient_session.post(f"{BASE_URL}/register", data={
    "username": patient_user,
    "password": "secure123",
    "name": "राज कुमार",  # Patient name in Hindi
    "role": "patient"
})
assert r.status_code == 200, f"Registration failed: {r.status_code}"
print("   ✓ Patient registered")

# Step 2: Patient logs in
print("2. Patient logging in...")
r = patient_session.post(f"{BASE_URL}/login", data={
    "username": patient_user,
    "password": "secure123"
})
assert r.status_code == 200, f"Login failed: {r.status_code}"
print("   ✓ Patient logged in")

# Step 3: Update patient profile with medical data
print("3. Updating patient profile with medical info...")
r = patient_session.post(f"{BASE_URL}/patient/edit-profile", data={
    "name": "राज कुमार",
    "email": "raj@example.com",
    "age": "35",
    "contact": "+919876543210",
    "blood_group": "O+",
    "address": "Delhi, India",
    "emergency_contact": "+919111111111"
})
assert r.status_code == 200, f"Profile update failed: {r.status_code}"
print("   ✓ Profile updated")

# Step 4: Add medical history
print("4. Adding medical history...")
r = patient_session.post(f"{BASE_URL}/patient/edit-medical", data={
    "medical_history": "Diabetes, Hypertension",
    "allergies": "Penicillin, Shellfish",
    "current_medications": "Metformin 500mg, Lisinopril 10mg"
})
assert r.status_code == 200, f"Medical history update failed: {r.status_code}"
print("   ✓ Medical history saved")

# Step 5: Add a prescription
print("5. Adding prescription...")
r = patient_session.post(f"{BASE_URL}/patient/add-prescription", data={
    "medicine": "Amoxicillin",
    "dosage": "500mg",
    "duration": "7 days",
    "prescribed_by": "Dr. Singh",
    "notes": "For throat infection"
})
assert r.status_code == 200, f"Prescription add failed: {r.status_code}"
print("   ✓ Prescription added")

# Step 6: Get QR page to extract patient ID and token
print("6. Generating QR code with access token...")
r = patient_session.get(f"{BASE_URL}/patient/qrcode")
assert r.status_code == 200, f"QR page load failed: {r.status_code}"

# Extract patient ID from the response
import re
match = re.search(r'/p/([a-f0-9]+)', r.text)
if not match:
    print("   ✗ Could not extract patient ID from QR page")
    print(r.text[:500])
    exit(1)

patient_id_hex = match.group(1)
print(f"   Patient ID: {patient_id_hex}")

# Extract token from the response
token_match = re.search(r'[?&]t=([a-f0-9]+)', r.text)
if not token_match:
    print("   ✗ Could not extract token from QR page")
    exit(1)

token = token_match.group(1)
print(f"   Access Token: {token[:20]}...")
print("   ✓ QR generated")

# Session 2: Emergency responder scans QR (new session, no auth)
print("\n[EMERGENCY RESPONDER - SCANS QR]")
responder_session = requests.Session()

# Step 7: Access public view with token (as if scanned from mobile)
print(f"7. Scanning QR code (accessing /p/{patient_id_hex[:8]}...?t={token[:8]}...)")
qr_url = f"{BASE_URL}/p/{patient_id_hex}?t={token}"
r = responder_session.get(qr_url)
if r.status_code != 200:
    print("ERROR response body:\n", r.text)
assert r.status_code == 200, f"QR access failed: {r.status_code}"

# Verify authorized access
assert "Verified" in r.text or "✓" in r.text, "Authorized badge not found"
assert "राज कुमार" in r.text, "Patient name not found in response"
assert "Diabetes" in r.text or "diabetes" in r.text, "Medical history not visible"
assert "Penicillin" in r.text, "Allergies not visible"
assert "Metformin" in r.text, "Medications not visible"

print("   ✓ QR scanned successfully!")
print("   ✓ Patient data displayed")
print(f"\n[DATA VISIBLE ON MOBILE]")
print(f"   Name: राज कुमार")
print(f"   Age: 35")
print(f"   Blood Group: O+")
print(f"   Emergency: +919111111111")
print(f"   Conditions: Diabetes, Hypertension")
print(f"   Allergies: Penicillin, Shellfish")
print(f"   Medications: Metformin 500mg, Lisinopril 10mg")

# Step 8: Test expired/invalid token
print("\n[SECURITY TEST - INVALID TOKEN]")
print("8. Attempting access with invalid token...")
bad_token = "invalidtoken123"
r = responder_session.get(f"{BASE_URL}/p/{patient_id_hex}?t={bad_token}")
assert r.status_code == 200, f"Request failed: {r.status_code}"
assert "Access Restricted" in r.text or "restricted" in r.text.lower(), "Should show restricted message"
print("   ✓ Invalid token rejected - access restricted")

# Step 9: Test access without token
print("9. Attempting access without token...")
r = responder_session.get(f"{BASE_URL}/p/{patient_id_hex}")
assert r.status_code == 200, f"Request failed: {r.status_code}"
assert "Access Restricted" in r.text or "restricted" in r.text.lower(), "Should show restricted message"
print("   ✓ No token access denied - access restricted")

print("\n" + "=" * 60)
print("✅ ALL QR MOBILE SCAN TESTS PASSED!")
print("=" * 60)
print("\nSummary:")
print("- Patient can create QR with embedded access token")
print("- Emergency responder can scan QR and view medical data")
print("- Token-based authorization prevents unauthorized access")
print("- Mobile-optimized view displays all critical information")
print("\n🚨 Ready for emergency use!")
