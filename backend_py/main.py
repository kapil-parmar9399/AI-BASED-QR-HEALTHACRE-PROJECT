import os
import random
import threading
import time
import re
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
from datetime import datetime, timedelta
import qrcode
import io
import base64
import numpy as np
from slowapi import Limiter
from slowapi.util import get_remote_address
from health_utils import analyze_health_ai
from doctor_engine import suggest_doctor
from diet_engine import generate_diet
from medicine_engine import suggest_medicine
from pdf_generator import generate_pdf

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
    url = os.getenv("PUBLIC_URL", "").strip()
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


def _extract_metrics_from_text(text: str) -> dict:
    """Best-effort extraction of vitals from report text."""
    metrics = {}
    if not text:
        return metrics

    # Normalize (keep lines for table-style PDFs)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    t = " ".join(lines)

    def _first_number(s: str) -> Optional[float]:
        m = re.search(r"([0-9]{2,3}(?:\\.[0-9])?)", s)
        return float(m.group(1)) if m else None

    # Blood pressure: "bp", "b.p.", "blood pressure", "systolic/diastolic"
    bp_match = re.search(r"(blood pressure|bp|b\\.p\\.|systolic)[:\\s-]*([0-9]{2,3})(?:\\s*/\\s*([0-9]{2,3}))?", t, re.IGNORECASE)
    if bp_match:
        metrics["blood_pressure"] = int(bp_match.group(2))
    else:
        # Try generic pattern like "120/80"
        bp_match2 = re.search(r"\\b([0-9]{2,3})\\s*/\\s*([0-9]{2,3})\\b", t)
        if bp_match2:
            metrics["blood_pressure"] = int(bp_match2.group(1))

    # Sugar / glucose (inline)
    sugar_matches = re.findall(r"(sugar|blood sugar|glucose|fbs|rbs|fasting|random)[:\\s-]*([0-9]{2,3})", t, re.IGNORECASE)
    if sugar_matches:
        values = [int(m[1]) for m in sugar_matches]
        metrics["sugar_level"] = max(values)

    # Cholesterol (inline)
    chol_match = re.search(r"(cholesterol|total cholesterol|tc)[:\\s-]*([0-9]{2,3})", t, re.IGNORECASE)
    if chol_match:
        metrics["cholesterol"] = int(chol_match.group(2))

    # BMI (inline)
    bmi_match = re.search(r"(bmi)[:\\s-]*([0-9]{2,3}(?:\\.[0-9])?)", t, re.IGNORECASE)
    if bmi_match:
        metrics["bmi"] = float(bmi_match.group(2))

    # Table-style: label on one line, value on next
    label_map = {
        "blood sugar": "sugar_level",
        "sugar": "sugar_level",
        "glucose": "sugar_level",
        "cholesterol": "cholesterol",
        "bmi": "bmi",
        "blood pressure": "blood_pressure",
        "bp": "blood_pressure",
    }
    for idx, ln in enumerate(lines):
        key = None
        low = ln.lower()
        for label, metric_key in label_map.items():
            if label in low:
                key = metric_key
                break
        if not key:
            continue
        # If number is on same line, use it
        num = _first_number(ln)
        if num is None and idx + 1 < len(lines):
            num = _first_number(lines[idx + 1])
        if num is not None:
            if key in ["blood_pressure", "sugar_level", "cholesterol"]:
                metrics[key] = int(num)
            elif key == "bmi":
                metrics[key] = float(num)

    # Symptoms: capture bullets after "Symptoms:"
    for i, ln in enumerate(lines):
        if ln.lower().startswith("symptoms"):
            collected = []
            for j in range(i + 1, min(i + 6, len(lines))):
                if re.search(r"^(test|result|normal range|diagnosis|prescription)\\b", lines[j], re.IGNORECASE):
                    break
                collected.append(lines[j])
            if collected:
                joined = " ".join(collected).replace(" - ", ", ").replace("-", ",")
                symptoms = [s.strip() for s in joined.split(",") if s.strip()]
                if symptoms:
                    metrics["symptoms"] = symptoms
            break

    return metrics


def _ocr_text_from_image_path(image_path: str) -> str:
    """Best-effort OCR for image files."""
    try:
        import pytesseract  # optional dependency
        from PIL import Image
        # Ensure tesseract path on Windows if not in PATH
        if os.name == "nt":
            default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        return pytesseract.image_to_string(Image.open(image_path)) or ""
    except Exception:
        return ""


def _ocr_text_from_pdf_path(pdf_path: str) -> str:
    """Best-effort OCR for PDF via pdf2image + pytesseract."""
    try:
        from pdf2image import convert_from_path  # optional dependency
        import pytesseract  # optional dependency
        # Ensure tesseract path on Windows if not in PATH
        if os.name == "nt":
            default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        text_parts = []
        images = convert_from_path(pdf_path, first_page=1, last_page=2)
        for img in images:
            text_parts.append(pytesseract.image_to_string(img) or "")
        return " ".join(text_parts)
    except Exception:
        return ""


def send_sms_via_twilio(to: str, body: str) -> bool:
    """Send SMS using Twilio SDK if configured."""
    sid = os.getenv('TWILIO_SID') or os.getenv('TWILIO_ACCOUNT_SID')
    auth = os.getenv('TWILIO_AUTH_TOKEN')
    from_num = os.getenv('TWILIO_FROM') or os.getenv('TWILIO_FROM_NUMBER')
    if not (sid and auth and from_num):
        return False
    if TwilioClient is None:
        return False
    try:
        client = TwilioClient(sid, auth)
        client.messages.create(body=body, from_=from_num, to=to)
        return True
    except Exception as e:
        logger.exception("Twilio SMS failed: %s", e)
        return False


def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"


def is_valid_phone(phone: str) -> bool:
    # E.164 format like +91XXXXXXXXXX
    return bool(re.fullmatch(r"\+[1-9]\d{9,14}$", phone or ""))


