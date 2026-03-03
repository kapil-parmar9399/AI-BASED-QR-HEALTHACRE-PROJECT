def generate_diet(diseases):
    if "Diabetes" in diseases:
        return "Low sugar diet, high fiber food"
    if "Obesity" in diseases:
        return "Low carb diet, calorie deficit plan"
    return "Balanced diet with vegetables and protein"