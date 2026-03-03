import random

def calculate_risk_percentage(score):
    return min(100, score * 12)

def analyze_health_ai(patient_data: dict) -> dict:
    score = 0
    diseases = []
    recommendations = []
    emergency = False
    emergency_message = ""

    age = patient_data.get("age", 0)
    bp = patient_data.get("blood_pressure", 0)
    sugar = patient_data.get("sugar_level", 0)
    cholesterol = patient_data.get("cholesterol", 0)
    bmi = patient_data.get("bmi", 0)
    symptoms = patient_data.get("symptoms", [])

    # 🔴 CRITICAL SUGAR
    if sugar > 250:
        score += 5
        emergency = True
        emergency_message = "Critical blood sugar level detected!"
        diseases.append("Severe Diabetes Risk")
        recommendations.append("Immediate medical attention required")

    # 🔴 CRITICAL BP
    elif bp > 180:
        score += 5
        emergency = True
        emergency_message = "Hypertensive crisis risk!"
        diseases.append("Severe Blood Pressure Risk")
        recommendations.append("Visit hospital immediately")

    # Diabetes
    elif sugar > 180:
        score += 3
        diseases.append("Diabetes")
        recommendations.append("Control blood sugar immediately")

    # Heart Risk
    if bp > 140 or cholesterol > 220:
        score += 3
        diseases.append("Heart Disease Risk")
        recommendations.append("Cardiac screening required")

    # Chest Pain Emergency
    if "chest pain" in symptoms:
        score += 4
        emergency = True
        emergency_message = "Possible cardiac emergency!"
        diseases.append("Possible Heart Attack")
        recommendations.append("Immediate ECG test required")

    # Obesity
    if bmi > 30:
        score += 2
        diseases.append("Obesity")
        recommendations.append("Weight management plan required")

    risk_percentage = calculate_risk_percentage(score)

    if score >= 8:
        risk_level = "High"
    elif score >= 4:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "risk_score": score,
        "risk_percentage": risk_percentage,
        "risk_level": risk_level,
        "possible_diseases": diseases or ["No major disease"],
        "recommendations": recommendations or ["Maintain healthy lifestyle"],
        "emergency": emergency,
        "emergency_message": emergency_message
    }