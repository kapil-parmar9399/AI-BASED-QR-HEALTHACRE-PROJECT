"""
Security utilities for Swasthya Healthcare System
Includes password hashing, token generation, and security middleware
"""
import bcrypt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import json

class PasswordManager:
    """Handle password hashing and verification"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False


class TokenManager:
    """Generate and validate secure tokens"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_access_token(patient_id: str, expiry_days: int = 7) -> dict:
        """Generate QR access token with expiry"""
        token = TokenManager.generate_token(24)
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=expiry_days)
        
        return {
            "token": token,
            "patient_id": patient_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "expiry_days": expiry_days,
        }
    
    @staticmethod
    def is_token_valid(token_data: dict) -> bool:
        """Check if token is still valid (not expired)"""
        if not token_data:
            return False
        
        expires_at_str = token_data.get("expires_at")
        if not expires_at_str:
            return False
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.utcnow() < expires_at
        except (ValueError, TypeError):
            return False


class SecurityHeaders:
    """Common security headers for responses"""
    
    @staticmethod
    def get_secure_headers() -> dict:
        """Return dictionary of security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }


class AuditLog:
    """Log important security and audit events"""
    
    def __init__(self, db_collection=None):
        self.db_collection = db_collection
    
    def log_event(self, event_type: str, user_id: str, action: str, details: dict = None):
        """Log security event"""
        event = {
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "details": details or {},
            "timestamp": datetime.utcnow(),
            "ip_address": None,  # Should be set from request context
        }
        
        if self.db_collection:
            try:
                self.db_collection.insert_one(event)
            except Exception as e:
                print(f"Error logging event: {e}")
        
        return event
    
    def log_login(self, user_id: str, success: bool, ip_address: str = None):
        """Log login attempt"""
        return self.log_event(
            event_type="authentication",
            user_id=user_id,
            action="login_attempt",
            details={
                "success": success,
                "ip_address": ip_address,
            }
        )
    
    def log_access(self, user_id: str, resource: str, action: str):
        """Log resource access"""
        return self.log_event(
            event_type="access",
            user_id=user_id,
            action=action,
            details={"resource": resource}
        )


class InputValidator:
    """Validate and sanitize user inputs"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Basic phone number validation"""
        import re
        # Accepts formats: +91-9999999999, 09999999999, +919999999999
        pattern = r'^[\+]?[0-9]{1,3}[\s\-]?[0-9]{7,14}$'
        return re.match(pattern, phone.replace(" ", "").replace("-", "")) is not None
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Basic input sanitization"""
        if not text:
            return ""
        # Remove potential script tags and dangerous characters
        dangerous_chars = ['<', '>', '"', "'", ';', '&', '|', '`']
        for char in dangerous_chars:
            text = text.replace(char, '')
        return text.strip()


# Utility functions
password_manager = PasswordManager()
token_manager = TokenManager()
audit_log = AuditLog()
input_validator = InputValidator()
