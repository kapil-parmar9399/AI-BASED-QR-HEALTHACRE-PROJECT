import requests, re
s=requests.Session()
# register and login
try:
    s.post('http://127.0.0.1:3001/register', data={'username':'qrtestuser4','name':'QR Test','password':'Test@123','role':'patient'})
except Exception:
    pass
s.post('http://127.0.0.1:3001/login', data={'username':'qrtestuser4','password':'Test@123'})
r=s.get('http://127.0.0.1:3001/patient/qrcode')
print('status', r.status_code)
m=re.search(r"data:image/png;base64,[A-Za-z0-9+/=]+", r.text)
print('qr image exists', bool(m))
m2=re.search(r'(/p/[0-9a-fA-F]{24})', r.text)
print('public link found:', bool(m2))
if m2:
    print('path:', m2.group(1))