def is_strong_password(pw: str) -> bool:
    # Minimum 8 chars, at least 1 upper, 1 lower, 1 digit, 1 special
    if not pw or len(pw) < 8:
        return False
    if not re.search(r"[A-Z]", pw):
        return False
    if not re.search(r"[a-z]", pw):
        return False
    if not re.search(r"\d", pw):
        return False
    if not re.search(r"[^\w\s]", pw):
        return False
    return True


def is_valid_contact(contact: str) -> bool:
    if not contact:
        return True
    if is_valid_phone(contact):
        return True
    return bool(re.fullmatch(r"\d{10,15}", contact))


def save_otp(phone: str, otp: str, user_id: str):
    if db is None:
        return
    try:
        db.otps.insert_one({
            "phone": phone,
            "otp": otp,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=5)
        })
    except Exception:
        pass


def verify_otp(phone: str, otp: str):
    if db is None:
        return None
    try:
        rec = db.otps.find_one({
            "phone": phone,
            "otp": otp,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        if rec:
            # cleanup used OTPs
            db.otps.delete_many({"phone": phone})
            return rec
    except Exception:
        pass
    return None


def _parse_duration_days(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d+)", str(text))
    return int(m.group(1)) if m else None


def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _send_sms_safe(phone: str, body: str) -> bool:
    if not phone:
        return False
    try:
        return send_sms_via_twilio(phone, body)
    except Exception:
        return False


def send_appointment_reminders():
    if db is None:
        return
    try:
        tomorrow = (datetime.utcnow().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        appts = list(db.appointments.find({
            "date": tomorrow,
            "status": {"$in": ["pending", "scheduled", "accepted", "rescheduled"]},
            "$or": [{"reminder_sent": {"$exists": False}}, {"reminder_sent": False}]
        }))
        for apt in appts:
            phone = None
            if apt.get("patient_username"):
                u = db.users.find_one({"username": apt.get("patient_username")})
                phone = u.get("phone") if u else None
            if not phone and apt.get("patient_name"):
                u = db.users.find_one({"name": apt.get("patient_name")})
                phone = u.get("phone") if u else None
            if phone:
                msg = f"Appointment reminder: {apt.get('doctor_display', apt.get('doctor_name', 'Doctor'))} on {apt.get('date')} at {apt.get('time')}."
                if _send_sms_safe(phone, msg):
                    db.appointments.update_one({"_id": apt["_id"]}, {"$set": {"reminder_sent": True}})
    except Exception:
        logger.exception("appointment reminders failed")


def send_medicine_reminders():
    if db is None:
        return
    try:
        today = _today_str()
        patients = list(db.users.find({"role": "patient"}))
        for p in patients:
            phone = p.get("phone")
            if not phone:
                continue
            prescriptions = p.get("prescriptions", [])
            for rx in prescriptions:
                last = rx.get("last_reminder_date")
                if last == today:
                    continue
                days = _parse_duration_days(rx.get("duration"))
                start_date = rx.get("date", "")[:10]
                if days and start_date:
                    try:
                        start = datetime.strptime(start_date, "%Y-%m-%d").date()
                    except Exception:
                        try:
                            start = datetime.fromisoformat(rx.get("date", "")).date()
                        except Exception:
                            start = None
                    if start:
                        end = start + timedelta(days=days)
                        if datetime.utcnow().date() > end:
                            continue
                # send reminder
                msg = f"Medicine reminder: {rx.get('medicine', 'your prescription')} - {rx.get('dosage', '')}."
                if _send_sms_safe(phone, msg):
                    # update embedded doc using positional operator
                    db.users.update_one(
                        {"_id": p["_id"], "prescriptions": rx},
                        {"$set": {"prescriptions.$.last_reminder_date": today}}
                    )
    except Exception:
        logger.exception("medicine reminders failed")


def reminder_loop():
    # Runs periodically (hourly) to send reminders
    while True:
        try:
            send_appointment_reminders()
            # send medicine reminders once per day around 09:00 UTC
            if datetime.utcnow().hour == 9:
                send_medicine_reminders()
        except Exception:
            logger.exception("reminder loop failed")
        time.sleep(3600)


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
    # Start reminder background loop
    t = threading.Thread(target=reminder_loop, daemon=True)
    t.start()


# backend_py/main.py


# from fastapi.templating import Jinja2Templates

# templates = Jinja2Templates(directory="templates")

# # Example AI health analysis function
# def analyze_health(patient_data: dict) -> dict:
#     """Basic AI health analysis based on patient data"""
#     analysis = {
#         "age_risk": "Low",
#         "pattern": "Stable",
#         "recommendations": []
#     }
    
#     age = patient_data.get("age", 0)
#     if age > 60:
#         analysis["age_risk"] = "High"
#         analysis["recommendations"].append("Regular cardiovascular checkup recommended")
#     elif age > 45:
#         analysis["age_risk"] = "Medium"
#         analysis["recommendations"].append("Annual health checkup advised")
    
#     visits = len(patient_data.get("visits", []))
#     if visits > 5:
#         analysis["pattern"] = "Frequent - Monitor closely"
#         analysis["recommendations"].append("Consider specialist consultation")
#     elif visits > 2:
#         analysis["pattern"] = "Moderate - Normal"
    
#     history = patient_data.get("medical_history", [])
#     if history:
#         analysis["recommendations"].append(f"Continuing treatment for {len(history)} condition(s)")
    
#     if not analysis["recommendations"]:
#         analysis["recommendations"].append("Maintain regular checkups")
    
#     return analysis

# Route for AI Medical Report
# @app.get("/patient/medical-report", response_class=HTMLResponse)
# async def patient_medical_report(request: Request):
#     # Fetch patient data from your DB
#     # For example:
#     patient = db.patients.find_one({"email": request.session.get("user_email")})
#     if not patient:
#         return templates.TemplateResponse("error.html", {"request": request, "message": "Patient not found"})

#     # Run AI analysis
#     analysis = analyze_health(patient)

#     return templates.TemplateResponse(
#         "medical_report.html",
#         {"request": request, "patient": patient, "analysis": analysis}
#     )

# from fastapi import Request
# from fastapi.responses import HTMLResponse, RedirectResponse
# from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# # Example AI health analysis function
# def analyze_health(patient_data: dict) -> dict:
#     """Basic AI health analysis based on patient data"""
#     analysis = {
#         "age_risk": "Low",
#         "pattern": "Stable",
#         "recommendations": []
#     }
    
#     age = patient_data.get("age", 0)
#     if age > 60:
#         analysis["age_risk"] = "High"
#         analysis["recommendations"].append("Regular cardiovascular checkup recommended")
#     elif age > 45:
#         analysis["age_risk"] = "Medium"
#         analysis["recommendations"].append("Annual health checkup advised")
    
#     visits = len(patient_data.get("visits", []))
#     if visits > 5:
#         analysis["pattern"] = "Frequent - Monitor closely"
#         analysis["recommendations"].append("Consider specialist consultation")
#     elif visits > 2:
#         analysis["pattern"] = "Moderate - Normal"
    
#     history = patient_data.get("medical_history", [])
#     if history:
#         analysis["recommendations"].append(f"Continuing treatment for {len(history)} condition(s)")
    
#     if not analysis["recommendations"]:
#         analysis["recommendations"].append("Maintain regular checkups")
    
#     return analysis

# Route for AI Medical Report
from health_utils import analyze_health_ai
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request

# ---------------- UPLOAD REPORT ----------------
@app.post("/patient/upload-report")
async def upload_report(request: Request, file: UploadFile = File(...)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Save file under static uploads for access
    report_dir = os.path.join(uploads_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(report_dir, stored_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Try to extract metrics from report text (txt/pdf)
    extracted = {}
    try:
        if file.filename.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as rf:
                text_raw = rf.read()
                extracted = _extract_metrics_from_text(text_raw)
                logger.info("upload-report txt parsed len=%s extracted=%s", len(text_raw), extracted)
        elif file.filename.lower().endswith(".pdf"):
            text = ""
            # Try PyPDF2 first
            try:
                import PyPDF2  # optional dependency
                text_parts = []
                with open(file_path, "rb") as rf:
                    reader = PyPDF2.PdfReader(rf)
                    for page in reader.pages:
                        text_parts.append(page.extract_text() or "")
                text = " ".join(text_parts)
            except Exception:
                text = ""

            # Fallback to pdfminer.six if available
            if not text.strip():
                try:
                    from pdfminer.high_level import extract_text  # optional dependency
                    text = extract_text(file_path) or ""
                except Exception:
                    text = ""

            # OCR fallback for scanned PDFs
            if not text.strip():
                text = _ocr_text_from_pdf_path(file_path)

            extracted = _extract_metrics_from_text(text)
            if not extracted and text:
                logger.info("upload-report pdf text sample=%s", text[:500])
            logger.info("upload-report pdf parsed len=%s extracted=%s", len(text), extracted)
        elif file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            text = _ocr_text_from_image_path(file_path)
            extracted = _extract_metrics_from_text(text)
            logger.info("upload-report image parsed len=%s extracted=%s", len(text), extracted)
    except Exception:
        extracted = {}
        logger.exception("upload-report parsing failed")

    # Build patient payload for AI analysis
    patient = db.users.find_one({"username": user})
    patient = oid_to_str(patient) if patient else {}
    patient_payload = {
        "age": patient.get("age", 0),
        "blood_pressure": extracted.get("blood_pressure", patient.get("blood_pressure", 0)),
        "sugar_level": extracted.get("sugar_level", patient.get("sugar_level", 0)),
        "cholesterol": extracted.get("cholesterol", patient.get("cholesterol", 0)),
        "bmi": extracted.get("bmi", patient.get("bmi", 0)),
        "symptoms": extracted.get("symptoms", patient.get("symptoms", [])),
        "filename": file.filename,
    }

    analysis = analyze_health_ai(patient_payload) or {}
    logger.info("upload-report analysis risk_score=%s risk_level=%s", analysis.get("risk_score"), analysis.get("risk_level"))

    # Save in MongoDB
    db.users.update_one(
        {"username": user},
        {
            "$push": {
                "reports": {
                    "filename": file.filename,
                    "stored_name": stored_name,
                    "path": f"/static/uploads/reports/{stored_name}",
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "analysis": analysis,
                }
            }
        },
    )

    # Optionally update patient vitals if extracted
    if extracted:
        update_data = {}
        for k in ["blood_pressure", "sugar_level", "cholesterol", "bmi", "symptoms"]:
            if k in extracted:
                update_data[k] = extracted[k]
        if update_data:
            db.users.update_one({"username": user}, {"$set": update_data})

    # Health warning SMS for high risk
    try:
        if analysis.get("risk_level") == "High":
            u = db.users.find_one({"username": user})
            phone = u.get("phone") if u else None
            _send_sms_safe(phone, "Health warning: High risk detected in your latest report. Please consult a doctor.")
    except Exception:
        pass

    return RedirectResponse(
        url="/patient/medical-report?msg=uploaded",
        status_code=303
    )


@app.get("/patient/medical-report")
def patient_medical_report(request: Request, msg: str = None):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)

    # Patient data from DB
    patient = db.users.find_one({"username": user})
    patient = oid_to_str(patient) if patient else {}

    # If a report was uploaded, use its analysis; otherwise analyze patient data
    reports = patient.get("reports", [])
    analysis = None
    if reports:
        latest_report = sorted(
            reports, key=lambda x: x.get("uploaded_at", ""), reverse=True
        )[0]
        analysis = latest_report.get("analysis")
    if not analysis:
        analysis = analyze_health_ai(patient)

    # Ensure required keys exist for template rendering
    analysis = {
        "summary": analysis.get("summary", "Report analyzed"),
        "risk_score": analysis.get("risk_score", 0),
        "risk_percentage": analysis.get("risk_percentage", 0),
        "risk_level": analysis.get("risk_level", "Low"),
        "possible_diseases": analysis.get("possible_diseases", []),
        "recommendations": analysis.get("recommendations", []),
        "emergency": analysis.get("emergency", False),
        "emergency_message": analysis.get("emergency_message", ""),
    }

    # Step 10 logic: Doctor + Diet + Medicine
    doctor = suggest_doctor(analysis["possible_diseases"])
    diet = generate_diet(analysis["possible_diseases"])
    medicine = suggest_medicine(analysis["possible_diseases"])

    # Add these to analysis dict
    analysis["doctor"] = doctor
    analysis["diet"] = diet
    analysis["medicine"] = medicine

    # Emergency alert message (optional)
    # If risk is high or risk percentage is very high but emergency flag is missing/false, still show alert.
    risk_pct_raw = analysis.get("risk_percentage", 0)
    try:
        risk_pct = float(risk_pct_raw)
    except Exception:
        risk_pct = 0.0

    if (analysis.get("risk_level") == "High" or risk_pct >= 70) and not analysis.get("emergency"):
        analysis["emergency"] = True
        analysis["emergency_message"] = "High risk detected! Please consult a doctor immediately."
    elif analysis.get("emergency"):
        # Keep any specific emergency message if already provided
        if not analysis.get("emergency_message"):
            analysis["emergency_message"] = "Immediate medical attention required!"

    # Step 4: PDF generation (optional: filename by username)
    pdf_filename = f"{user}_medical_report.pdf"
    generate_pdf(patient, analysis, filename=pdf_filename)

    return templates.TemplateResponse(
        "patient_medical_report.html",
        {
            "request": request,
            "patient": patient,
            "health_analysis": analysis,
            "pdf_file": pdf_filename,  # template me download button ke liye
            "msg": msg
        }
    )
@app.get("/")
def index(request: Request):
    user = request.session.get("user")
    print(f"User '{user}' accessed home page")
    user_role = request.session.get("role")
    return templates.TemplateResponse("home.html", {"request": request, "user": user, "role": user_role})


@app.get("/register")
def register_get(request: Request):
    if not request.session.get("otp_verified"):
        return RedirectResponse(url="/register/phone", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "phone": request.session.get("phone")})


@app.post("/register")
def register_post(request: Request, username: str = Form(...), password: str = Form(...), 
                  name: str = Form(...), role: str = Form("patient"), confirm_password: str = Form(...),
                  doctor_specialty: str = Form(""), doctor_degree: str = Form(""), doctor_id: str = Form("")):
    if db is None:
        return templates.TemplateResponse("register.html", {"request": request, "error": "DB not available"})
    if not request.session.get("otp_verified"):
        return RedirectResponse(url="/register/phone", status_code=303)
    phone = request.session.get("phone")
    if not phone:
        return RedirectResponse(url="/register/phone", status_code=303)
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match.",
            "phone": phone
        })
    if not is_strong_password(password):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Password must be 8+ chars with upper, lower, number, and special character.",
            "phone": phone
        })
    if db.users.find_one({"username": username}):
        return templates.TemplateResponse("register.html", {"request": request, "error": "User exists"})
    if phone and db.users.find_one({"phone": phone}):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Phone already registered"})
    
    hashed = password_manager.hash_password(password)
    user_role = role if role in ["patient", "doctor", "admin"] else "patient"
    db.users.insert_one({
        "username": username,
        "password": hashed,
        "name": name,
        "role": user_role,
        "phone": phone,
        "doctor_specialty": doctor_specialty if user_role == "doctor" else "",
        "doctor_degree": doctor_degree if user_role == "doctor" else "",
        "doctor_id": doctor_id if user_role == "doctor" else ""
    })
    # if doctor register, add to doctor collection with approval flag
    if user_role == "doctor":
        try:
            db.doctors.insert_one({
                "name": name,
                "specialty": doctor_specialty,
                "degree": doctor_degree,
                "registration_id": doctor_id,
                "approved": False,
                # additional fields can be added later via profile
            })
        except Exception:
            pass

    request.session["user"] = username
    request.session["role"] = user_role
    request.session["name"] = name
    request.session["phone"] = phone
    request.session["otp_verified"] = False
    return RedirectResponse(url='/', status_code=303)


