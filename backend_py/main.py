import os
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
import smtplib
from email.message import EmailMessage
import requests as _requests
from urllib.parse import urlencode
import shutil
import uuid
from datetime import datetime
import qrcode
import io
import base64
import numpy as np
from slowapi import Limiter
from slowapi.util import get_remote_address

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import configuration and security modules
from config import config
from security import (
    password_manager,
    token_manager,
    audit_log,
    input_validator,
    SecurityHeaders,
)
from backup import DatabaseBackup

# admin routes router
from admin_routes import get_admin_router

# Logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# optional ngrok for public tunneling
ngrok_tunnel_url = None
try:
    from pyngrok import ngrok
except Exception:
    ngrok = None
try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None


BASE_DIR = os.path.dirname(__file__)

# FastAPI app with enhanced documentation
app = FastAPI(
    title="Swasthya - AI QR Healthcare System",
    description="Secure healthcare platform with QR-based emergency access, role-based dashboards, and patient record management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# CORS middleware (from config)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Sessions (simple cookie-based sessions)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    https_only=config.ENVIRONMENT == "production",
    same_site="lax",
)

# Static + templates
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")
if not os.path.isdir(static_dir):
    os.makedirs(static_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Add strftime filter to Jinja2 for datetime formatting in templates
def strftime_filter(dt, fmt):
    """Jinja2 filter for datetime formatting"""
    if isinstance(dt, str):
        try:
            from datetime import datetime as dt_class
            dt = dt_class.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    return dt.strftime(fmt) if hasattr(dt, 'strftime') else str(dt)

templates.env.filters['strftime'] = strftime_filter
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# MongoDB setup
MONGO_URL = config.MONGODB_URI
DATABASE_NAME = config.DATABASE_NAME
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
try:
    db = client[DATABASE_NAME]
    client.admin.command('ping')
    logger.info(f"✅ Connected to MongoDB: {DATABASE_NAME}")
except Exception as e:
    db = None
    logger.error(f"❌ Could not connect to MongoDB: {e}")

# Database backup instance
db_backup = DatabaseBackup() if db is not None else None


# Utility functions
def oid_to_str(doc: dict) -> dict:
    if not doc:
        return doc
    doc["id"] = str(doc.get("_id"))
    doc.pop("_id", None)
    return doc


def get_public_base_url(request: Request = None) -> str:
    """Return a base URL used for public links.
    Preference order:
      1. PUBLIC_URL env var
      2. ngrok tunnel (if NGROK_AUTHTOKEN env provided and pyngrok available)
      3. request.base_url (if request given)
    """
    global ngrok_tunnel_url
    # 1. explicit override
    url = os.getenv('PUBLIC_URL')
    if url:
        return url.rstrip('/')

    # 2. ngrok dynamic tunnel
    if ngrok and os.getenv('NGROK_AUTHTOKEN'):
        if not ngrok_tunnel_url:
            try:
                ngrok.set_auth_token(os.getenv('NGROK_AUTHTOKEN'))
                port = os.getenv('PORT', '3002')
                tunnel = ngrok.connect(addr=port, bind_tls=True)
                ngrok_tunnel_url = tunnel.public_url
                print(f"[ngrok] tunnel established at {ngrok_tunnel_url}")
            except Exception as e:
                print("[ngrok] unable to establish tunnel:", e)
        if ngrok_tunnel_url:
            return ngrok_tunnel_url.rstrip('/')

    # 3. derive from request if available
    if request is not None:
        try:
            base = str(request.base_url)
            return base.rstrip('/')
        except Exception:
            pass
    # fallback
    return ''


def generate_qr_code(data: str) -> str:
    """Generate QR code and return as base64 data URL"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


def require_admin(request: Request):
    """Raise HTTPException unless current session user is admin."""
    role = request.session.get('role')
    if role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

# include admin router after db is initialized
app.include_router(get_admin_router(db))


def analyze_health(patient_data: dict) -> dict:
    """Basic AI health analysis based on patient data"""
    analysis = {
        "age_risk": "Low",
        "pattern": "Stable",
        "recommendations": []
    }
    
    age = patient_data.get("age", 0)
    
    # Age-based risk assessment
    if age > 60:
        analysis["age_risk"] = "High"
        analysis["recommendations"].append("Regular cardiovascular checkup recommended")
    elif age > 45:
        analysis["age_risk"] = "Medium"
        analysis["recommendations"].append("Annual health checkup advised")
    
    # Visit frequency analysis
    visits = len(patient_data.get("visits", []))
    if visits > 5:
        analysis["pattern"] = "Frequent - Monitor closely"
        analysis["recommendations"].append("Consider specialist consultation")
    elif visits > 2:
        analysis["pattern"] = "Moderate - Normal"
    
    # Medical history analysis
    history = patient_data.get("medical_history", [])
    if history:
        analysis["recommendations"].append(f"Continuing treatment for {len(history)} condition(s)")
    
    if not analysis["recommendations"]:
        analysis["recommendations"].append("Maintain regular checkups")
    
    return analysis


def send_sms_via_twilio(to: str, body: str) -> bool:
    """Send SMS using Twilio SDK if configured."""
    sid = os.getenv('TWILIO_SID')
    auth = os.getenv('TWILIO_AUTH_TOKEN')
    from_num = os.getenv('TWILIO_FROM')
    if not (sid and auth and from_num):
        return False
    if TwilioClient is None:
        return False
    try:
        client = TwilioClient(sid, auth)
        client.messages.create(body=body, from_=from_num, to=to)
        return True
    except Exception:
        return False


def seed_db():
    if db is None:
        return
    
    # Seed users with roles
    if db.users.count_documents({}) == 0:
        pw_admin = password_manager.hash_password("admin")
        pw_doc = password_manager.hash_password("doctor")
        pw_pat = password_manager.hash_password("patient")
        
        db.users.insert_many([
            {"username": "admin", "password": pw_admin, "role": "admin", "name": "Admin User"},
            {"username": "doctor1", "password": pw_doc, "role": "doctor", "name": "Dr. Rajesh Kumar", "specialty": "General Medicine"},
            {"username": "doctor2", "password": pw_doc, "role": "doctor", "name": "Dr. Priya Singh", "specialty": "Cardiology"},
            {"username": "patient1", "password": pw_pat, "role": "patient", "name": "John Doe"},
        ])
    
    if db.doctors.count_documents({}) == 0:
        db.doctors.insert_many([
            {"name": "Dr. Rajesh Kumar", "specialty": "General Medicine", "experience": 15, "email": "rajesh@swasthya.com", "approved": True},
            {"name": "Dr. Priya Singh", "specialty": "Cardiology", "experience": 12, "email": "priya@swasthya.com", "approved": True},
            {"name": "Dr. Amit Patel", "specialty": "Pediatrics", "experience": 10, "email": "amit@swasthya.com", "approved": True},
        ])
    
    if db.patients.count_documents({}) == 0:
        db.patients.insert_many([
            {
                "name": "Raj Kumar",
                "age": 35,
                "contact": "9876543210",
                "email": "raj@example.com",
                "blood_group": "O+",
                "address": "Delhi",
                "medical_history": ["Hypertension"],
                "current_medications": ["Lisinopril"],
                "allergies": ["Penicillin"],
                "visits": [],
                "prescriptions": [],
                "reports": [],
                "emergency_contact": "9876543211"
            },
            {
                "name": "Aisha Khan",
                "age": 28,
                "contact": "9876543212",
                "email": "aisha@example.com",
                "blood_group": "B+",
                "address": "Mumbai",
                "medical_history": [],
                "current_medications": [],
                "allergies": [],
                "visits": [],
                "prescriptions": [],
                "reports": [],
                "emergency_contact": "9876543213"
            },
        ])
    
    if db.appointments.count_documents({}) == 0:
        db.appointments.insert_many([
            {
                "patient_name": "Raj Kumar",
                "doctor_name": "Dr. Rajesh Kumar",
                "date": "2026-02-28",
                "time": "10:00",
                "status": "scheduled",
                "notes": ""
            },
            {
                "patient_name": "Aisha Khan",
                "doctor_name": "Dr. Priya Singh",
                "date": "2026-03-05",
                "time": "14:30",
                "status": "scheduled",
                "notes": ""
            },
        ])


# Ensure uploads dir
uploads_dir = os.path.join(static_dir, "uploads")
os.makedirs(uploads_dir, exist_ok=True)


# --- Server-rendered routes ---
@app.on_event("startup")
def on_startup():
    seed_db()


@app.get("/")
def index(request: Request):
    user = request.session.get("user")
    user_role = request.session.get("role")
    return templates.TemplateResponse("home.html", {"request": request, "user": user, "role": user_role})


@app.get("/register")
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register_post(request: Request, username: str = Form(...), password: str = Form(...), 
                  name: str = Form(...), role: str = Form("patient")):
    if db is None:
        return templates.TemplateResponse("register.html", {"request": request, "error": "DB not available"})
    if db.users.find_one({"username": username}):
        return templates.TemplateResponse("register.html", {"request": request, "error": "User exists"})
    
    hashed = password_manager.hash_password(password)
    user_role = role if role in ["patient", "doctor", "admin"] else "patient"
    db.users.insert_one({
        "username": username,
        "password": hashed,
        "name": name,
        "role": user_role
    })
    # if doctor register, add to doctor collection with approval flag
    if user_role == "doctor":
        try:
            db.doctors.insert_one({
                "name": name,
                "approved": False,
                # additional fields can be added later via profile
            })
        except Exception:
            pass

    request.session["user"] = username
    request.session["role"] = user_role
    return RedirectResponse(url='/', status_code=303)


@app.get("/login")
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if db is None:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DB not available"})
    
    u = db.users.find_one({"username": username})
    if not u or not password_manager.verify_password(password, u["password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    request.session["user"] = username
    request.session["role"] = u.get("role", "patient")
    request.session["name"] = u.get("name", username)
    return RedirectResponse(url='/', status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/', status_code=303)


# ===== PATIENT ROUTES =====
@app.get("/patient/dashboard")
def patient_dashboard(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        patient = None
    else:
        patient = db.users.find_one({"username": user})
        patient = oid_to_str(patient) if patient else None
    
    return templates.TemplateResponse("patient_dashboard.html", {
        "request": request,
        "user": user,
        "role": role,
        "patient": patient
    })


@app.get("/patient/records")
def patient_records(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        patient = None
    else:
        patient = db.users.find_one({"username": user})
        patient = oid_to_str(patient) if patient else None
    
    return templates.TemplateResponse("patient_records.html", {
        "request": request,
        "user": user,
        "patient": patient
    })


@app.get("/patient/qrcode")
def patient_qrcode(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        patient = None
        qr_data = ""
    else:
        patient = db.users.find_one({"username": user})
        if patient:
            patient = oid_to_str(patient)
            # Generate a public URL that can be opened when QR is scanned
            # determine base URL for public link
            base = get_public_base_url(request)
            public_url = f"{base}/p/{patient.get('id')}"

            # Ensure a public token exists for this patient (create if missing)
            token = patient.get('public_token')
            token_created = patient.get('public_token_created')
            if not token:
                token = uuid.uuid4().hex
                token_created = datetime.utcnow().isoformat()
                try:
                    db.users.update_one({"_id": ObjectId(patient.get('id'))}, {"$set": {"public_token": token, "public_token_created": token_created}})
                except Exception:
                    pass

            # Append token as query param to public URL
            public_url_with_token = f"{public_url}?t={token}"
            qr_data = generate_qr_code(public_url_with_token)
            public_link = public_url_with_token
            # expose token creation time to template
            token_created_iso = token_created
        else:
            qr_data = ""
    
    return templates.TemplateResponse("patient_qrcode.html", {
        "request": request,
        "user": user,
        "patient": patient,
        "qr_data": qr_data,
        "public_link": public_link if 'public_link' in locals() else '',
        "token_created": token_created_iso if 'token_created_iso' in locals() else None
    })


@app.post('/patient/regenerate-token')
def regenerate_token(request: Request):
    user = request.session.get('user')
    role = request.session.get('role')
    if not user or role != 'patient':
        return RedirectResponse(url='/login', status_code=303)

    if db is None:
        return RedirectResponse(url='/patient/qrcode', status_code=303)

    try:
        # Create new token and save with timestamp
        token = uuid.uuid4().hex
        token_created = datetime.utcnow().isoformat()
        db.users.update_one({'username': user}, {'$set': {'public_token': token, 'public_token_created': token_created}})

        # Send email/sms if provided in profile
        profile = db.users.find_one({'username': user})
        email = profile.get('email') if profile else None
        phone = profile.get('contact') if profile else None

        # determine link base (PUBLIC_URL, ngrok, etc.)
        base = get_public_base_url(request)
        public_url = f"{base}/p/{profile.get('_id')}"
        public_link = f"{public_url}?t={token}"

        sent = {'email': False, 'sms': False}
        # send email
        try:
            smtp_host = os.getenv('SMTP_HOST')
            smtp_user = os.getenv('SMTP_USER')
            smtp_pass = os.getenv('SMTP_PASS')
            from_addr = os.getenv('SMTP_FROM', smtp_user)
            if smtp_host and smtp_user and smtp_pass and email:
                msg = EmailMessage()
                msg['Subject'] = 'Your Swasthya QR Access Link'
                msg['From'] = from_addr
                msg['To'] = email
                msg.set_content(f'Your access link: {public_link}\nIt expires in {os.getenv("QR_TOKEN_EXPIRY_DAYS", "7")} days.')
                with smtplib.SMTP(smtp_host) as s:
                    s.login(smtp_user, smtp_pass)
                    s.send_message(msg)
                sent['email'] = True
        except Exception:
            pass

        # send sms via Twilio SDK if configured, otherwise attempt generic TWILIO_URL REST endpoint
        try:
            sent_sms = False
            # Prefer Twilio SDK
            if phone and os.getenv('TWILIO_SID') and os.getenv('TWILIO_AUTH_TOKEN') and os.getenv('TWILIO_FROM'):
                body_text = f'Access link: {public_link}'
                if send_sms_via_twilio(phone, body_text):
                    sent_sms = True

            # Fallback to generic REST endpoint if SDK not available or not configured
            if not sent_sms:
                twilio_url = os.getenv('TWILIO_URL')
                twilio_from = os.getenv('TWILIO_FROM')
                if twilio_url and phone:
                    body = urlencode({'from': twilio_from or '', 'to': phone, 'body': f'Access link: {public_link}'})
                    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                    _requests.post(twilio_url, data=body, headers=headers, timeout=5)
                    sent_sms = True

            sent['sms'] = sent_sms
        except Exception:
            pass

        # store sent message in session so QR page can show confirmation
        request.session['qr_sent_msg'] = f"Email sent: {sent['email']}, SMS sent: {sent['sms']}"
    except Exception:
        token = None

    # Redirect back to QR page where new token will be used
    return RedirectResponse(url='/patient/qrcode', status_code=303)


@app.get('/p/{patient_id}')
def public_patient_view(request: Request, patient_id: str, t: str = ""):
    """Public-facing patient view for scanned QR codes. Token required."""
    if db is None:
        return templates.TemplateResponse('patient_public_view.html', {
            'request': request,
            'patient': None,
            'error': 'Database not available',
            'authorized': False
        })

    try:
        pid = ObjectId(patient_id)
        patient = db.users.find_one({'_id': pid})
        patient = oid_to_str(patient) if patient else None
    except Exception:
        patient = None

    # Validate token with expiration
    authorized = False
    if patient:
        stored = patient.get('public_token') or ''
        created = patient.get('public_token_created')
        # default expiry days (can be made configurable)
        expiry_days = int(os.getenv('QR_TOKEN_EXPIRY_DAYS', '7'))
        expired = False
        if created:
            try:
                created_dt = datetime.fromisoformat(created)
                expired = (datetime.utcnow() - created_dt).days >= expiry_days
            except Exception:
                expired = False

        if t and stored and t == stored and not expired:
            authorized = True

    return templates.TemplateResponse('patient_public_view.html', {
        'request': request,
        'patient': patient,
        'authorized': authorized,
        'token': t
    })


@app.get("/patient/edit-profile")
def edit_profile_get(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        patient = None
    else:
        patient = db.users.find_one({"username": user})
        patient = oid_to_str(patient) if patient else None
    
    return templates.TemplateResponse("patient_edit_profile.html", {
        "request": request,
        "user": user,
        "patient": patient if patient else {},
        "success": False
    })


@app.post("/patient/edit-profile")
def edit_profile_post(request: Request, 
                      name: str = Form(...),
                      email: str = Form(""),
                      age: Optional[int] = Form(None),
                      contact: str = Form(""),
                      blood_group: str = Form(""),
                      address: str = Form(""),
                      emergency_contact: str = Form("")):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/patient/edit-profile', status_code=303)
    
    # Update user document
    update_data = {
        "name": name,
        "email": email,
        "age": age,
        "contact": contact,
        "blood_group": blood_group,
        "address": address,
        "emergency_contact": emergency_contact
    }
    
    db.users.update_one({"username": user}, {"$set": update_data})
    
    # Fetch updated patient and return with success message
    patient = db.users.find_one({"username": user})
    patient = oid_to_str(patient) if patient else {}
    
    return templates.TemplateResponse("patient_edit_profile.html", {
        "request": request,
        "user": user,
        "patient": patient,
        "success": True
    })


@app.post("/patient/edit-medical")
def edit_medical_post(request: Request,
                     medical_history: str = Form(""),
                     allergies: str = Form(""),
                     current_medications: str = Form("")):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/patient/edit-profile', status_code=303)
    
    # Convert comma-separated strings to lists
    medical_hist = [h.strip() for h in medical_history.split(',') if h.strip()]
    allerg = [a.strip() for a in allergies.split(',') if a.strip()]
    meds = [m.strip() for m in current_medications.split(',') if m.strip()]
    
    # Update user document
    update_data = {
        "medical_history": medical_hist,
        "allergies": allerg,
        "current_medications": meds
    }
    
    db.users.update_one({"username": user}, {"$set": update_data})
    
    # Fetch updated patient and return with success message
    patient = db.users.find_one({"username": user})
    patient = oid_to_str(patient) if patient else {}
    
    return templates.TemplateResponse("patient_edit_profile.html", {
        "request": request,
        "user": user,
        "patient": patient,
        "success": True
    })


@app.get("/patient/add-prescription")
def add_prescription_get(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    return templates.TemplateResponse("patient_add_prescription.html", {
        "request": request,
        "user": user,
        "success": False
    })


@app.get('/patient/settings')
def patient_settings_get(request: Request):
    user = request.session.get('user')
    role = request.session.get('role')
    if not user or role != 'patient':
        return RedirectResponse(url='/login', status_code=303)

    if db is None:
        patient = {}
    else:
        patient = db.users.find_one({'username': user})
        patient = oid_to_str(patient) if patient else {}

    msg = request.session.pop('settings_msg', None)
    return templates.TemplateResponse('patient_settings.html', {
        'request': request,
        'user': user,
        'patient': patient,
        'message': msg
    })


@app.post('/patient/settings')
def patient_settings_post(request: Request, email: str = Form(''), contact: str = Form(''), action: str = Form('')):
    user = request.session.get('user')
    role = request.session.get('role')
    if not user or role != 'patient':
        return RedirectResponse(url='/login', status_code=303)

    if db is None:
        return RedirectResponse(url='/patient/settings', status_code=303)

    # Save contact details
    try:
        db.users.update_one({'username': user}, {'$set': {'email': email, 'contact': contact}})
    except Exception:
        pass

    sent = {'email': False, 'sms': False}

    # Handle action buttons: send test email or SMS
    try:
        if action == 'send_test_email' and email:
            smtp_host = os.getenv('SMTP_HOST')
            smtp_user = os.getenv('SMTP_USER')
            smtp_pass = os.getenv('SMTP_PASS')
            from_addr = os.getenv('SMTP_FROM', smtp_user)
            if smtp_host and smtp_user and smtp_pass:
                msg = EmailMessage()
                msg['Subject'] = 'Swasthya - Test Email'
                msg['From'] = from_addr
                msg['To'] = email
                msg.set_content('This is a test email from Swasthya to verify your settings.')
                with smtplib.SMTP(smtp_host) as s:
                    s.login(smtp_user, smtp_pass)
                    s.send_message(msg)
                sent['email'] = True

        if action == 'send_test_sms' and contact:
            body_text = 'This is a test SMS from Swasthya to verify your settings.'
            # Prefer Twilio SDK
            sms_sent = False
            if os.getenv('TWILIO_SID') and os.getenv('TWILIO_AUTH_TOKEN') and os.getenv('TWILIO_FROM'):
                sms_sent = send_sms_via_twilio(contact, body_text)

            if not sms_sent:
                twilio_url = os.getenv('TWILIO_URL')
                twilio_from = os.getenv('TWILIO_FROM')
                if twilio_url:
                    body = urlencode({'from': twilio_from or '', 'to': contact, 'body': body_text})
                    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                    _requests.post(twilio_url, data=body, headers=headers, timeout=5)
                    sms_sent = True

            sent['sms'] = sms_sent
    except Exception:
        pass

    request.session['settings_msg'] = f"Email sent: {sent['email']}, SMS sent: {sent['sms']}"
    return RedirectResponse(url='/patient/settings', status_code=303)


@app.post("/patient/add-prescription")
def add_prescription_post(request: Request,
                         medicine: str = Form(...),
                         dosage: str = Form(...),
                         duration: str = Form(...),
                         prescribed_by: str = Form(""),
                         notes: str = Form("")):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/patient/add-prescription', status_code=303)
    
    try:
        prescription = {
            "medicine": medicine,
            "dosage": dosage,
            "duration": duration,
            "prescribed_by": prescribed_by if prescribed_by else "Self-reported",
            "date": datetime.utcnow().isoformat(),
            "notes": notes
        }
        db.users.update_one({"username": user}, {"$push": {"prescriptions": prescription}})
    except Exception as e:
        print(f"Error adding prescription: {e}")
        pass
    
    return templates.TemplateResponse("patient_add_prescription.html", {
        "request": request,
        "user": user,
        "success": True
    })


@app.get("/patient/add-visit")
def add_visit_get(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    return templates.TemplateResponse("patient_add_visit.html", {
        "request": request,
        "user": user,
        "success": False
    })


@app.post("/patient/add-visit")
def add_visit_post(request: Request,
                  doctor: str = Form(...),
                  visit_date: str = Form(...),
                  diagnosis: str = Form(...),
                  treatment: str = Form(...),
                  notes: str = Form("")):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/patient/add-visit', status_code=303)
    
    try:
        visit = {
            "date": visit_date,
            "doctor": doctor,
            "diagnosis": diagnosis,
            "treatment": treatment,
            "notes": notes,
            "recorded_by": user,
            "recorded_at": datetime.utcnow().isoformat()
        }
        db.users.update_one({"username": user}, {"$push": {"visits": visit}})
    except Exception as e:
        print(f"Error adding visit: {e}")
        pass
    
    return templates.TemplateResponse("patient_add_visit.html", {
        "request": request,
        "user": user,
        "success": True
    })


# ===== DOCTOR ROUTES =====
@app.get("/doctor/dashboard")
def doctor_dashboard(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        patients = []
        appointments = []
        doctors_list = []
    else:
        patients = [oid_to_str(d) for d in db.users.find({"role": "patient"}).limit(50)]
        appointments = [oid_to_str(d) for d in db.appointments.find().limit(50)]
        # doctor panel should show all registered/approved doctors
        doctors_list = [oid_to_str(d) for d in db.doctors.find({"approved": True}).limit(50)]
    
    return templates.TemplateResponse("doctor_dashboard.html", {
        "request": request,
        "user": user,
        "role": role,
        "patients": patients,
        "appointments": appointments,
        "doctors": doctors_list
    })


@app.get("/doctor/patient/{patient_id}")
def view_patient_details(request: Request, patient_id: str):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        patient = None
        analysis = None
    else:
        try:
            pid = ObjectId(patient_id)
            patient = db.users.find_one({"_id": pid})
            patient = oid_to_str(patient) if patient else None
            analysis = analyze_health(patient) if patient else None
        except:
            patient = None
            analysis = None
    
    return templates.TemplateResponse("doctor_patient_detail.html", {
        "request": request,
        "user": user,
        "patient": patient,
        "analysis": analysis
    })


@app.post("/doctor/add-prescription")
def add_prescription(request: Request, patient_id: str = Form(...), 
                    medicine: str = Form(...), dosage: str = Form(...),
                    duration: str = Form(...)):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)
    
    try:
        pid = ObjectId(patient_id)
        prescription = {
            "medicine": medicine,
            "dosage": dosage,
            "duration": duration,
            "prescribed_by": user,
            "date": datetime.utcnow().isoformat()
        }
        db.users.update_one({"_id": pid}, {"$push": {"prescriptions": prescription}})
    except:
        pass
    
    return RedirectResponse(url=f'/doctor/patient/{patient_id}', status_code=303)


@app.post("/doctor/add-visit")
def add_visit_record(request: Request, patient_id: str = Form(...), 
                    diagnosis: str = Form(...), treatment: str = Form(...),
                    notes: str = Form("")):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)
    
    try:
        pid = ObjectId(patient_id)
        visit = {
            "date": datetime.utcnow().isoformat(),
            "doctor": user,
            "diagnosis": diagnosis,
            "treatment": treatment,
            "notes": notes
        }
        db.users.update_one({"_id": pid}, {"$push": {"visits": visit}})
    except:
        pass
    
    return RedirectResponse(url=f'/doctor/patient/{patient_id}', status_code=303)


# ===== ADMIN ROUTES =====
@app.get("/admin/dashboard")
def admin_dashboard(request: Request):
    try:
        user = request.session.get("user")
        role = request.session.get("role")
        if not user or role != "admin":
            return RedirectResponse(url='/login', status_code=303)

        if db is None:
            stats = {"patients": 0, "doctors": 0, "appointments": 0, "pending_doctors": 0}
        else:
            stats = {
                "patients": db.users.count_documents({"role": "patient"}),
                "doctors": db.users.count_documents({"role": "doctor"}),
                "appointments": db.appointments.count_documents({}),
                "pending_doctors": db.doctors.count_documents({"approved": False})
            }

        # debug: indicate template handler was executed (logs before response)
        logger.debug("served admin_dashboard template for user=%s", user)
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "user": user,
            "stats": stats
        })
    except Exception as e:
        # Log full exception traceback for diagnostics and return a friendly HTML error
        logger.exception("Error rendering admin dashboard")
        body = "<h2>Internal Server Error</h2><p>Unable to render admin dashboard. Check server logs for details.</p>"
        return HTMLResponse(content=body, status_code=500)



# ===== ADMIN DOCTOR APPROVAL ROUTES =====

@app.get("/admin/doctors", tags=["admin"])
def admin_list_doctors(request: Request):
    try:
        user = request.session.get("user")
        role = request.session.get("role")
        if not user or role != "admin":
            return RedirectResponse(url='/login', status_code=303)
        
        docs = []
        if db is not None:
            docs = [oid_to_str(d) for d in db.doctors.find().sort("approved", 1)]
        
        return templates.TemplateResponse("admin_doctors.html", {
            "request": request,
            "user": user,
            "doctors": docs
        })
    except Exception as e:
        logger.exception(f"Error loading admin doctors page: {e}")
        return HTMLResponse(
            content=f"<h2>Error</h2><p>Unable to load doctors list: {str(e)}</p>",
            status_code=500
        )

@app.post("/admin/doctors/approve", tags=["admin"])
def admin_approve_doctor(request: Request, doctor_id: str = Form(...)):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "admin":
        return RedirectResponse(url='/login', status_code=303)
    
    try:
        if db is None:
            logger.error("Database not available for doctor approval")
        else:
            oid = ObjectId(doctor_id)
            result = db.doctors.update_one({"_id": oid}, {"$set": {"approved": True}})
            logger.info(f"Doctor approval: matched={result.matched_count}, modified={result.modified_count}")
    except Exception as e:
        logger.exception(f"Error approving doctor {doctor_id}: {e}")
    
    return RedirectResponse(url='/admin/doctors', status_code=303)

# ===== EMERGENCY ACCESS (No login required) =====
@app.get("/emergency/{patient_qr_id}")
def emergency_access(request: Request, patient_qr_id: str):
    if db is None:
        patient = None
    else:
        try:
            pid = ObjectId(patient_qr_id)
            patient = db.users.find_one({"_id": pid})
            patient = oid_to_str(patient) if patient else None
        except:
            patient = None
    
    return templates.TemplateResponse("emergency_access.html", {
        "request": request,
        "patient": patient,
        "is_emergency": True
    })


# ===== APPOINTMENTS =====
@app.get("/appointments")
def appointments_view(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    
    if db is None:
        items = []
    else:
        items = [oid_to_str(d) for d in db.appointments.find().limit(100)]
    
    return templates.TemplateResponse("appointments.html", {
        "request": request,
        "user": user,
        "role": role,
        "appointments": items
    })


@app.post("/appointments/book")
def book_appointment(request: Request, doctor_name: str = Form(...),
                    appointment_date: str = Form(...), time: str = Form(...)):
    user = request.session.get("user")
    role = request.session.get("role")
    
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/appointments', status_code=303)
    
    patient_name = request.session.get("name", user)
    appointment = {
        "patient_name": patient_name,
        "doctor_name": doctor_name,
        "date": appointment_date,
        "time": time,
        "status": "scheduled",
        "notes": ""
    }
    db.appointments.insert_one(appointment)
    
    return RedirectResponse(url='/appointments', status_code=303)


# ===== LEGACY ROUTES (for compatibility) =====
@app.get("/patients")
def patients_view(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        items = []
    else:
        items = [oid_to_str(d) for d in db.users.find({"role": "patient"}).limit(100)]
    
    return templates.TemplateResponse("patients.html", {
        "request": request,
        "user": user,
        "patients": items
    })


@app.post("/patients/add")
def add_patient(request: Request, name: str = Form(...), age: int = Form(...),
                blood_group: str = Form(""), address: str = Form("")):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is not None:
        db.users.insert_one({
            "username": f"patient_{uuid.uuid4().hex[:8]}",
            "password": password_manager.hash_password("temp"),
            "role": "patient",
            "name": name,
            "age": age,
            "blood_group": blood_group,
            "address": address,
            "medical_history": [],
            "visits": [],
            "prescriptions": [],
            "reports": []
        })
    
    return RedirectResponse(url='/patients', status_code=303)


@app.get('/doctors')
def doctors_view(request: Request):
    user = request.session.get('user')
    role = request.session.get('role')
    
    if db is None:
        docs = []
    else:
        if role == 'admin':
            # admin sees all doctors for review
            docs = [oid_to_str(d) for d in db.doctors.find().limit(100)]
        else:
            # only show approved doctors to general users
            docs = [oid_to_str(d) for d in db.doctors.find({"approved": True}).limit(100)]
    
    return templates.TemplateResponse('doctors.html', {
        'request': request,
        'user': user,
        'doctors': docs
    })


@app.post("/patients/upload")
def upload_file(request: Request, patient_id: str = Form(...), file: UploadFile = File(...)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/patients', status_code=303)
    
    try:
        pid = ObjectId(patient_id)
    except:
        return RedirectResponse(url='/patients', status_code=303)
    
    # Save file to uploads
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    dest_path = os.path.join(uploads_dir, filename)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    meta = {
        "filename": file.filename,
        "stored_name": filename,
        "path": f"/static/uploads/{filename}",
        "uploaded_by": user,
        "uploaded_at": datetime.utcnow().isoformat()
    }
    db.users.update_one({"_id": pid}, {"$push": {"reports": meta}})
    
    return RedirectResponse(url='/patients', status_code=303)


# API endpoints
@app.get("/api/", tags=["health"])
def health():
    return {"status": "ok", "message": "Swasthya - AI QR Healthcare System running"}


@app.get("/api/patients", tags=["patients"])
def api_list_patients():
    if db is None:
        return []
    return [oid_to_str(d) for d in db.users.find({"role": "patient"}).limit(100)]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3001)), reload=True)


# ensure uploads dir
uploads_dir = os.path.join(static_dir, "uploads")
os.makedirs(uploads_dir, exist_ok=True)


# --- Server-rendered routes ---
@app.on_event("startup")
def on_startup():
    seed_db()


@app.get("/")
def index(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("home.html", {"request": request, "user": user})


@app.get("/register")
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if db is None:
        return templates.TemplateResponse("register.html", {"request": request, "error": "DB not available"})
    if db.users.find_one({"username": username}):
        return templates.TemplateResponse("register.html", {"request": request, "error": "User exists"})
    hashed = password_manager.hash_password(password)
    db.users.insert_one({"username": username, "password": hashed})
    request.session["user"] = username
    return RedirectResponse(url='/', status_code=303)


@app.get("/login")
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if db is None:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DB not available"})
    u = db.users.find_one({"username": username})
    if not u or not password_manager.verify_password(password, u["password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    request.session["user"] = username
    return RedirectResponse(url='/', status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url='/', status_code=303)


@app.get("/patients")
def patients_view(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    if db is None:
        items = []
    else:
        items = [oid_to_str(d) for d in db.patients.find().limit(100)]
    return templates.TemplateResponse("patients.html", {"request": request, "user": user, "patients": items})


@app.post("/patients/add")
def add_patient(request: Request, name: str = Form(...), age: int = Form(...), notes: str = Form("")):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    if db is not None:
        db.patients.insert_one({"name": name, "age": age, "notes": notes})
    return RedirectResponse(url='/patients', status_code=303)


@app.get('/doctors')
def doctors_view(request: Request):
    user = request.session.get('user')
    if db is None:
        docs = []
    else:
        docs = [oid_to_str(d) for d in db.doctors.find().limit(100)]
    return templates.TemplateResponse('doctors.html', {'request': request, 'user': user, 'doctors': docs})


@app.get('/appointments')
def appointments_view(request: Request):
    user = request.session.get('user')
    if db is None:
        items = []
    else:
        items = [oid_to_str(d) for d in db.appointments.find().limit(100)]
    return templates.TemplateResponse('appointments.html', {'request': request, 'user': user, 'appointments': items})


@app.post("/patients/upload")
def upload_file(request: Request, patient_id: str = Form(...), file: UploadFile = File(...)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    if db is None:
        return templates.TemplateResponse("patients.html", {"request": request, "user": user, "patients": [] , "error": "DB not available"})
    # validate patient exists
    try:
        pid = ObjectId(patient_id)
    except Exception:
        return RedirectResponse(url='/patients', status_code=303)

    # save file to uploads
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    dest_path = os.path.join(uploads_dir, filename)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    meta = {
        "filename": file.filename,
        "stored_name": filename,
        "path": f"/static/uploads/{filename}",
        "uploaded_by": user,
        "uploaded_at": datetime.utcnow().isoformat()
    }
    db.patients.update_one({"_id": pid}, {"$push": {"files": meta}})
    return RedirectResponse(url='/patients', status_code=303)


# Keep simple JSON API endpoints for compatibility
@app.get("/api/", tags=["health"])
def health():
    return {"status": "ok", "message": "Swasthya API (FastAPI) running"}


@app.get("/api/patients", tags=["patients"])
def api_list_patients():
    if db is None:
        return []
    return [oid_to_str(d) for d in db.patients.find().limit(100)]

@app.get("/api/doctors", tags=["doctors"])
def api_list_doctors():
    if db is None:
        return []
    return [oid_to_str(d) for d in db.doctors.find({"approved": True}).limit(100)]


# ============== ADMIN & BACKUP ROUTES ==============

@app.on_event("startup")
async def startup_event():
    """Initialize app and validate configuration"""
    try:
        config.validate()
        logger.info("✅ Configuration validated successfully")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
    
    # Log startup info
    logger.info(f"🚀 Swasthya App Starting")
    logger.info(f"   Environment: {config.ENVIRONMENT}")
    logger.info(f"   Debug: {config.DEBUG}")
    logger.info(f"   Database: {config.DATABASE_NAME}")
    logger.info(f"   Rate Limiting: {'Enabled' if config.RATE_LIMIT_ENABLED else 'Disabled'}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Swasthya App Shutting Down")


@app.get("/admin/backup/list", tags=["admin"])
def list_backups_admin(request: Request):
    """List all available database backups"""
    require_admin(request)
    user = request.session.get('user')
    
    try:
        if db_backup:
            backups = db_backup.list_backups()
            return {"success": True, "backups": backups}
        return {"success": False, "error": "Database not initialized"}
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return {"success": False, "error": str(e)}


@app.post("/admin/backup/create", tags=["admin"])
def create_backup_admin(request: Request):
    """Create a new database backup"""
    require_admin(request)
    user = request.session.get('user')
    
    try:
        if db_backup:
            backup_path = db_backup.backup()
            return {
                "success": True,
                "message": f"Backup created: {backup_path}",
                "path": backup_path
            }
        return {"success": False, "error": "Database not initialized"}
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return {"success": False, "error": str(e)}


@app.post("/admin/backup/cleanup", tags=["admin"])
def cleanup_backups_admin(
    request: Request,
    keep_days: int = 30,
    keep_count: int = 10
):
    """Clean up old backups"""
    require_admin(request)
    user = request.session.get('user')
    
    try:
        if db_backup:
            deleted = db_backup.cleanup_old_backups(
                keep_days=keep_days,
                keep_count=keep_count
            )
            return {
                "success": True,
                "message": f"{deleted} old backup(s) removed"
            }
        return {"success": False, "error": "Database not initialized"}
    except Exception as e:
        logger.error(f"Error cleaning up backups: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/health", tags=["system"])
def health_check():
    """System health check endpoint"""
    status = {
        "status": "healthy" if db else "degraded",
        "database": "connected" if db else "disconnected",
        "version": "1.0.0",
        "environment": config.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    status_code = 200 if db else 503
    return JSONResponse(content=status, status_code=status_code)


@app.get("/api/config/info", tags=["system"])
def config_info(request: Request):
    """Get non-sensitive configuration info (admin only)"""
    require_admin(request)
    return {
        "app_name": "Swasthya - AI QR Healthcare System",
        "version": "1.0.0",
        "environment": config.ENVIRONMENT,
        "debug": config.DEBUG,
        "database_name": config.DATABASE_NAME,
        "qr_token_expiry_days": config.QR_TOKEN_EXPIRY_DAYS,
        "smtp_enabled": config.SMTP_ENABLED,
        "twilio_enabled": config.TWILIO_ENABLED,
        "rate_limiting_enabled": config.RATE_LIMIT_ENABLED,
        "rate_limit_per_minute": config.RATE_LIMIT_PER_MINUTE,
    }


if __name__ == "__main__":
    import uvicorn
    
    # Use config values
    host = config.HOST
    port = config.PORT
    
    logger.info(f"Starting server at http://{host}:{port}")
    logger.info(f"API Docs: http://{host}:{port}/api/docs")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower(),
    )
