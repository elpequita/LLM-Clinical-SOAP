"""
Security manager for remote activation and deactivation
"""

import requests
import json
from typing import Dict, Optional
from db_manager import DatabaseManager
import time

class SecurityManager:
    """Handles remote activation and security features"""
    
    def __init__(self, activation_url: str = "http://localhost:5000/api/check_activation"):
        self.activation_url = activation_url
        self.db = DatabaseManager()
        self.last_check = 0
        self.check_interval = 300  # 5 minutes
        self.cached_status = True
    
    def check_activation(self) -> bool:
        """Check if application is activated"""
        current_time = time.time()
        
        # Use cached status if within check interval
        if current_time - self.last_check < self.check_interval:
            return self.cached_status
        
        try:
            # First check local database
            local_status = self.db.get_setting('app_active')
            if local_status and local_status.lower() == 'false':
                self.cached_status = False
                self.last_check = current_time
                return False
            
            # Check remote activation service
            api_key = self.db.get_setting('api_key')
            if not api_key:
                api_key = "clinical_api_key_2025"
            
            response = requests.get(
                self.activation_url,
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                is_active = data.get('active', True)
                
                # Update local database with remote status
                self.db.update_setting('app_active', 'true' if is_active else 'false')
                
                self.cached_status = is_active
                self.last_check = current_time
                return is_active
            else:
                # If remote service is unavailable, use local status
                print(f"Remote activation service unavailable: {response.status_code}")
                self.cached_status = local_status != 'false'
                self.last_check = current_time
                return self.cached_status
                
        except requests.ConnectionError:
            print("Cannot connect to remote activation service")
            # Use local status when remote is unavailable
            local_status = self.db.get_setting('app_active')
            self.cached_status = local_status != 'false'
            self.last_check = current_time
            return self.cached_status
        except requests.Timeout:
            print("Timeout connecting to remote activation service")
            local_status = self.db.get_setting('app_active')
            self.cached_status = local_status != 'false'
            self.last_check = current_time
            return self.cached_status
        except Exception as e:
            print(f"Error checking activation: {e}")
            # Default to active if there's an error
            self.cached_status = True
            self.last_check = current_time
            return True
    
    def deactivate_locally(self) -> bool:
        """Deactivate application locally"""
        try:
            return self.db.update_setting('app_active', 'false')
        except Exception as e:
            print(f"Error deactivating locally: {e}")
            return False
    
    def activate_locally(self) -> bool:
        """Activate application locally"""
        try:
            return self.db.update_setting('app_active', 'true')
        except Exception as e:
            print(f"Error activating locally: {e}")
            return False
    
    def get_activation_status(self) -> Dict:
        """Get detailed activation status"""
        try:
            local_status = self.db.get_setting('app_active')
            api_key = self.db.get_setting('api_key')
            
            status = {
                'local_active': local_status != 'false',
                'api_key_configured': bool(api_key),
                'last_check': self.last_check,
                'check_interval': self.check_interval,
                'cached_status': self.cached_status
            }
            
            # Try to get remote status
            try:
                response = requests.get(
                    self.activation_url,
                    headers={'Authorization': f'Bearer {api_key}'},
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status['remote_active'] = data.get('active', True)
                    status['remote_message'] = data.get('message', '')
                    status['remote_available'] = True
                else:
                    status['remote_available'] = False
                    status['remote_error'] = f"Status code: {response.status_code}"
            except Exception as e:
                status['remote_available'] = False
                status['remote_error'] = str(e)
            
            return status
            
        except Exception as e:
            return {
                'error': str(e),
                'local_active': True,
                'remote_available': False
            }
    
    def update_api_key(self, new_api_key: str) -> bool:
        """Update API key"""
        try:
            return self.db.update_setting('api_key', new_api_key)
        except Exception as e:
            print(f"Error updating API key: {e}")
            return False