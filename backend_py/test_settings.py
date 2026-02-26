#!/usr/bin/env python3
"""Test patient settings flow"""
import requests
import time
import random

BASE_URL = "http://127.0.0.1:3002"

session = requests.Session()

# Use a unique username to avoid conflicts
unique_id = int(time.time() * 1000) % 100000
username = f"patient{unique_id}"

# Test 1: Register a patient with all required fields
print("=== Test 1: Register ===")
r = session.post(f"{BASE_URL}/register", data={
    "username": username,
    "password": "pass123",
    "name": "Test Patient",
    "role": "patient"
})
print(f"Register: {r.status_code}")

# Test 2: Login
print("\n=== Test 2: Login ===")
r = session.post(f"{BASE_URL}/login", data={"username": username, "password": "pass123"})
print(f"Login: {r.status_code}")

# Test 3: Access settings page (GET)
print("\n=== Test 3: Access Settings Page ===")
r = session.get(f"{BASE_URL}/patient/settings")
print(f"Settings GET: {r.status_code}")
if r.status_code == 200:
    has_form = '<form' in r.text
    has_email = 'email' in r.text.lower() and 'input' in r.text
    has_phone = 'contact' in r.text
    print(f"Contains form: {has_form}")
    print(f"Contains email field: {has_email}")
    print(f"Contains phone field: {has_phone}")

# Test 4: Save settings
print("\n=== Test 4: Save Settings ===")
r = session.post(f"{BASE_URL}/patient/settings", data={
    "email": "test@example.com",
    "contact": "+1234567890",
    "action": "save"
})
print(f"Settings POST: {r.status_code}")

# Test 5: Verify settings were saved (GET again)
print("\n=== Test 5: Verify Settings Saved ===")
r = session.get(f"{BASE_URL}/patient/settings")
print(f"Get settings after save: {r.status_code}")
if "test@example.com" in r.text:
    print("✓ Email is populated")
else:
    print("✗ Email not found in response (but POST may have worked)")

print("\n✓ All settings page tests completed!")

