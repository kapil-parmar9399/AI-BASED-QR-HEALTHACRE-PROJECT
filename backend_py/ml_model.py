import joblib

def load_model():
    return joblib.load("models/disease_model.pkl")

def predict_disease(model, patient_data):
    features = [[
        patient_data.get("age", 0),
        patient_data.get("blood_pressure", 0),
        patient_data.get("sugar_level", 0),
        patient_data.get("cholesterol", 0),
        patient_data.get("bmi", 0)
    ]]
    return model.predict(features)[0]