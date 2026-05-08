"""
Application Activation Management Script
Handles remote activation/deactivation of the entire application
"""

import os
import sys
import requests
import json
from datetime import datetime
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AppActivationManager:
    """Manage application-wide activation/deactivation"""

    def __init__(self, activation_url: str = "http://localhost:5000"):
        self.activation_url = activation_url
        self.user_api_key = (os.environ.get("CLINICAL_API_KEY", "").split(",")[0]).strip()
        self.admin_api_key = os.environ.get("CLINICAL_ADMIN_KEY", "").strip()
        if not self.user_api_key or not self.admin_api_key:
            sys.stderr.write(
                "FATAL: CLINICAL_API_KEY and CLINICAL_ADMIN_KEY must be set "
                "(via environment or .env file). See .env.example.\n"
            )
            sys.exit(1)
    
    def check_activation_service(self) -> bool:
        """Check if activation service is running"""
        try:
            response = requests.get(f"{self.activation_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Activation service is running")
                return True
            else:
                print(f"❌ Activation service returned: {response.status_code}")
                return False
        except requests.ConnectionError:
            print("❌ Cannot connect to activation service")
            print("💡 Start with: python activation_service.py")
            return False
        except Exception as e:
            print(f"❌ Error checking service: {e}")
            return False
    
    def check_app_activation(self) -> Optional[Dict]:
        """Check current application activation status"""
        print("🔍 CHECKING APPLICATION ACTIVATION STATUS")
        print("-" * 50)
        
        try:
            response = requests.get(
                f"{self.activation_url}/api/check_activation",
                headers={'Authorization': f'Bearer {self.user_api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = "🟢 ACTIVE" if data.get('active', False) else "🔴 INACTIVE"
                
                print(f"Application Status: {status}")
                print(f"Message: {data.get('message', 'No message')}")
                print(f"Timestamp: {data.get('timestamp', 'Unknown')}")
                
                return data
            else:
                print(f"❌ Status check failed: {response.status_code}")
                return None
                
        except requests.ConnectionError:
            print("❌ Cannot connect to activation service")
            return None
        except Exception as e:
            print(f"❌ Error checking activation: {e}")
            return None
    
    def deactivate_application(self, reason: str = "Administrative action") -> bool:
        """Deactivate the entire application"""
        print("🔴 DEACTIVATING APPLICATION")
        print("-" * 40)
        
        try:
            response = requests.post(
                f"{self.activation_url}/admin/deactivate",
                headers={'Authorization': f'Bearer {self.admin_api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Application deactivated successfully")
                print(f"   - Status: {data.get('status', {}).get('active', 'Unknown')}")
                print(f"   - Message: {data.get('status', {}).get('message', 'No message')}")
                print(f"   - Updated: {data.get('status', {}).get('last_updated', 'Unknown')}")
                print("\n📋 EFFECTS:")
                print("   - All users will be logged out within 5 minutes")
                print("   - New login attempts will fail")
                print("   - Application will show deactivation message")
                print("   - Local data remains safe")
                
                return True
            else:
                print(f"❌ Deactivation failed: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data.get('error', 'Unknown error')}")
                except:
                    pass
                return False
                
        except requests.ConnectionError:
            print("❌ Cannot connect to activation service")
            return False
        except Exception as e:
            print(f"❌ Error deactivating application: {e}")
            return False
    
    def activate_application(self, message: str = "Application reactivated") -> bool:
        """Activate the entire application"""
        print("🟢 ACTIVATING APPLICATION")
        print("-" * 40)
        
        try:
            response = requests.post(
                f"{self.activation_url}/admin/activate",
                headers={'Authorization': f'Bearer {self.admin_api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Application activated successfully")
                print(f"   - Status: {data.get('status', {}).get('active', 'Unknown')}")
                print(f"   - Message: {data.get('status', {}).get('message', 'No message')}")
                print(f"   - Updated: {data.get('status', {}).get('last_updated', 'Unknown')}")
                print("\n📋 EFFECTS:")
                print("   - Users can login normally")
                print("   - Application functions fully")
                print("   - All features available")
                
                return True
            else:
                print(f"❌ Activation failed: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data.get('error', 'Unknown error')}")
                except:
                    pass
                return False
                
        except requests.ConnectionError:
            print("❌ Cannot connect to activation service")
            return False
        except Exception as e:
            print(f"❌ Error activating application: {e}")
            return False
    
    def set_custom_activation_status(self, active: bool, message: str) -> bool:
        """Set custom activation status with message"""
        status_text = "ACTIVATING" if active else "DEACTIVATING"
        print(f"⚙️ {status_text} APPLICATION WITH CUSTOM MESSAGE")
        print("-" * 50)
        
        try:
            payload = {
                "active": active,
                "message": message
            }
            
            response = requests.post(
                f"{self.activation_url}/api/set_activation",
                headers={'Authorization': f'Bearer {self.admin_api_key}'},
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Custom activation status set successfully")
                print(f"   - Active: {data.get('status', {}).get('active', 'Unknown')}")
                print(f"   - Message: {data.get('status', {}).get('message', 'No message')}")
                
                return True
            else:
                print(f"❌ Failed to set status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error setting custom status: {e}")
            return False
    
    def get_service_info(self) -> Optional[Dict]:
        """Get activation service information"""
        try:
            response = requests.get(f"{self.activation_url}/api/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def interactive_management(self):
        """Interactive application management"""
        print("🏥 CLINICAL DOCUMENTATION AI - APPLICATION ACTIVATION MANAGEMENT")
        print("=" * 70)
        
        # Check service first
        if not self.check_activation_service():
            print("\n❌ Activation service is not running!")
            print("🚀 Start the service with: python activation_service.py")
            return
        
        # Show service info
        service_info = self.get_service_info()
        if service_info:
            print(f"\n📋 Service Info:")
            print(f"   Name: {service_info.get('service', 'Unknown')}")
            print(f"   Version: {service_info.get('version', 'Unknown')}")
            print(f"   Status: {service_info.get('status', 'Unknown')}")
        
        while True:
            print("\n📋 OPTIONS:")
            print("1. Check application status")
            print("2. Deactivate application")
            print("3. Activate application")
            print("4. Set custom status")
            print("5. Test activation service")
            print("6. Exit")
            
            try:
                choice = input("\nEnter choice (1-6): ").strip()
                
                if choice == "1":
                    self.check_app_activation()
                
                elif choice == "2":
                    reason = input("Enter deactivation reason (optional): ").strip()
                    if not reason:
                        reason = "Administrative deactivation"
                    
                    confirm = input(f"⚠️ This will deactivate the ENTIRE application. Continue? (yes/no): ").strip().lower()
                    if confirm == "yes":
                        self.deactivate_application(reason)
                    else:
                        print("❌ Deactivation cancelled")
                
                elif choice == "3":
                    message = input("Enter activation message (optional): ").strip()
                    if not message:
                        message = "Application reactivated by administrator"
                    
                    self.activate_application(message)
                
                elif choice == "4":
                    status_input = input("Activate or deactivate? (a/d): ").strip().lower()
                    if status_input in ['a', 'activate']:
                        active = True
                    elif status_input in ['d', 'deactivate']:
                        active = False
                    else:
                        print("❌ Invalid choice")
                        continue
                    
                    message = input("Enter custom message: ").strip()
                    if message:
                        self.set_custom_activation_status(active, message)
                    else:
                        print("❌ Message is required")
                
                elif choice == "5":
                    self.check_activation_service()
                
                elif choice == "6":
                    print("👋 Goodbye!")
                    break
                
                else:
                    print("❌ Invalid choice")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    """Main function"""
    manager = AppActivationManager()
    manager.interactive_management()

if __name__ == "__main__":
    main()