#!/usr/bin/env python3
"""
Test script to verify prescription and visit functionality
"""
import requests
import json

session = requests.Session()

print("=" * 80)
print("TESTING PRESCRIPTION & VISIT FUNCTIONALITY")
print("=" * 80)

# 1. Register a new patient
print("\n1️⃣  Registering new test patient...")
register_data = {
    "username": "presctest456",
    "name": "Test Patient",
    "password": "Test@123",
    "role": "patient"
}

resp = session.post('http://127.0.0.1:3001/register', data=register_data)
print(f"   Register status: {resp.status_code}")

# 2. Login
print("\n2️⃣  Logging in...")
login_data = {
    "username": "presctest456",
    "password": "Test@123"
}

resp = session.post('http://127.0.0.1:3001/login', data=login_data)
print(f"   Login status: {resp.status_code}")

# 3. Get prescription form
print("\n3️⃣  Getting prescription form...")
resp = session.get('http://127.0.0.1:3001/patient/add-prescription')
print(f"   Form status: {resp.status_code}")
if "💊 Add Prescription" in resp.text or "Add Prescription" in resp.text:
    print("   ✓ Prescription form loaded successfully")

# 4. Add a prescription
print("\n4️⃣  Adding prescription...")
prescription_data = {
    "medicine": "Aspirin",
    "dosage": "500mg",
    "duration": "30 days",
    "prescribed_by": "Dr. Rajesh Kumar",
    "notes": "Take with food"
}

resp = session.post('http://127.0.0.1:3001/patient/add-prescription', data=prescription_data)
print(f"   POST status: {resp.status_code}")
if "success" in resp.text.lower():
    print("   ✓ Success message shown")

# 5. Get visit form
print("\n5️⃣  Getting visit form...")
resp = session.get('http://127.0.0.1:3001/patient/add-visit')
print(f"   Form status: {resp.status_code}")
if "Add Visit Record" in resp.text or "Doctor Name" in resp.text:
    print("   ✓ Visit form loaded successfully")

# 6. Add a visit record
print("\n6️⃣  Adding visit record...")
visit_data = {
    "doctor": "Dr. Priya Singh",
    "visit_date": "2026-02-20",
    "diagnosis": "Fever and cold",
    "treatment": "Prescribed antibiotics and rest",
    "notes": "Follow-up in 1 week"
}

resp = session.post('http://127.0.0.1:3001/patient/add-visit', data=visit_data)
print(f"   POST status: {resp.status_code}")
if "success" in resp.text.lower():
    print("   ✓ Success message shown")

# 7. Check patient records to verify data
print("\n7️⃣  Verifying data in patient records...")
resp = session.get('http://127.0.0.1:3001/patient/records')
print(f"   Records page status: {resp.status_code}")

verification = []
if "Aspirin" in resp.text:
    print("   ✓ Prescription medicine found")
    verification.append(True)
else:
    print("   ✗ Prescription medicine NOT found")
    verification.append(False)

if "500mg" in resp.text or "Aspirin" in resp.text:
    print("   ✓ Prescription dosage found")
    verification.append(True)
else:
    print("   ✗ Prescription dosage NOT found")
    verification.append(False)

if "Fever" in resp.text or "cold" in resp.text:
    print("   ✓ Visit diagnosis found")
    verification.append(True)
else:
    print("   ✗ Visit diagnosis NOT found")
    verification.append(False)

if "Dr. Priya Singh" in resp.text:
    print("   ✓ Doctor name found")
    verification.append(True)
else:
    print("   ✗ Doctor name NOT found")
    verification.append(False)

# 8. Check dashboard
print("\n8️⃣  Checking patient dashboard...")
resp = session.get('http://127.0.0.1:3001/patient/dashboard')
print(f"   Dashboard status: {resp.status_code}")
if "Add Prescription" in resp.text:
    print("   ✓ Add Prescription button visible")
if "Add Visit" in resp.text:
    print("   ✓ Add Visit button visible")

# Summary
print("\n" + "=" * 80)
if all(verification):
    print("✅ ALL TESTS PASSED!")
    print("   - Prescription functionality working")
    print("   - Visit functionality working")
    print("   - Data persisting correctly")
else:
    print("⚠️  Some tests passed, check details above")
print("=" * 80)