@app.get("/register/phone")
def register_phone_get(request: Request):
    # Reset OTP verification for fresh registration
    request.session["otp_verified"] = False
    request.session.pop("phone", None)
    return templates.TemplateResponse("register_phone.html", {"request": request})


@app.post("/register/phone")
def register_phone_post(request: Request, phone: str = Form(...)):
    if db is None:
        return templates.TemplateResponse("register_phone.html", {"request": request, "error": "DB not available"})
    if not is_valid_phone(phone):
        return templates.TemplateResponse("register_phone.html", {
            "request": request,
            "error": "Enter a valid phone number in format +91XXXXXXXXXX",
            "phone": phone
        })
    if phone and db.users.find_one({"phone": phone}):
        return templates.TemplateResponse("register_phone.html", {"request": request, "error": "Phone already registered"})
    otp = generate_otp()
    save_otp(phone, otp, "register")
    sent = send_sms_via_twilio(phone, f"Your Swasthya OTP for registration is {otp}. Valid for 5 minutes.")
    if not sent:
        logger.warning("Register OTP SMS failed for %s", phone)
        return templates.TemplateResponse("register_phone.html", {
            "request": request,
            "error": "SMS delivery failed. Please verify your number and try again.",
            "phone": phone
        })
    request.session["phone"] = phone
    return RedirectResponse(url="/register/otp", status_code=303)


