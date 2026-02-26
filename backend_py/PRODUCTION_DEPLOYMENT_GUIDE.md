# Swasthya Healthcare System - Production Deployment Guide

## ✅ Checklist for Production Deployment

### 1. Environment Configuration

```bash
# Create .env file from template
cp .env.example .env

# Edit .env with production values:
# - Change SECRET_KEY to a strong, random value
# - Set PUBLIC_URL to your domain/IP
# - Configure MONGODB_URI for production database
# - Add email credentials (SMTP)
# - Add Twilio credentials if using SMS
# - Set ENVIRONMENT=production
# - Set LOG_LEVEL=WARNING (or INFO)
```

### 2. Database Setup

```bash
# Backup existing data
python backup.py backup

# List available backups
python backup.py list

# Copy backups to secure location
cp -r backups/ /secure/backup/location/
```

### 3. Dependencies Installation

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

### 4. Security Setup

- [ ] Change `SECRET_KEY` in `.env` to a strong random value
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Verify `HTTPS_ONLY=true` for cookies (in `.env` or code)
- [ ] Configure firewall to allow only required ports (80, 443, 3003)
- [ ] Set up SSL/TLS certificates (use Let's Encrypt via Certbot)
- [ ] Enable CORS only for trusted domains in `config.py`

### 5. Database Security

```python
# In .env
MONGODB_URI=mongodb://user:password@host:port/database
# Enable MongoDB authentication and encryption
```

### 6. Email Configuration

```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password  # Use app password, not gmail password
SENDER_EMAIL=noreply@yourdomain.com
```

### 7. Twilio SMS Setup (Optional)

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890  # Your Twilio number
```

### 8. Run Tests

```bash
# Run comprehensive test suite
python test_comprehensive.py

# All tests should show ✅ PASSED
```

### 9. Production Server Setup (Using Gunicorn)

```bash
# Install Gunicorn (already in requirements.txt)

# Run with Gunicorn (4 workers recommended)
gunicorn -w 4 -b 0.0.0.0:3003 --access-logfile - --error-logfile - main:app

# Or with timeout and other optimizations:
gunicorn \
  -w 4 \
  -b 0.0.0.0:3003 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  main:app
```

### 10. Reverse Proxy Setup (Nginx)

```nginx
# /etc/nginx/sites-available/swasthya
server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://127.0.0.1:3003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 11. Systemd Service Setup (Linux)

```bash
# Create service file
cat > /etc/systemd/system/swasthya.service << EOF
[Unit]
Description=Swasthya Healthcare System
After=network.target MongoDB.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/backend_py
Environment="PATH=/path/to/backend_py/venv/bin"
Environment="ENVIRONMENT=production"
Environment="PUBLIC_URL=https://yourdomain.com"
ExecStart=/path/to/backend_py/venv/bin/gunicorn -w 4 -b 0.0.0.0:3003 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable swasthya
sudo systemctl start swasthya
sudo systemctl status swasthya
```

### 12. Database Backups (Cron Job)

```bash
# Add to crontab (backup daily at 2 AM)
0 2 * * * cd /path/to/backend_py && python backup.py backup >> /var/log/swasthya-backup.log 2>&1

# Cleanup old backups (weekly on Sunday)
0 3 * * 0 cd /path/to/backend_py && python backup.py cleanup >> /var/log/swasthya-backup.log 2>&1
```

### 13. Logging and Monitoring

```bash
# Check application logs
tail -f /path/to/backend_py/logs/app.log

# Monitor system resources
top
ps aux | grep gunicorn
netstat -tulpn | grep 3003

# Check MongoDB connection
mongosh mongodb://user:password@host:port/database
```

### 14. Performance Optimization

- [ ] Enable gzip compression in Nginx
- [ ] Set up caching headers for static files
- [ ] Configure MongoDB indexes for frequently queried fields:

```bash
# Run in MongoDB shell
use swasthya_db

# Create indexes
db.patients.createIndex({ "email": 1 })
db.patients.createIndex({ "user_id": 1 })
db.appointments.createIndex({ "patient_id": 1 })
db.appointments.createIndex({ "date": 1 })
db.users.createIndex({ "email": 1 }, { unique: true })
```

### 15. Health Check Endpoint

```bash
# Test health endpoint
curl http://localhost:3003/api/health

# Expected response (when healthy):
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0",
  "environment": "production",
  "timestamp": "2024-02-26T10:30:45.123456"
}
```

### 16. Admin Operations

```bash
# View configuration
curl http://localhost:3003/api/config/info

# List backups
curl http://localhost:3003/admin/backup/list

# Create backup
curl -X POST http://localhost:3003/admin/backup/create

# Cleanup old backups
curl -X POST http://localhost:3003/admin/backup/cleanup?keep_days=30&keep_count=10
```

---

## Common Issues and Solutions

### MongoDB Connection Fails
- Check MongoDB is running: `systemctl status mongod`
- Verify credentials in `.env`
- Test connection: `mongosh mongodb://...`

### SSL Certificate Issues
- Use Let's Encrypt: `sudo certbot certonly --standalone -d yourdomain.com`
- Renew automatically: `sudo certbot renew --quiet --cron`

### Email Not Sending
- Enable "Less secure apps" (Gmail)
- Or use app-specific password
- Test: `python -c "import smtplib; ..."`

### High Memory Usage
- Reduce Gunicorn workers: `-w 2`
- Enable MongoDB compression
- Configure MongoDB memory cache

### Performance Slow
- Add database indexes (see section 14)
- Use CDN for static files
- Enable caching headers
- Monitor slow queries in MongoDB

---

## Backup and Recovery

### Regular Backups
```bash
# Automatic daily backups
# Set up cron job (see section 12)

# Manual backup
python backup.py backup

# List all backups
python backup.py list

# Restore from backup
python -c "from backup import DatabaseBackup; DatabaseBackup().restore('path/to/backup.json.gz')"
```

---

## Version 1.0.0 Features
- ✅ Patient Registration & Login (Email/Password)
- ✅ Patient Profile Management (Personal & Medical)
- ✅ QR Code Generation with Token-based Access
- ✅ Public Patient View (Mobile-Friendly)
- ✅ Prescription & Visit Management
- ✅ Patient Records Display
- ✅ Email & SMS Notifications (Twilio)
- ✅ Patient Settings (Email/Contact Save)
- ✅ Role-based Dashboards (Patient, Doctor, Admin)
- ✅ Database Backup/Restore
- ✅ Security Headers & CORS
- ✅ Rate Limiting
- ✅ API Documentation (Swagger)
- ✅ Health Check Endpoint
