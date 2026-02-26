import requests
import time
import os

# base URL picks up PORT env var so scripts stay in sync with server config
BASE_URL = f"http://127.0.0.1:{os.getenv('PORT','3001')}"

time.sleep(2)

# Test registration
username = f'testuser_{int(time.time())}'
data = {
    'username': username,
    'password': 'testpass123',
    'name': 'Test User',
    'role': 'patient'
}

resp = requests.post(f'{BASE_URL}/register', data=data, allow_redirects=False)
print(f'Register POST: {resp.status_code}')

if resp.status_code == 303:
    print('✓ Registration successful (redirected to home)')
    print(f'  Created user: {username}')
elif resp.status_code == 200:
    if 'error' in resp.text.lower():
        print('✗ Registration failed - error displayed')
    else:
        print('✓ Registration form returned (might need to redirect)')
else:
    print(f'? Unexpected status: {resp.status_code}')

# Test login with newly created user
resp = requests.post('http://127.0.0.1:3001/login', data={'username': username, 'password': 'testpass123'}, allow_redirects=False)
print(f'Login POST: {resp.status_code}')

if resp.status_code == 303:
    print('✓ Login successful')
else:
    print(f'✗ Login failed: {resp.status_code}')