@app.get("/register/otp")
def register_otp_get(request: Request):
    if not request.session.get("phone"):
        return RedirectResponse(url="/register/phone", status_code=303)
    return templates.TemplateResponse("register_otp.html", {"request": request, "phone": request.session.get("phone")})


@app.post("/register/otp")
def register_otp_verify(request: Request, otp: str = Form(...)):
    phone = request.session.get("phone")
    if not phone:
        return RedirectResponse(url="/register/phone", status_code=303)
    if not verify_otp(phone, otp):
        return templates.TemplateResponse("register_otp.html", {"request": request, "error": "Invalid or expired OTP", "phone": phone})
    request.session["otp_verified"] = True
    return RedirectResponse(url="/register", status_code=303)


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
    
    # Only show this patient's appointments
    if db is None:
        appointments = []
    else:
        patient_name = request.session.get("name", user)
        appointments = [oid_to_str(d) for d in db.appointments.find({
            "$or": [
                {"patient_username": user},
                {"patient_name": patient_name},
                {"patient_name": user}
            ]
        }).sort("date", 1)]

    # Follow-up alert from latest visit
    followup_alert = None
    try:
        visits = patient.get("visits", []) if patient else []
        if visits:
            latest = sorted(visits, key=lambda v: v.get("date", ""), reverse=True)[0]
            fdays = latest.get("followup_days")
            if fdays is not None:
                # Parse visit date
                vdate_raw = latest.get("date", "")
                vdate = None
                try:
                    vdate = datetime.fromisoformat(vdate_raw).date()
                except Exception:
                    try:
                        vdate = datetime.strptime(vdate_raw[:10], "%Y-%m-%d").date()
                    except Exception:
                        vdate = None
                if vdate:
                    due = vdate + timedelta(days=int(fdays))
                    today = datetime.utcnow().date()
                    if today <= due:
                        days_left = (due - today).days
                        followup_alert = {
                            "days_left": days_left,
                            "due_date": due.strftime("%Y-%m-%d"),
                            "doctor": latest.get("doctor", "Doctor")
                        }
    except Exception:
        followup_alert = None

    return templates.TemplateResponse("patient_dashboard.html", {
        "request": request,
        "user": user,
        "role": role,
        "patient": patient,
        "appointments": appointments,
        "followup_alert": followup_alert
    })


