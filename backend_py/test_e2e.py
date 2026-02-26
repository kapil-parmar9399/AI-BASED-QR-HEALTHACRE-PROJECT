import requests
import uuid
import os

BASE = "http://127.0.0.1:3001"
s = requests.Session()

# Generate unique username
user = f"testuser_{uuid.uuid4().hex[:6]}"
password = "testpass"

print('Registering', user)
r = s.post(f"{BASE}/register", data={"username": user, "password": password}, allow_redirects=True)
print('Register status', r.status_code)

print('Accessing home')
r = s.get(f"{BASE}/")
print('Home OK', r.status_code)

print('Adding patient')
r = s.post(f"{BASE}/patients/add", data={"name": "E2E Patient", "age": 42, "notes": "From test"}, allow_redirects=True)
print('Add patient status', r.status_code)

print('Listing patients (HTML)')
r = s.get(f"{BASE}/patients")
print('Patients page status', r.status_code)

# Try to parse first patient id from HTML by searching for value="..."
import re
m = re.search(r'value="([0-9a-f]{24})"', r.text)
if m:
    pid = m.group(1)
    print('Found patient id', pid)
    # create a small file
    fname = os.path.join(os.path.dirname(__file__), 'e2e_sample.txt')
    with open(fname, 'w') as f:
        f.write('sample file content')
    files = {'file': open(fname, 'rb')}
    data = {'patient_id': pid}
    print('Uploading file')
    r = s.post(f"{BASE}/patients/upload", data=data, files=files, allow_redirects=True)
    print('Upload status', r.status_code)
    files["file"].close()
else:
    print('No patient id found in patients HTML; upload skipped')

print('Done')
