# 📝 Personal Information Management Guide

## How to Add/Edit Personal Information in Swasthya

### Step 1: Login to Your Account
- Go to http://127.0.0.1:3001/login
- Enter your username and password
- Click **Sign In**

### Step 2: Access Profile Edit Page
From your **Patient Dashboard**, click the **✏️ Edit Profile** button
OR
Go directly to: http://127.0.0.1:3001/patient/edit-profile

### Step 3: Edit Personal Information
The form has two sections:

#### **Section 1: Personal Information** (Left Column)
Update your:
- **Full Name** - Your complete name
- **Email** - Email address for contact
- **Age** - Your current age
- **Contact Number** - Mobile/phone number (10 digits)
- **Address** - Your residential address
- **Blood Group** - Select from dropdown (O+, O-, A+, A-, B+, B-, AB+, AB-)
- **Emergency Contact** - Contact number for emergencies

Click **💾 Save Personal Information** to update

#### **Section 2: Medical Information** (Right Column)
Update your medical details:
- **Medical History** - Enter conditions separated by commas
  - Example: `Diabetes, Hypertension, Asthma`
  
- **Allergies** - Enter allergies separated by commas
  - Example: `Penicillin, Aspirin, Shellfish`
  
- **Current Medications** - Enter medications separated by commas
  - Example: `Lisinopril 10mg, Metformin 500mg`

Click **💾 Save Medical Information** to update

### Step 4: View Your Information
After saving, you'll see:
- A success message "✓ Information updated successfully!"
- A **Current Medical Summary** section showing your conditions, allergies, and medications with color-coded badges

---

## Features

✅ **Personal Details**
- Name, email, age, contact, address
- Blood group selection
- Emergency contact information

✅ **Medical History**
- Store medical conditions
- Track allergies (critical for safety)
- Document current medications

✅ **Auto-Display**
- Medical history shown as yellow badges
- Allergies shown as red badges
- Medications listed with checkmarks

✅ **Real-Time Updates**
- Changes saved immediately to MongoDB
- Accessible to doctors when viewing your records
- Used in emergency access scenarios

---

## Tips

💡 **Blood Group**: Keep this updated - it's critical for medical emergencies
💡 **Allergies**: This is especially important - doctors will check this before prescribing
💡 **Medications**: List all medications including doses and frequency
💡 **Medical History**: Include chronic conditions and past major illnesses

---

## Example Data

### Good Medical History Entry
```
Hypertension, Type 2 Diabetes, Asthma, Migraine
```

### Good Allergies Entry
```
Penicillin, Sulfonamides, Aspirin, Peanuts
```

### Good Medications Entry
```
Lisinopril 10mg daily, Metformin 500mg twice daily, Albuterol inhaler as needed
```

---

## Next Steps
After updating your information:
1. View your complete medical records: `/patient/records`
2. Check your QR code: `/patient/qrcode`
3. Book appointments: `/appointments`

---

🔒 **Your data is secure and only accessible to authorized medical professionals and in emergency situations.**