@app.get("/patient/records")
def patient_records(request: Request, msg: str = None):
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
        "patient": patient,
        "success": True if msg == "uploaded" else False
    })


@app.get("/patient/add-report")
def add_report_get(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)

    return templates.TemplateResponse("patient_add_medical_report.html", {
        "request": request,
        "success": False
    })


@app.post("/patient/add-report")
async def add_report_post(request: Request, report_file: UploadFile = File(...)):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)

    # Save file under static uploads for access
    report_dir = os.path.join(uploads_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{report_file.filename}"
    file_path = os.path.join(report_dir, stored_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(report_file.file, f)

    # Try to extract metrics from report text (txt/pdf)
    extracted = {}
    try:
        if report_file.filename.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as rf:
                text_raw = rf.read()
                extracted = _extract_metrics_from_text(text_raw)
                logger.info("add-report txt parsed len=%s extracted=%s", len(text_raw), extracted)
        elif report_file.filename.lower().endswith(".pdf"):
            text = ""
            # Try PyPDF2 first
            try:
                import PyPDF2  # optional dependency
                text_parts = []
                with open(file_path, "rb") as rf:
                    reader = PyPDF2.PdfReader(rf)
                    for page in reader.pages:
                        text_parts.append(page.extract_text() or "")
                text = " ".join(text_parts)
            except Exception:
                text = ""

            # Fallback to pdfminer.six if available
            if not text.strip():
                try:
                    from pdfminer.high_level import extract_text  # optional dependency
                    text = extract_text(file_path) or ""
                except Exception:
                    text = ""

            # OCR fallback for scanned PDFs
            if not text.strip():
                text = _ocr_text_from_pdf_path(file_path)

            extracted = _extract_metrics_from_text(text)
            if not extracted and text:
                logger.info("add-report pdf text sample=%s", text[:500])
            logger.info("add-report pdf parsed len=%s extracted=%s", len(text), extracted)
        elif report_file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            text = _ocr_text_from_image_path(file_path)
            extracted = _extract_metrics_from_text(text)
            logger.info("add-report image parsed len=%s extracted=%s", len(text), extracted)
    except Exception:
        extracted = {}
        logger.exception("add-report parsing failed")

    # Build patient payload for AI analysis
    patient = db.users.find_one({"username": user})
    patient = oid_to_str(patient) if patient else {}
    patient_payload = {
        "age": patient.get("age", 0),
        "blood_pressure": extracted.get("blood_pressure", patient.get("blood_pressure", 0)),
        "sugar_level": extracted.get("sugar_level", patient.get("sugar_level", 0)),
        "cholesterol": extracted.get("cholesterol", patient.get("cholesterol", 0)),
        "bmi": extracted.get("bmi", patient.get("bmi", 0)),
        "symptoms": extracted.get("symptoms", patient.get("symptoms", [])),
        "filename": report_file.filename,
    }

    analysis = analyze_health_ai(patient_payload) or {}
    logger.info("add-report analysis risk_score=%s risk_level=%s", analysis.get("risk_score"), analysis.get("risk_level"))

    # Save in MongoDB
    db.users.update_one(
        {"username": user},
        {
            "$push": {
                "reports": {
                    "filename": report_file.filename,
                    "stored_name": stored_name,
                    "path": f"/static/uploads/reports/{stored_name}",
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "analysis": analysis,
                }
            }
        },
    )

    # Optionally update patient vitals if extracted
    if extracted:
        update_data = {}
        for k in ["blood_pressure", "sugar_level", "cholesterol", "bmi", "symptoms"]:
            if k in extracted:
                update_data[k] = extracted[k]
        if update_data:
            db.users.update_one({"username": user}, {"$set": update_data})

    # Health warning SMS for high risk
    try:
        if analysis.get("risk_level") == "High":
            u = db.users.find_one({"username": user})
            phone = u.get("phone") if u else None
            _send_sms_safe(phone, "Health warning: High risk detected in your latest report. Please consult a doctor.")
    except Exception:
        pass

    return RedirectResponse(
        url="/patient/records?msg=uploaded",
        status_code=303
    )


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
        public_url = f"https://ai-qr-healthcare.onrender.com/p/{profile.get('_id')}"
        public_link = f"https://ai-qr-healthcare.onrender.com/"

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
                      emergency_contact: str = Form(""),
                      blood_pressure: Optional[int] = Form(None),
                      sugar_level: Optional[int] = Form(None),
                      cholesterol: Optional[int] = Form(None),
                      bmi: Optional[float] = Form(None),
                      symptoms: str = Form("")):  # comma separated
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role != "patient":
        return RedirectResponse(url='/login', status_code=303)
    
    if db is None:
        return RedirectResponse(url='/patient/edit-profile', status_code=303)

    if not is_valid_contact(contact) or not is_valid_contact(emergency_contact):
        patient = db.users.find_one({"username": user})
        patient = oid_to_str(patient) if patient else {}
        return templates.TemplateResponse("patient_edit_profile.html", {
            "request": request,
            "user": user,
            "patient": patient,
            "success": False,
            "error": "Please enter valid contact numbers (digits or +countrycode)."
        })
    
    # Prepare update dictionary
    update_data = {
        "name": name,
        "email": email,
        "age": age,
        "contact": contact,
        "blood_group": blood_group,
        "address": address,
        "emergency_contact": emergency_contact,
        "blood_pressure": blood_pressure,
        "sugar_level": sugar_level,
        "cholesterol": cholesterol,
        "bmi": bmi,
        "symptoms": [s.strip() for s in symptoms.split(",")] if symptoms else []
    }
    
    db.users.update_one({"username": user}, {"$set": update_data})
    
    # Fetch updated patient
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

    if not is_valid_contact(contact):
        request.session['settings_msg'] = "Please enter a valid contact number."
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
                  notes: str = Form(""),
                  followup_days: Optional[int] = Form(None)):
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
            "followup_days": followup_days,
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
        appointments = []
        doctors_list = []
        patients_list = []
    else:
        if role == "doctor":
            doc = db.users.find_one({"username": user})
            doctor_name = (doc or {}).get("name", user)
            appointments = [oid_to_str(d) for d in db.appointments.find({"doctor_name": doctor_name}).sort("date", 1)]
            patient_names = list({a.get("patient_name") for a in appointments if a.get("patient_name")})
            if patient_names:
                patients_list = [oid_to_str(d) for d in db.users.find({
                    "role": "patient",
                    "$or": [
                        {"name": {"$in": patient_names}},
                        {"username": {"$in": patient_names}}
                    ]
                }).limit(100)]
            else:
                patients_list = []
        else:
            appointments = [oid_to_str(d) for d in db.appointments.find().limit(50)]
            patients_list = [oid_to_str(d) for d in db.users.find({"role": "patient"}).limit(100)]

        # doctor panel should show all registered/approved doctors
        doctors_list = [oid_to_str(d) for d in db.doctors.find({"approved": True}).limit(50)]
    
    return templates.TemplateResponse("doctor_dashboard.html", {
        "request": request,
        "user": user,
        "role": role,
        "patients": patients_list,
        "appointments": appointments,
        "doctors": doctors_list
    })


