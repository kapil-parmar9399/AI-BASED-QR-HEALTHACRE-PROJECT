from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def generate_pdf(patient, analysis, filename="report.pdf"):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("AI Medical Report", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"Patient: {patient.get('username')}", styles["Normal"]))
    elements.append(Paragraph(f"Risk Level: {analysis['risk_level']}", styles["Normal"]))
    elements.append(Paragraph(f"Risk %: {analysis['risk_percentage']}%", styles["Normal"]))
    elements.append(Paragraph(f"Diseases: {', '.join(analysis['possible_diseases'])}", styles["Normal"]))

    doc.build(elements)