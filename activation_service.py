"""
Simple remote activation service for the clinical documentation app
"""

from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
VALID_API_KEYS = [
    "clinical_api_key_2025",
    "admin_key_2025",
    "backup_key_2025"
]

# Activation status (can be changed via admin endpoint)
ACTIVATION_STATUS = {
    "active": True,
    "message": "Application is active and licensed",
    "last_updated": datetime.now().isoformat()
}

def validate_api_key(api_key: str) -> bool:
    """Validate API key"""
    return api_key in VALID_API_KEYS

@app.route('/api/check_activation', methods=['GET'])
def check_activation():
    """Check application activation status"""
    try:
        # Get API key from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "error": "Missing or invalid authorization header",
                "active": False
            }), 401
        
        api_key = auth_header.split(' ')[1]
        
        if not validate_api_key(api_key):
            return jsonify({
                "error": "Invalid API key",
                "active": False
            }), 401
        
        # Return activation status
        return jsonify({
            "active": ACTIVATION_STATUS["active"],
            "message": ACTIVATION_STATUS["message"],
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "active": False
        }), 500

@app.route('/api/set_activation', methods=['POST'])
def set_activation():
    """Set application activation status (admin only)"""
    try:
        # Get API key from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "error": "Missing or invalid authorization header"
            }), 401
        
        api_key = auth_header.split(' ')[1]
        
        # Only admin key can change activation status
        if api_key != "admin_key_2025":
            return jsonify({
                "error": "Admin privileges required"
            }), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "No JSON data provided"
            }), 400
        
        # Update activation status
        ACTIVATION_STATUS["active"] = data.get("active", True)
        ACTIVATION_STATUS["message"] = data.get("message", "Status updated by admin")
        ACTIVATION_STATUS["last_updated"] = datetime.now().isoformat()
        
        return jsonify({
            "success": True,
            "message": "Activation status updated",
            "status": ACTIVATION_STATUS
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get API status"""
    return jsonify({
        "service": "Clinical Documentation Activation Service",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200

# Admin endpoints for testing
@app.route('/admin/deactivate', methods=['POST'])
def admin_deactivate():
    """Admin endpoint to deactivate application"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing authorization header"}), 401
        
        api_key = auth_header.split(' ')[1]
        if api_key != "admin_key_2025":
            return jsonify({"error": "Admin privileges required"}), 403
        
        ACTIVATION_STATUS["active"] = False
        ACTIVATION_STATUS["message"] = "Application deactivated by admin"
        ACTIVATION_STATUS["last_updated"] = datetime.now().isoformat()
        
        return jsonify({
            "success": True,
            "message": "Application deactivated",
            "status": ACTIVATION_STATUS
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/activate', methods=['POST'])
def admin_activate():
    """Admin endpoint to activate application"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing authorization header"}), 401
        
        api_key = auth_header.split(' ')[1]
        if api_key != "admin_key_2025":
            return jsonify({"error": "Admin privileges required"}), 403
        
        ACTIVATION_STATUS["active"] = True
        ACTIVATION_STATUS["message"] = "Application activated by admin"
        ACTIVATION_STATUS["last_updated"] = datetime.now().isoformat()
        
        return jsonify({
            "success": True,
            "message": "Application activated",
            "status": ACTIVATION_STATUS
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Clinical Documentation Activation Service")
    print("📋 Available endpoints:")
    print("   GET  /api/check_activation - Check activation status")
    print("   POST /api/set_activation   - Set activation status (admin)")
    print("   GET  /api/status          - Get API status")
    print("   GET  /health              - Health check")
    print("   POST /admin/deactivate    - Deactivate app (admin)")
    print("   POST /admin/activate      - Activate app (admin)")
    print("\n🔑 API Keys:")
    print("   User: clinical_api_key_2025")
    print("   Admin: admin_key_2025")
    print("   Backup: backup_key_2025")
    print("\nService running on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)