@app.post("/doctor/appointments/{appointment_id}/accept")
def doctor_accept_appointment(request: Request, appointment_id: str):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    try:
        oid = ObjectId(appointment_id)
    except Exception:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)

    if db is not None:
        db.appointments.update_one({"_id": oid}, {"$set": {"status": "accepted"}})
    return RedirectResponse(url='/doctor/dashboard', status_code=303)


@app.post("/doctor/appointments/{appointment_id}/reject")
def doctor_reject_appointment(request: Request, appointment_id: str):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    try:
        oid = ObjectId(appointment_id)
    except Exception:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)

    if db is not None:
        db.appointments.update_one({"_id": oid}, {"$set": {"status": "rejected"}})
    return RedirectResponse(url='/doctor/dashboard', status_code=303)


@app.post("/doctor/appointments/{appointment_id}/reschedule")
def doctor_reschedule_appointment(
    request: Request,
    appointment_id: str,
    appointment_date: str = Form(...),
    time: str = Form(...),
):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    try:
        oid = ObjectId(appointment_id)
    except Exception:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)

    if db is not None:
        # Ensure doctor can only edit their own appointments
        if role == "doctor":
            doc = db.users.find_one({"username": user})
            doctor_name = (doc or {}).get("name", user)
            db.appointments.update_one(
                {"_id": oid, "doctor_name": doctor_name},
                {"$set": {"date": appointment_date, "time": time, "status": "rescheduled"}},
            )
        else:
            db.appointments.update_one(
                {"_id": oid},
                {"$set": {"date": appointment_date, "time": time, "status": "rescheduled"}},
            )
        # Notify patient via SMS if phone exists
        try:
            appt = db.appointments.find_one({"_id": oid})
            patient_phone = None
            if appt:
                if appt.get("patient_username"):
                    u = db.users.find_one({"username": appt.get("patient_username")})
                    patient_phone = u.get("phone") if u else None
                if not patient_phone and appt.get("patient_name"):
                    u = db.users.find_one({"name": appt.get("patient_name")})
                    patient_phone = u.get("phone") if u else None
            if patient_phone:
                send_sms_via_twilio(
                    patient_phone,
                    f"Your appointment has been rescheduled to {appointment_date} at {time}."
                )
        except Exception:
            pass
    return RedirectResponse(url='/doctor/dashboard', status_code=303)


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
                    notes: str = Form(""), followup_days: Optional[int] = Form(None)):
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
            "notes": notes,
            "followup_days": followup_days
        }
        db.users.update_one({"_id": pid}, {"$push": {"visits": visit}})
        # SMS follow-up alert to patient's phone (if set)
        try:
            if followup_days is not None:
                p = db.users.find_one({"_id": pid})
                phone = p.get("phone") if p else None
                if phone:
                    send_sms_via_twilio(
                        phone,
                        f"Follow-up reminder: Please visit after {int(followup_days)} days."
                    )
        except Exception:
            pass
    except:
        pass
    
    return RedirectResponse(url=f'/doctor/patient/{patient_id}', status_code=303)


