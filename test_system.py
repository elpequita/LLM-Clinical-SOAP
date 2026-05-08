"""
Test script to demonstrate the clinical documentation application functionality
"""

import os
import sys
import requests
import time
import json

def test_activation_service():
    """Test the activation service"""
    print("🔐 Testing Activation Service")
    print("="*40)
    
    activation_url = "http://localhost:5000"
    api_key = (os.environ.get("CLINICAL_API_KEY", "").split(",")[0]).strip()
    admin_key = os.environ.get("CLINICAL_ADMIN_KEY", "").strip()
    if not api_key or not admin_key:
        print("⏭️  Skipping activation tests: CLINICAL_API_KEY/CLINICAL_ADMIN_KEY not set")
        return True
    
    try:
        # Test health endpoint
        response = requests.get(f"{activation_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Activation service is running")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Test activation check
        response = requests.get(
            f"{activation_url}/api/check_activation",
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Activation check successful: {data.get('active', False)}")
        else:
            print(f"❌ Activation check failed: {response.status_code}")
            return False
        
        # Test admin deactivation
        response = requests.post(
            f"{activation_url}/admin/deactivate",
            headers={'Authorization': f'Bearer {admin_key}'},
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ Admin deactivation successful")
        else:
            print(f"❌ Admin deactivation failed: {response.status_code}")
        
        # Test admin reactivation
        response = requests.post(
            f"{activation_url}/admin/activate",
            headers={'Authorization': f'Bearer {admin_key}'},
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ Admin reactivation successful")
        else:
            print(f"❌ Admin reactivation failed: {response.status_code}")
        
        return True
        
    except requests.ConnectionError:
        print("❌ Cannot connect to activation service")
        print("💡 Make sure to run: python activation_service.py")
        return False
    except Exception as e:
        print(f"❌ Error testing activation service: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("\n📊 Testing Database Connection")
    print("="*40)
    
    try:
        from db_manager import DatabaseManager
        
        db = DatabaseManager()
        connection = db.get_connection()
        
        if connection and connection.is_connected():
            print("✅ MySQL database connection successful")
            
            # Test getting settings
            api_key = db.get_setting('api_key')
            app_active = db.get_setting('app_active')
            
            print(f"✅ API Key configured: {bool(api_key)}")
            print(f"✅ App active status: {app_active}")
            
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except ImportError:
        print("❌ Database manager not found")
        return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        print("💡 Make sure to run: python setup_mysql.py")
        return False

def test_ollama_connection():
    """Test Ollama connection"""
    print("\n🤖 Testing Ollama Connection")
    print("="*40)
    
    try:
        from llm_utils import check_ollama_status
        
        status = check_ollama_status()
        
        if status['status'] == 'running':
            print("✅ Ollama service is running")
            print(f"✅ Available models: {', '.join(status['models'])}")
            
            if 'gemma4' in status['models']:
                print("✅ gemma4 model is available")
            else:
                print("⚠️ gemma4 model not found")
                print("💡 Run: ollama pull gemma4")
            
            return True
        else:
            print(f"❌ Ollama not running: {status['message']}")
            print("💡 Start Ollama service and pull model:")
            print("   ollama serve")
            print("   ollama pull gemma4")
            return False
            
    except ImportError:
        print("❌ LLM utils not found")
        return False
    except Exception as e:
        print(f"❌ Ollama connection error: {e}")
        return False

def test_audio_dependencies():
    """Test audio processing dependencies"""
    print("\n🎵 Testing Audio Dependencies")
    print("="*40)
    
    # Test PyAudio
    try:
        import pyaudio
        print("✅ PyAudio is available")
        
        # Test audio device access
        audio = pyaudio.PyAudio()
        device_count = audio.get_device_count()
        print(f"✅ Audio devices found: {device_count}")
        audio.terminate()
        
    except ImportError:
        print("❌ PyAudio not installed")
        print("💡 Install with: pip install pyaudio")
        return False
    except Exception as e:
        print(f"⚠️ PyAudio warning: {e}")
    
    # Test Whisper (faster-whisper / CTranslate2)
    try:
        from faster_whisper import WhisperModel
        print("✅ faster-whisper is available")

        # Try loading the configured model. First-run downloads ~800 MB.
        try:
            model = WhisperModel("large-v3-turbo", device="auto", compute_type="int8")
            print("✅ Whisper large-v3-turbo loaded successfully")
        except Exception as e:
            print(f"⚠️ Whisper model loading warning: {e}")
    except ImportError:
        print("❌ faster-whisper not installed")
        print("💡 Install with: pip install faster-whisper")
        return False
    
    # Test Pydub
    try:
        from pydub import AudioSegment
        print("✅ Pydub is available")
    except ImportError:
        print("❌ Pydub not installed")
        print("💡 Install with: pip install pydub")
        return False
    
    return True

def test_gui_dependencies():
    """Test GUI dependencies"""
    print("\n🖥️ Testing GUI Dependencies")
    print("="*40)
    
    try:
        import customtkinter as ctk
        print("✅ CustomTkinter is available")
        
        # Test tkinter
        import tkinter as tk
        print("✅ Tkinter is available")
        
        return True
        
    except ImportError as e:
        print(f"❌ GUI dependency missing: {e}")
        print("💡 Install with: pip install customtkinter")
        return False

def create_test_report():
    """Create a test report"""
    print("\n📋 Test Summary Report")
    print("="*50)
    
    tests = [
        ("Activation Service", test_activation_service),
        ("Database Connection", test_database_connection),
        ("Ollama Connection", test_ollama_connection),
        ("Audio Dependencies", test_audio_dependencies),
        ("GUI Dependencies", test_gui_dependencies),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results[test_name] = False
    
    print("\n📊 Final Results:")
    print("="*30)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The application is ready to use.")
        print("\n📋 To start the application:")
        print("   1. python activation_service.py  # In one terminal")
        print("   2. python clinical_app.py        # In another terminal")
    else:
        print("\n⚠️ Some tests failed. Please address the issues above.")
        print("💡 Check the troubleshooting section in README.md")
    
    return passed == total

def main():
    """Main test function"""
    print("🏥 Clinical Documentation AI - System Test")
    print("==========================================")
    print("This script tests all components of the application")
    print("Make sure you have run the setup scripts first:\n")
    print("1. python install_dependencies.py")
    print("2. python setup_mysql.py")
    print("3. ollama pull gemma4")
    print("4. python activation_service.py (in another terminal)")
    print("\nStarting tests...\n")
    
    # Give user a chance to prepare
    try:
        input("Press Enter to continue or Ctrl+C to exit...")
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        return
    
    # Run tests
    success = create_test_report()
    
    if success:
        print("\n✅ System is ready for use!")
    else:
        print("\n❌ System needs configuration. Check the error messages above.")

if __name__ == "__main__":
    main()