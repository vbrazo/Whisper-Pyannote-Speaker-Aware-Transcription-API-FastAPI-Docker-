#!/usr/bin/env python3
"""
Test script for the upgraded Whisper + Pyannote API with authentication.
This script tests the new authentication system and admin features.
"""

import requests
import json
import time
import os
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "password123"

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False
    
    def login(self):
        """Login with test credentials"""
        print("🔐 Testing login...")
        try:
            # First get the login page to establish session
            response = self.session.get(f"{API_BASE_URL}/login")
            if response.status_code != 200:
                print(f"❌ Failed to access login page: {response.status_code}")
                return False
            
            # Submit login form
            login_data = {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            
            response = self.session.post(f"{API_BASE_URL}/login", data=login_data)
            
            if response.status_code == 302:  # Redirect after successful login
                print("✅ Login successful")
                self.logged_in = True
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def test_main_page(self):
        """Test access to main page"""
        print("🌐 Testing main page access...")
        try:
            response = self.session.get(f"{API_BASE_URL}/")
            if response.status_code == 200:
                print("✅ Main page accessible")
                return True
            else:
                print(f"❌ Main page failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Main page error: {e}")
            return False
    
    def test_admin_dashboard(self):
        """Test admin dashboard access"""
        print("📊 Testing admin dashboard...")
        try:
            response = self.session.get(f"{API_BASE_URL}/admin")
            if response.status_code == 200:
                print("✅ Admin dashboard accessible")
                return True
            else:
                print(f"❌ Admin dashboard failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Admin dashboard error: {e}")
            return False
    
    def test_admin_api(self):
        """Test admin API endpoints"""
        print("🔧 Testing admin API endpoints...")
        
        # Test stats endpoint
        try:
            response = self.session.get(f"{API_BASE_URL}/admin/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Admin stats: {stats}")
            else:
                print(f"❌ Admin stats failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Admin stats error: {e}")
        
        # Test jobs endpoint
        try:
            response = self.session.get(f"{API_BASE_URL}/admin/jobs")
            if response.status_code == 200:
                jobs_data = response.json()
                print(f"✅ Admin jobs: {jobs_data['total']} total jobs")
            else:
                print(f"❌ Admin jobs failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Admin jobs error: {e}")
    
    def test_audio_processing(self):
        """Test audio processing with authentication"""
        print("🎤 Testing authenticated audio processing...")
        
        # Check if sample.wav exists
        sample_file = Path("sample.wav")
        if not sample_file.exists():
            print("❌ sample.wav not found. Run 'python create_sample_audio.py' first.")
            return False
        
        try:
            # Prepare the request
            files = {"file": open(sample_file, "rb")}
            data = {
                "language": "en",
                "webhook_url": ""  # No webhook for testing
            }
            
            print("📤 Uploading sample.wav with authentication...")
            response = self.session.post(
                f"{API_BASE_URL}/process",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Audio processing successful!")
                print(f"📊 Job ID: {result.get('job_id')}")
                print(f"📝 Transcript segments: {len(result.get('transcript_file', {}).get('segments', []))}")
                print(f"👥 Diarization segments: {len(result.get('diarization_file', {}).get('segments', []))}")
                print(f"🔗 Merged segments: {len(result.get('merged_file', {}).get('segments', []))}")
                
                # Save results for inspection
                with open("test_auth_results.json", "w") as f:
                    json.dump(result, f, indent=2)
                print("💾 Results saved to test_auth_results.json")
                
                return True
            else:
                print(f"❌ Audio processing failed: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Audio processing error: {e}")
            return False
    
    def test_logout(self):
        """Test logout functionality"""
        print("🚪 Testing logout...")
        try:
            response = self.session.get(f"{API_BASE_URL}/logout")
            if response.status_code == 302:  # Redirect after logout
                print("✅ Logout successful")
                self.logged_in = False
                return True
            else:
                print(f"❌ Logout failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Logout error: {e}")
            return False
    
    def test_health_check(self):
        """Test health check endpoint"""
        print("🏥 Testing health check...")
        try:
            response = requests.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

def main():
    """Run all tests"""
    print("🧪 Starting API tests with authentication...")
    print("=" * 60)
    
    tester = APITester()
    
    tests = [
        ("Health Check", tester.test_health_check),
        ("Login", tester.login),
        ("Main Page", tester.test_main_page),
        ("Admin Dashboard", tester.test_admin_dashboard),
        ("Admin API", tester.test_admin_api),
        ("Audio Processing", tester.test_audio_processing),
        ("Logout", tester.test_logout),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The API with authentication is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print("\n📚 Next steps:")
    print("1. Visit http://localhost:8000/login for the login page")
    print("2. Login with admin@example.com / password123")
    print("3. Access the admin dashboard at /admin")
    print("4. Check test_auth_results.json for sample output")

if __name__ == "__main__":
    main() 