@app.post("/doctor/upload-report")
def doctor_upload_report(request: Request, patient_id: str = Form(...), file: UploadFile = File(...)):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user or role not in ["doctor", "admin"]:
        return RedirectResponse(url='/login', status_code=303)
    if db is None:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)
    try:
        pid = ObjectId(patient_id)
    except Exception:
        return RedirectResponse(url='/doctor/dashboard', status_code=303)

    report_dir = os.path.join(uploads_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(report_dir, stored_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    meta = {
        "filename": file.filename,
        "stored_name": stored_name,
        "path": f"/static/uploads/reports/{stored_name}",
        "uploaded_by": user,
        "uploaded_at": datetime.utcnow().isoformat()
    }
    db.users.update_one({"_id": pid}, {"$push": {"reports": meta}})

    return RedirectResponse(url=f'/doctor/patient/{patient_id}', status_code=303)


# ===== ADMIN ROUTES =====
@app.get("/admin/dashboard")
def admin_dashboard(request: Request):
    try:
        user = request.session.get("user")
        role = request.session.get("role")
        if not user or role != "admin":
            return RedirectResponse(url='/login', status_code=303)

        stats = {"patients": 0, "doctors": 0, "appointments": 0, "pending_doctors": 0}
        if db is not None:
            try:
                stats = {
                    "patients": db.users.count_documents({"role": "patient"}),
                    "doctors": db.users.count_documents({"role": "doctor"}),
                    "appointments": db.appointments.count_documents({}),
                    "pending_doctors": db.doctors.count_documents({"approved": False})
                }
            except Exception:
                logger.exception("admin dashboard stats query failed")

        # debug: indicate template handler was executed (logs before response)
        logger.debug("served admin_dashboard template for user=%s", user)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "user": user,
            "stats": stats,
            "now_str": now_str
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
    if user and role not in ["patient", "doctor", "admin"]:
        role = "patient"
    
    if db is None:
        items = []
        doctors_list = []
    else:
        items = [oid_to_str(d) for d in db.appointments.find().limit(100)]
        approved_docs = [oid_to_str(d) for d in db.doctors.find({"approved": True}).sort("name", 1)]
        approved_names = {d.get("name") for d in approved_docs if d.get("name")}
        if approved_names:
            doctors_list = [oid_to_str(d) for d in db.users.find({
                "role": "doctor",
                "name": {"$in": list(approved_names)}
            }).sort("name", 1)]
            # Fallback to approved_docs if user records not found
            if not doctors_list:
                doctors_list = approved_docs
        else:
            doctors_list = []
    
    return templates.TemplateResponse("appointments.html", {
        "request": request,
        "user": user,
        "role": role,
        "appointments": items,
        "doctors": doctors_list
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
    doctor_display = doctor_name
    doctor_base = doctor_name.split(" - ")[0].strip()
    doctor_username = None
    try:
        doc_user = db.users.find_one({"role": "doctor", "name": doctor_base})
        if doc_user:
            doctor_username = doc_user.get("username")
    except Exception:
        doctor_username = None
    appointment = {
        "patient_username": user,
        "patient_name": patient_name,
        "doctor_name": doctor_base,
        "doctor_display": doctor_display,
        "doctor_username": doctor_username,
        "date": appointment_date,
        "time": time,
        "status": "pending",
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


@app.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(
        "privacy.html",
        {"request": request}
    )

from fastapi import Form
from datetime import datetime

# Contact Page (GET)
@app.get("/contact")
def contact_page(request: Request):
    return templates.TemplateResponse(
        "contact.html",
        {"request": request}
    )


# Contact Form Submit (POST)
@app.post("/contact")
def submit_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...)
):
    db.contacts.insert_one({
        "name": name,
        "email": email,
        "message": message,
        "created_at": datetime.utcnow()
    })

    return templates.TemplateResponse(
        "contact.html",
        {
            "request": request,
            "success": "Message sent successfully!"
        }
    )
@app.get("/admin/contact-messages")
def view_contact_messages(request: Request):

    messages = list(
        db.contacts.find().sort("created_at", -1)
    )

    return templates.TemplateResponse(
        "admin_contact_messages.html",
        {
            "request": request,
            "messages": messages
        }
    )
    
    
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from bson import ObjectId

# Ensure db is already defined: db = client[DATABASE_NAME]

from fastapi.responses import RedirectResponse
from bson import ObjectId
from fastapi import HTTPException, Request

@app.post("/admin/contact/delete/{msg_id}")
async def delete_contact_message(msg_id: str, request: Request):
    # Admin access check
    role = request.session.get("role")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Use same collection as in view
    contact_collection = db.contacts  # Ensure collection name matches view

    # Convert string to ObjectId
    try:
        obj_id = ObjectId(msg_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid message ID")

    # Delete the document
    result = contact_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")

    # Redirect back to contact messages page
    return RedirectResponse(url="/admin/contact-messages", status_code=303)




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


# NOTE: Legacy /register handlers removed to avoid route conflicts.


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
    request.session["phone"] = u.get("phone")
    return RedirectResponse(url='/', status_code=303)


@app.post("/login/otp")
def login_otp_send(request: Request, phone: str = Form(...)):
    if db is None:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DB not available"})
    user = db.users.find_one({"phone": phone})
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Phone not registered"})

    otp = generate_otp()
    save_otp(phone, otp, str(user.get("_id")))
    sent = send_sms_via_twilio(phone, f"Your Swasthya OTP is {otp}. Valid for 5 minutes.")
    if not sent:
        logger.info("OTP for %s is %s (SMS not sent; Twilio not configured)", phone, otp)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "info": "OTP sent to your phone.",
        "phone": phone,
        "otp_sent": True
    })


@app.post("/login/otp/verify")
def login_otp_verify(request: Request, phone: str = Form(...), otp: str = Form(...)):
    rec = verify_otp(phone, otp)
    if not rec:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid or expired OTP", "phone": phone})
    if db is None:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DB not available"})
    user = db.users.find_one({"phone": phone})
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "User not found"})
    request.session["user"] = user.get("username")
    request.session["role"] = user.get("role", "patient")
    request.session["name"] = user.get("name", user.get("username"))
    request.session["phone"] = user.get("phone")
    return RedirectResponse(url='/', status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url='/', status_code=303)


