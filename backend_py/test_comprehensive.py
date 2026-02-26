"""
Comprehensive end-to-end test suite for Swasthya Healthcare System
Tests all major features: Registration, Profile, QR, Public Access, Prescriptions, Settings
"""
import requests
import json
from datetime import datetime
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:3003"
TEST_EMAIL = f"testuser_{datetime.now().strftime('%Y%m%d%H%M%S')}@test.com"
TEST_PASSWORD = "TestPassword123!"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(name):
    print(f"\n{BLUE}{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}{RESET}")

def print_success(msg):
    print(f"{GREEN}[PASS] {msg}{RESET}")

def print_error(msg):
    print(f"{RED}[FAIL] {msg}{RESET}")

def print_info(msg):
    print(f"{YELLOW}[INFO] {msg}{RESET}")

class SwasthyaTester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.user_data = {}
        self.patient_id = None
        self.token = None
    
    def test_registration(self):
        """Test patient registration"""
        print_test("Patient Registration")
        
        try:
            response = self.session.post(
                urljoin(self.base_url, "/register"),
                data={
                    "username": TEST_EMAIL.split("@")[0],
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "role": "patient",
                }
            )
            
            if response.status_code in [200, 302] or "redirect" in response.text.lower():
                print_success(f"Registration successful - Email: {TEST_EMAIL}")
                self.user_data['email'] = TEST_EMAIL
                self.user_data['password'] = TEST_PASSWORD
                return True
            else:
                print_error(f"Registration failed: {response.status_code}")
                print_info(f"Response: {response.text[:200]}")
                return False
        except Exception as e:
            print_error(f"Registration error: {e}")
            return False
    
    def test_login(self):
        """Test patient login"""
        print_test("Patient Login")
        
        try:
            response = self.session.post(
                urljoin(self.base_url, "/login"),
                data={
                    "email": self.user_data.get('email'),
                    "password": self.user_data.get('password'),
                }
            )
            
            if response.status_code in [200, 302] or "patient" in response.text.lower():
                print_success(f"Login successful")
                return True
            else:
                print_error(f"Login failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Login error: {e}")
            return False
    
    def test_profile_edit(self):
        """Test patient profile editing"""
        print_test("Profile Editing")
        
        try:
            profile_data = {
                "name": "Test Patient",
                "age": "30",
                "blood_group": "O+",
                "medical_history": "Diabetes, Hypertension",
                "allergies": "Penicillin",
                "current_medications": "Insulin, Metformin",
                "emergency_contact": "9876543210",
                "emergency_contact_name": "Emergency Contact",
            }
            
            response = self.session.post(
                urljoin(self.base_url, "/patient/edit-profile"),
                data=profile_data
            )
            
            if response.status_code in [200, 302] or "success" in response.text.lower():
                print_success("Profile edit successful")
                self.user_data.update(profile_data)
                return True
            else:
                print_error(f"Profile edit failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Profile edit error: {e}")
            return False
    
    def test_qr_generation(self):
        """Test QR code generation"""
        print_test("QR Code Generation")
        
        try:
            response = self.session.get(
                urljoin(self.base_url, "/patient/qrcode")
            )
            
            if response.status_code == 200 and ("qrcode" in response.text.lower() or "src=" in response.text):
                print_success("QR code page loaded successfully")
                
                # Try to extract patient ID and token from the page
                if 'data:image' in response.text:
                    print_success("QR image embedded in page")
                
                return True
            else:
                print_error(f"QR generation failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"QR generation error: {e}")
            return False
    
    def test_add_prescription(self):
        """Test adding prescription"""
        print_test("Add Prescription")
        
        try:
            prescription_data = {
                "medicine_name": "Aspirin",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "duration": "7 days",
                "doctor_name": "Dr. Test",
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            
            response = self.session.post(
                urljoin(self.base_url, "/patient/add-prescription"),
                data=prescription_data
            )
            
            if response.status_code in [200, 302] or "success" in response.text.lower():
                print_success("Prescription added successfully")
                return True
            else:
                print_error(f"Prescription add failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Prescription add error: {e}")
            return False
    
    def test_add_visit(self):
        """Test adding visit record"""
        print_test("Add Visit Record")
        
        try:
            visit_data = {
                "doctor_name": "Dr. Test Doctor",
                "clinic_name": "Test Clinic",
                "visit_date": datetime.now().strftime("%Y-%m-%d"),
                "reason": "Routine checkup",
                "notes": "Patient is in good health",
            }
            
            response = self.session.post(
                urljoin(self.base_url, "/patient/add-visit"),
                data=visit_data
            )
            
            if response.status_code in [200, 302] or "success" in response.text.lower():
                print_success("Visit record added successfully")
                return True
            else:
                print_error(f"Visit add failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Visit add error: {e}")
            return False
    
    def test_patient_records(self):
        """Test viewing patient records"""
        print_test("View Patient Records")
        
        try:
            response = self.session.get(
                urljoin(self.base_url, "/patient/records")
            )
            
            if response.status_code == 200:
                print_success("Patient records page loaded")
                
                if "prescription" in response.text.lower() or "visit" in response.text.lower():
                    print_success("Records data visible on page")
                
                return True
            else:
                print_error(f"Records page failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Records page error: {e}")
            return False
    
    def test_patient_settings(self):
        """Test patient settings page"""
        print_test("Patient Settings")
        
        try:
            # GET the settings page
            response = self.session.get(
                urljoin(self.base_url, "/patient/settings")
            )
            
            if response.status_code == 200 and "email" in response.text.lower():
                print_success("Settings page loaded")
                
                # Try to update settings
                settings_data = {
                    "email": TEST_EMAIL,
                    "contact": "9876543210",
                }
                
                response = self.session.post(
                    urljoin(self.base_url, "/patient/settings"),
                    data=settings_data
                )
                
                if response.status_code in [200, 302]:
                    print_success("Settings updated successfully")
                    return True
            
            print_error(f"Settings page failed: {response.status_code}")
            return False
        except Exception as e:
            print_error(f"Settings page error: {e}")
            return False
    
    def test_dashboard(self):
        """Test patient dashboard"""
        print_test("Patient Dashboard")
        
        try:
            response = self.session.get(
                urljoin(self.base_url, "/patient/dashboard")
            )
            
            if response.status_code == 200:
                print_success("Dashboard loaded successfully")
                
                if "patient" in response.text.lower() or "dashboard" in response.text.lower():
                    print_success("Dashboard content visible")
                
                return True
            else:
                print_error(f"Dashboard failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Dashboard error: {e}")
            return False
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        print_test("API Endpoints")
        
        all_passed = True
        
        # Health check
        try:
            response = requests.get(urljoin(self.base_url, "/api/health"))
            if response.status_code in [200, 503]:
                health = response.json()
                print_success(f"Health check: {health.get('status', 'unknown')}")
            else:
                print_error(f"Health check failed: {response.status_code}")
                all_passed = False
        except Exception as e:
            print_error(f"Health check error: {e}")
            all_passed = False
        
        # Config info
        try:
            response = requests.get(urljoin(self.base_url, "/api/config/info"))
            if response.status_code == 200:
                config = response.json()
                print_success(f"Config info: {config.get('app_name', 'Swasthya')}")
            else:
                print_error(f"Config info failed: {response.status_code}")
                all_passed = False
        except Exception as e:
            print_error(f"Config info error: {e}")
            all_passed = False
        
        # List patients API
        try:
            response = requests.get(urljoin(self.base_url, "/api/patients"))
            if response.status_code == 200:
                patients = response.json()
                print_success(f"List patients API: {len(patients)} patients found")
            else:
                print_error(f"List patients API failed: {response.status_code}")
                all_passed = False
        except Exception as e:
            print_error(f"List patients API error: {e}")
            all_passed = False
        
        return all_passed
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"\n{BLUE}{'='*60}")
        print(f"SWASTHYA HEALTHCARE SYSTEM - COMPREHENSIVE TEST SUITE")
        print(f"{'='*60}{RESET}")
        print_info(f"Base URL: {self.base_url}")
        print_info(f"Test Email: {TEST_EMAIL}")
        
        tests = [
            ("Registration", self.test_registration),
            ("Login", self.test_login),
            ("Profile Edit", self.test_profile_edit),
            ("QR Generation", self.test_qr_generation),
            ("Add Prescription", self.test_add_prescription),
            ("Add Visit", self.test_add_visit),
            ("View Records", self.test_patient_records),
            ("Settings", self.test_patient_settings),
            ("Dashboard", self.test_dashboard),
            ("API Endpoints", self.test_api_endpoints),
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                print_error(f"Test error: {e}")
                results[test_name] = False
        
        # Summary
        print(f"\n{BLUE}{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}{RESET}")
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, passed_flag in results.items():
            status = f"{GREEN}[PASS]{RESET}" if passed_flag else f"{RED}[FAIL]{RESET}"
            print(f"{test_name:<30} {status}")
        
        print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}")
        
        if passed == total:
            print(f"{GREEN}SUCCESS: All tests passed!{RESET}")
        elif passed > total / 2:
            print(f"{YELLOW}WARNING: Most tests passed, but some failures{RESET}")
        else:
            print(f"{RED}FAILURE: Many test failures - check configuration{RESET}")
        
        return passed == total


if __name__ == "__main__":
    tester = SwasthyaTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
