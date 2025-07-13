#!/usr/bin/env python3
"""
Test script for the Faster Whisper + Pyannote API.
This script tests the API endpoints and demonstrates usage.
"""

import requests
import base64
import json
import time
import os
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "password123"

def get_auth_header():
    """Generate Basic Auth header"""
    credentials = f"{USERNAME}:{PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}

def test_health_check():
    """Test the health check endpoint"""
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

def test_web_interface():
    """Test the web interface"""
    print("🌐 Testing web interface...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print("✅ Web interface accessible")
            return True
        else:
            print(f"❌ Web interface failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Web interface error: {e}")
        return False

def test_audio_processing():
    """Test audio processing with sample file"""
    print("🎤 Testing audio processing...")
    
    # Check if sample.wav exists
    sample_file = Path("sample.wav")
    if not sample_file.exists():
        print("❌ sample.wav not found. Run 'python create_sample_audio.py' first.")
        return False
    
    try:
        # Prepare the request
        files = {"file": ("sample.wav", open(sample_file, "rb"), "audio/wav")}
        data = {
            "language": "en",
            "webhook_url": ""  # No webhook for testing
        }
        headers = get_auth_header()
        
        print("📤 Uploading sample.wav...")
        response = requests.post(
            f"{API_BASE_URL}/process",
            files=files,
            data=data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Audio processing successful!")
            print(f"📊 Processing steps: {len(result.get('processing_steps', {}))} steps")
            print(f"📝 Transcript segments: {len(result.get('transcript_file', {}).get('segments', []))}")
            print(f"👥 Diarization segments: {len(result.get('diarization_file', {}).get('segments', []))}")
            print(f"🔗 Merged segments: {len(result.get('merged_file', {}).get('segments', []))}")
            
            # Save results for inspection
            with open("test_results.json", "w") as f:
                json.dump(result, f, indent=2)
            print("💾 Results saved to test_results.json")
            
            return True
        else:
            print(f"❌ Audio processing failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Audio processing error: {e}")
        return False

def test_webhook():
    """Test webhook functionality"""
    print("📡 Testing webhook functionality...")
    
    # Start a simple webhook server (this is a simplified test)
    print("⚠️  Webhook test requires manual setup:")
    print("1. Start a webhook server: python -m http.server 8080")
    print("2. Run: curl -X POST 'http://localhost:8000/process' \\")
    print("   -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' \\")
    print("   -F 'file=@sample.wav' \\")
    print("   -F 'language=en' \\")
    print("   -F 'webhook_url=http://localhost:8080/webhook'")
    return True

def main():
    """Run all tests"""
    print("🧪 Starting API tests...")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health_check),
        ("Web Interface", test_web_interface),
        ("Audio Processing", test_audio_processing),
        ("Webhook Info", test_webhook),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print("\n📚 Next steps:")
    print("1. Visit http://localhost:8000 for the web interface")
    print("2. Use the API with your own audio files")
    print("3. Check test_results.json for sample output")

if __name__ == "__main__":
    main() 