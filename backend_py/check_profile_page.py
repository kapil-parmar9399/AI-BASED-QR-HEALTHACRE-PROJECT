import requests
from http.cookiejar import CookieJar

session = requests.Session()

# First, register a test user
print("Step 1: Registering user...")
register_data = {
    "username": "testprofilecheck",
    "name": "Test User",
    "password": "Test@123",
    "role": "patient"
}

resp = session.post(f'{BASE_URL}/register', data=register_data)
print(f"Register status: {resp.status_code}")

# Now login
print("\nStep 2: Logging in...")
login_data = {
    "username": "testprofilecheck",
    "password": "Test@123"
}

resp = session.post(f'{BASE_URL}/login', data=login_data)
print(f"Login status: {resp.status_code}")

# Now get the edit profile page
print("\nStep 3: Getting edit profile page...")
resp = session.get(f'{BASE_URL}/patient/edit-profile')
print(f"Edit profile status: {resp.status_code}")
print(f"Response length: {len(resp.text)}")

# Check what's in the response
if "Edit Personal Information" in resp.text:
    print("✓ Found 'Edit Personal Information' heading")
else:
    print("✗ Missing 'Edit Personal Information' heading")
    
if "Medical Information" in resp.text:
    print("✓ Found 'Medical Information' heading")
else:
    print("✗ Missing 'Medical Information' heading")

if "personal_info_form" in resp.text or "name=" in resp.text:
    print("✓ Found form with name field")
else:
    print("✗ Form or name field not found")

# Look for specific input fields
inputs_to_check = ["Full Name", "Email", "Age", "Contact", "Blood Group", "Medical History"]
for input_label in inputs_to_check:
    if input_label in resp.text:
        print(f"✓ Found: {input_label}")
    else:
        print(f"✗ Not found: {input_label}")
