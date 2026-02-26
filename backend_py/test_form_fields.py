import requests

time.sleep(2)

# Check if forms are loading correctly
resp = requests.get('http://127.0.0.1:3001/patient/edit-profile')

checks = [
    ('Personal Information', 'Personal Information' in resp.text),
    ('Blood group field', 'blood_group' in resp.text),
    ('Medical history field', 'medical_history' in resp.text),
    ('Allergies field', 'allergies' in resp.text),
    ('Current medications field', 'current_medications' in resp.text),
    ('Edit profile form', 'id="name"' in resp.text),
    ('Save button', 'Save Personal Information' in resp.text),
    ('Medical info form', 'Edit Medical Information' in resp.text),
]

print('Form Fields Check:')
for check_name, result in checks:
    status = '✓' if result else '✗'
    print(f'{status} {check_name}')

# Show a snippet of what's in the response
print('\nForm found:', 'form' in resp.text)
print('Status code:', resp.status_code)