@app.get("/patients")
def patients_view(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    if db is None:
        items = []
    else:
        if role == "patient":
            p = db.users.find_one({"username": user})
            items = [oid_to_str(p)] if p else []
        elif role == "doctor":
            doc = db.users.find_one({"username": user})
            doctor_name = (doc or {}).get("name", user)
            appts = list(db.appointments.find({"doctor_name": doctor_name}))
            patient_names = list({a.get("patient_name") for a in appts if a.get("patient_name")})
            if patient_names:
                items = [oid_to_str(d) for d in db.users.find({
                    "role": "patient",
                    "$or": [
                        {"name": {"$in": patient_names}},
                        {"username": {"$in": patient_names}}
                    ]
                }).limit(100)]
            else:
                items = []
        else:
            items = [oid_to_str(d) for d in db.patients.find().limit(100)]
    return templates.TemplateResponse("patients.html", {"request": request, "user": user, "role": role, "patients": items})


# @app.post("/patients/add")
# def add_patient(request: Request, name: str = Form(...), age: int = Form(...), notes: str = Form("")):
#     user = request.session.get("user")
#     if not user:
#         return RedirectResponse(url='/login', status_code=303)
#     if db is not None:
#         db.patients.insert_one({"name": name, "age": age, "notes": notes})
#     return RedirectResponse(url='/patients', status_code=303)

@app.post("/patients/add")
def add_patient(
    request: Request,
    name: str = Form(...),
    age: int = Form(...),
    contact: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    blood_group: str = Form(""),
    emergency_contact: str = Form(""),
    blood_pressure: int = Form(0),
    sugar_level: int = Form(0),
    cholesterol: int = Form(0),
    bmi: float = Form(0.0),
    symptoms: str = Form(""),
    notes: str = Form("")
):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url='/login', status_code=303)

    patient_data = {
        "name": name,
        "age": age,
        "contact": contact,
        "email": email,
        "address": address,
        "blood_group": blood_group,
        "emergency_contact": emergency_contact,
        "blood_pressure": blood_pressure,
        "sugar_level": sugar_level,
        "cholesterol": cholesterol,
        "bmi": bmi,
        "symptoms": [s.strip() for s in symptoms.split(",")] if symptoms else [],
        "notes": notes
    }

    if db is not None:
        db.patients.insert_one(patient_data)

    return RedirectResponse(url='/patients', status_code=303)
@app.get('/doctors')
def doctors_view(request: Request):
    user = request.session.get('user')
    role = request.session.get("role")
    if db is None:
        docs = []
    else:
        if role == "doctor":
            doc = db.users.find_one({"username": user})
            doc_name = (doc or {}).get("name", user)
            docs = [oid_to_str(d) for d in db.doctors.find({"name": doc_name}).limit(1)]
        elif role == "patient":
            docs = [oid_to_str(d) for d in db.doctors.find({"approved": True}).limit(100)]
        else:
            docs = [oid_to_str(d) for d in db.doctors.find().limit(100)]
    return templates.TemplateResponse('doctors.html', {'request': request, 'user': user, 'role': role, 'doctors': docs})


@app.get('/appointments')
def appointments_view(request: Request):
    user = request.session.get('user')
    role = request.session.get("role")
    if user and role not in ["patient", "doctor", "admin"]:
        role = "patient"
    if db is None:
        items = []
        doctors_list = []
    else:
        if role == "patient":
            patient_name = request.session.get("name", user)
            items = [oid_to_str(d) for d in db.appointments.find({
                "$or": [
                    {"patient_username": user},
                    {"patient_name": patient_name},
                    {"patient_name": user}
                ]
            }).limit(100)]
            # Approved doctors list for booking
            approved_docs = [oid_to_str(d) for d in db.doctors.find({"approved": True}).sort("name", 1)]
            approved_names = {d.get("name") for d in approved_docs if d.get("name")}
            if approved_names:
                doctors_list = [oid_to_str(d) for d in db.users.find({
                    "role": "doctor",
                    "name": {"$in": list(approved_names)}
                }).sort("name", 1)]
                if not doctors_list:
                    doctors_list = approved_docs
            else:
                doctors_list = []
        elif role == "doctor":
            doc = db.users.find_one({"username": user})
            doctor_name = (doc or {}).get("name", user)
            items = [oid_to_str(d) for d in db.appointments.find({
                "$or": [
                    {"doctor_name": doctor_name},
                    {"doctor_display": {"$regex": f"^{re.escape(doctor_name)}(\\s*-|$)"}}
                ]
            }).limit(100)]
            doctors_list = []
        else:
            items = [oid_to_str(d) for d in db.appointments.find().limit(100)]
            doctors_list = [oid_to_str(d) for d in db.doctors.find({"approved": True}).sort("name", 1)]
    return templates.TemplateResponse('appointments.html', {
        'request': request,
        'user': user,
        'role': role,
        'appointments': items,
        'doctors': doctors_list
    })


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
