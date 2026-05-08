"""
Simple remote activation service for the clinical documentation app

API keys are read from environment variables (or a local .env file). The
service refuses to start if CLINICAL_API_KEY or CLINICAL_ADMIN_KEY is missing.
Generate keys with:  python -c "import secrets; print(secrets.token_hex(32))"
"""

from flask import Flask, request, jsonify
import os
import sys
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional at runtime; env vars work either way.
    pass

app = Flask(__name__)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.stderr.write(
            f"FATAL: environment variable {name} is not set.\n"
            f"Generate one with:  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            f"Then export {name}=<value> or add it to a .env file in this directory.\n"
        )
        sys.exit(1)
    return value


# User key may be a single value or a comma-separated list of valid keys.
_user_keys_raw = _require_env("CLINICAL_API_KEY")
VALID_API_KEYS = [k.strip() for k in _user_keys_raw.split(",") if k.strip()]
ADMIN_KEY = _require_env("CLINICAL_ADMIN_KEY")

# Activation status (in-memory; resets on service restart)
ACTIVATION_STATUS = {
    "active": True,
    "message": "Application is active and licensed",
    "last_updated": datetime.now().isoformat(),
}


def _extract_bearer(req) -> str:
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    return auth_header.split(" ", 1)[1].strip()


def validate_api_key(api_key: str) -> bool:
    return api_key in VALID_API_KEYS


@app.route("/api/check_activation", methods=["GET"])
def check_activation():
    """Check application activation status"""
    try:
        api_key = _extract_bearer(request)
        if not api_key:
            return jsonify({"error": "Missing or invalid authorization header", "active": False}), 401

        if not validate_api_key(api_key):
            return jsonify({"error": "Invalid API key", "active": False}), 401

        return jsonify({
            "active": ACTIVATION_STATUS["active"],
            "message": ACTIVATION_STATUS["message"],
            "timestamp": datetime.now().isoformat(),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e), "active": False}), 500


@app.route("/api/set_activation", methods=["POST"])
def set_activation():
    """Set application activation status (admin only)"""
    try:
        api_key = _extract_bearer(request)
        if not api_key:
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        if api_key != ADMIN_KEY:
            return jsonify({"error": "Admin privileges required"}), 403

        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        ACTIVATION_STATUS["active"] = data.get("active", True)
        ACTIVATION_STATUS["message"] = data.get("message", "Status updated by admin")
        ACTIVATION_STATUS["last_updated"] = datetime.now().isoformat()

        return jsonify({
            "success": True,
            "message": "Activation status updated",
            "status": ACTIVATION_STATUS,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def api_status():
    """Get API status"""
    return jsonify({
        "service": "Clinical Documentation Activation Service",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }), 200


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


@app.route("/admin/deactivate", methods=["POST"])
def admin_deactivate():
    """Admin endpoint to deactivate application"""
    try:
        api_key = _extract_bearer(request)
        if not api_key:
            return jsonify({"error": "Missing authorization header"}), 401
        if api_key != ADMIN_KEY:
            return jsonify({"error": "Admin privileges required"}), 403

        ACTIVATION_STATUS["active"] = False
        ACTIVATION_STATUS["message"] = "Application deactivated by admin"
        ACTIVATION_STATUS["last_updated"] = datetime.now().isoformat()

        return jsonify({
            "success": True,
            "message": "Application deactivated",
            "status": ACTIVATION_STATUS,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/activate", methods=["POST"])
def admin_activate():
    """Admin endpoint to activate application"""
    try:
        api_key = _extract_bearer(request)
        if not api_key:
            return jsonify({"error": "Missing authorization header"}), 401
        if api_key != ADMIN_KEY:
            return jsonify({"error": "Admin privileges required"}), 403

        ACTIVATION_STATUS["active"] = True
        ACTIVATION_STATUS["message"] = "Application activated by admin"
        ACTIVATION_STATUS["last_updated"] = datetime.now().isoformat()

        return jsonify({
            "success": True,
            "message": "Application activated",
            "status": ACTIVATION_STATUS,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("Starting Clinical Documentation Activation Service")
    print("Endpoints:")
    print("   GET  /api/check_activation")
    print("   POST /api/set_activation   (admin)")
    print("   GET  /api/status")
    print("   GET  /health")
    print("   POST /admin/deactivate     (admin)")
    print("   POST /admin/activate       (admin)")
    print(f"Loaded {len(VALID_API_KEYS)} user key(s); admin key configured.")
    print("Service running on http://localhost:5000")

    debug_flag = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_flag, host="127.0.0.1", port=5000)
