def suggest_doctor(diseases):
    if "Diabetes" in diseases:
        return "Endocrinologist"
    if "Heart Disease Risk" in diseases:
        return "Cardiologist"
    return "General Physician"