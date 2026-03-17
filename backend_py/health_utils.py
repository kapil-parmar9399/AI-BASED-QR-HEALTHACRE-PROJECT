import os
from fpdf import FPDF

PDF_FOLDER = os.path.join(os.getcwd(), "pdfs")
os.makedirs(PDF_FOLDER, exist_ok=True)

def calculate_risk_percentage(score):
    # Professional, interpretable scaling: 5 points ≈ 50% risk
    return min(100, score * 10)

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

    if sugar > 250:
        score += 6
        emergency = True
        emergency_message = "Critical blood sugar level detected!"
        diseases.append("Severe Diabetes Risk")
        recommendations.append("Immediate medical attention required")

    elif bp > 180:
        score += 6
        emergency = True
        emergency_message = "Hypertensive crisis risk!"
        diseases.append("Severe Blood Pressure Risk")
        recommendations.append("Visit hospital immediately")

    elif sugar > 180:
        score += 4
        diseases.append("Diabetes")
        recommendations.append("Control blood sugar immediately")

    if bp > 140 or cholesterol > 220:
        score += 5
        diseases.append("Heart Disease Risk")
        recommendations.append("Cardiac screening required")

    if "chest pain" in symptoms:
        score += 6
        emergency = True
        emergency_message = "Possible cardiac emergency!"
        diseases.append("Possible Heart Attack")
        recommendations.append("Immediate ECG test required")

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

# Simple doctor, diet, medicine suggestions
def suggest_doctor(diseases):
    return "Dr. Sharma (General Physician)"

def generate_diet(diseases):
    return "Balanced diet with low sugar & low fat"

def suggest_medicine(diseases):
    meds = []
    if "Diabetes" in diseases or "Severe Diabetes Risk" in diseases:
        meds.append("Metformin")
    if "Heart Disease Risk" in diseases or "Possible Heart Attack" in diseases:
        meds.append("Aspirin")
    if "Obesity" in diseases:
        meds.append("Weight management supplements")
    return meds

# UTF-safe PDF generation
def generate_pdf(patient_data: dict, analysis: dict, filename: str = "report.pdf"):
    pdf_path = os.path.join(PDF_FOLDER, filename)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "AI Medical Report", ln=True, align="C")
    pdf.ln(5)

    # Patient Info
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Patient Name: {patient_data.get('name', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Age: {patient_data.get('age', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Gender: {patient_data.get('gender', 'N/A')}", ln=True)
    pdf.ln(5)

    # Risk Info
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Risk Level: {analysis.get('risk_level', 'N/A')}", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Risk Score: {analysis.get('risk_score', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Risk Percentage: {analysis.get('risk_percentage', 0)}%", ln=True)
    pdf.ln(5)

    # Possible Diseases
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Possible Diseases:", ln=True)
    pdf.set_font("Arial", "", 12)
    for disease in analysis.get("possible_diseases", []):
        pdf.cell(0, 8, f"- {disease}", ln=True)
    pdf.ln(3)

    # Recommendations
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Recommendations:", ln=True)
    pdf.set_font("Arial", "", 12)
    for rec in analysis.get("recommendations", []):
        pdf.cell(0, 8, f"- {rec}", ln=True)
    pdf.ln(3)

    # Doctor, Diet, Medicine
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Doctor & Suggestions:", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Suggested Doctor: {analysis.get('doctor', 'N/A')}", ln=True)
    pdf.cell(0, 8, f"Diet Plan: {analysis.get('diet', 'N/A')}", ln=True)
    pdf.cell(0, 8, "Medicine Suggestions:", ln=True)
    for med in analysis.get("medicine", []):
        pdf.cell(0, 8, f"- {med}", ln=True)

    pdf.output(pdf_path)
    return pdf_path
