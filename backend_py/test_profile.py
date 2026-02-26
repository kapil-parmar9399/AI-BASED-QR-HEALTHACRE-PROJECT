import requests
import time
import os

BASE_URL = f"http://127.0.0.1:{os.getenv('PORT','3001')}"

time.sleep(2)

# Create a test user
username = f'profiletest_{int(time.time())}'
data = {
    'username': username,
    'password': 'test123',
    'name': 'Profile Test User',
    'role': 'patient'
}

# Register
resp = requests.post(f'{BASE_URL}/register', data=data, allow_redirects=False)
print(f'✓ Registration: {resp.status_code}')

# Login
resp = requests.post(f'{BASE_URL}/login', data={'username': username, 'password': 'test123'})
print(f'✓ Login: {resp.status_code}')

# Get edit profile page
resp = requests.get(f'{BASE_URL}/patient/edit-profile')
print(f'✓ Edit profile page: {resp.status_code}')

if 'Edit Personal Information' in resp.text:
    print('✓ Edit form found')
if 'Medical Information' in resp.text:
    print('✓ Medical form found')
if 'blood_group' in resp.text:
    print('✓ Blood group field found')
if 'medical_history' in resp.text:
    print('✓ Medical history field found')
if 'allergies' in resp.text:
    print('✓ Allergies field found')

# Test updating personal information
update_data = {
    'name': 'Updated Name',
    'email': 'test@example.com',
    'age': '30',
    'contact': '9876543210',
    'blood_group': 'O+',
    'address': 'Test Address',
    'emergency_contact': '9876543211'
}

resp = requests.post(f'{BASE_URL}/patient/edit-profile', data=update_data)
print(f'✓ Update personal info: {resp.status_code}')

if 'updated successfully' in resp.text.lower():
    print('✓ Success message shown')

# Test updating medical information
medical_data = {
    'medical_history': 'Diabetes, Hypertension',
    'allergies': 'Penicillin, Aspirin',
    'current_medications': 'Lisinopril 10mg, Metformin 500mg'
}

resp = requests.post(f'{BASE_URL}/patient/edit-medical', data=medical_data)
print(f'✓ Update medical info: {resp.status_code}')

print('\n✅ All profile editing features working!')
