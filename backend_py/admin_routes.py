"""
Advanced admin dashboard with analytics and statistics
"""
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timedelta
from typing import Dict, List

router = APIRouter(prefix="/admin", tags=["admin"])

def get_admin_router(db):
    """Create admin routes with database access"""
    
    # NOTE: the primary HTML dashboard lives in `main.py` at `/admin/dashboard`.
    # this router serves a JSON data endpoint used by tests or API clients.  the
    # old path conflicted with the template route once the router was included
    # (FastAPI would register the router later and override the earlier handler,
    # causing browsers to see raw JSON instead of the rendered dashboard).  use a
    # distinct path (`/admin/stats`) and update documentation/tests accordingly.
    @router.get("/stats")
    def admin_stats(request: Request):
        """Return admin statistics as JSON"""
        user = request.session.get('user')
        role = request.session.get('role')
        
        if role != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Calculate statistics
        total_patients = db.patients.count_documents({})
        total_doctors = db.doctors.count_documents({})
        total_users = db.users.count_documents({})
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_visits = db.appointments.count_documents({"date": {"$gte": week_ago.isoformat()}})
        
        # Get recent patients
        recent_patients = list(db.patients.find().sort("_id", -1).limit(10))
        recent_patients = [{"id": str(p["_id"]), "name": p.get("name"), "created": p.get("created_at")} for p in recent_patients]
        
        # Top doctors (by appointment count)
        top_doctors = db.appointments.aggregate([
            {"$group": {"_id": "$doctor_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ])
        top_doctors = list(top_doctors)
        
        stats = {
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_users": total_users,
            "recent_visits_week": recent_visits,
            "recent_patients": recent_patients,
            "top_doctors": top_doctors,
        }
        
        return stats
    
    @router.get("/analytics")
    def admin_analytics(request: Request):
        """Detailed analytics and reports"""
        user = request.session.get('user')
        role = request.session.get('role')
        
        if role != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Patient growth (monthly)
        patients_by_month = db.patients.aggregate([
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}}, "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
            {"$limit": 12}
        ])
        
        # Doctor statistics
        doctors_stats = db.doctors.aggregate([
            {"$group": {
                "_id": "$specialty",
                "count": {"$sum": 1},
                "avg_rating": {"$avg": "$rating"}
            }},
            {"$sort": {"count": -1}}
        ])
        
        # Appointment statistics
        appointments_today = db.appointments.count_documents({
            "date": datetime.utcnow().date().isoformat()
        })
        
        return {
            "patient_growth": list(patients_by_month),
            "doctor_stats": list(doctors_stats),
            "appointments_today": appointments_today,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @router.get("/users")
    def list_all_users(request: Request):
        """List all users with filtering"""
        user = request.session.get('user')
        role = request.session.get('role')
        
        if role != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        users = list(db.users.find({}, {"password": 0}).limit(100))
        return [{"id": str(u["_id"]), "username": u.get("username"), "role": u.get("role")} for u in users]
    
    return router
