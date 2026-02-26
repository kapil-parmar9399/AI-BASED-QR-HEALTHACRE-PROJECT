import requests
import time

time.sleep(2)

# Test register page
resp = requests.get('http://127.0.0.1:3001/register')
print(f'Register page: {resp.status_code}')

# Check for new fields
if 'name' in resp.text and 'id="name"' in resp.text:
    print('✓ Name field found')
else:
    print('✗ Name field NOT found')

if 'role' in resp.text and 'id="role"' in resp.text:
    print('✓ Role dropdown found')
else:
    print('✗ Role dropdown NOT found')

# Test login page
resp = requests.get('http://127.0.0.1:3001/login')
print(f'Login page: {resp.status_code}')

# Test home page
resp = requests.get('http://127.0.0.1:3001/')
if 'QR Code' in resp.text:
    print('✓ Home page has QR Code feature')
if 'AI Health' in resp.text:
    print('✓ Home page has AI Health feature')
if 'Emergency' in resp.text:
    print('✓ Home page has Emergency feature')
