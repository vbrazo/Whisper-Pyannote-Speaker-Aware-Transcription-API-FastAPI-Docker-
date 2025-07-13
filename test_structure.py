#!/usr/bin/env python3
"""
Test script to verify the new project structure works correctly
"""

def test_imports():
    """Test that all modules can be imported correctly"""
    try:
        # Test core imports
        from app.core.config import settings
        print("✅ Core config imported successfully")
        
        from app.core.security import verify_password, get_password_hash
        print("✅ Core security imported successfully")
        
        # Test database imports
        from app.db.models import User, Job, WebhookLog
        print("✅ Database models imported successfully")
        
        from app.db.database import get_db, init_db
        print("✅ Database utilities imported successfully")
        
        from app.db.schemas import User as UserSchema, Job as JobSchema
        print("✅ Database schemas imported successfully")
        
        # Test services imports
        from app.services.whisper import transcribe_audio
        print("✅ Whisper service imported successfully")
        
        from app.services.diarize import diarize_speakers
        print("✅ Diarization service imported successfully")
        
        from app.services.merge import merge_transcript_and_diarization
        print("✅ Merge service imported successfully")
        
        # Test API imports
        from app.api.process import router as process_router
        print("✅ Process API imported successfully")
        
        from app.api.admin import router as admin_router
        print("✅ Admin API imported successfully")
        
        from app.api.auth import router as auth_router
        print("✅ Auth API imported successfully")
        
        # Test main app
        from app.main import app
        print("✅ Main app imported successfully")
        
        print("\n🎉 All imports successful! The new structure is working correctly.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing new project structure...")
    success = test_imports()
    if success:
        print("\n✅ Structure test passed!")
    else:
        print("\n❌ Structure test failed!")
        exit(1) 