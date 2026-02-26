import requests
import os

BASE_URL = f"http://127.0.0.1:{os.getenv('PORT','3001')}"

resp = requests.get(f"{BASE_URL}/patient/edit-profile")

# Check what's actually in the response
print("Response length:", len(resp.text))
print("\nChecking for key elements:")

key_elements = [
    "Edit Personal Information",
    "Medical Information",
    "<form",
    "name=",
    "input type",
    "form method",
    "POST",
]

for element in key_elements:
    if element in resp.text:
        print(f"✓ Found: {element}")
    else:
        print(f"✗ Not found: {element}")

# Print first 500 chars of body
if "<body" in resp.text:
    start = resp.text.find("<body")
    snippet = resp.text[start:start+1000]
    print("\nHTML Snippet:")
    print(snippet)
