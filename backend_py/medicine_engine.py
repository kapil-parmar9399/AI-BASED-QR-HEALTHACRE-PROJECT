def suggest_medicine(diseases):
    meds = []
    if "Diabetes" in diseases:
        meds.append("Metformin (Doctor prescribed)")
    if "Heart Disease Risk" in diseases:
        meds.append("Aspirin (After consultation)")
    return meds or ["No medication required"]