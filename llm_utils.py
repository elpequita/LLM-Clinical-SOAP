"""
LLM utilities for generating SOAP notes using Ollama
"""

import re
import requests
import json
from typing import Dict, Optional

# Per-model cache: once we've verified Ollama is up and the model is loaded
# in this process, skip the /api/tags + /api/pull preflight on subsequent
# calls. Reset for a model when a generate call fails so we re-verify.
_verified_models: set = set()

# Section header → SOAP key mapping. Longer phrases first so "clinical
# impression" wins over "impression" when both could match.
_SOAP_HEADERS = (
    ("clinical impression", "assessment"),
    ("patient reports", "subjective"),
    ("patient states", "subjective"),
    ("physical exam", "objective"),
    ("recommendations", "plan"),
    ("next steps", "plan"),
    ("examination", "objective"),
    ("subjective", "subjective"),
    ("assessment", "assessment"),
    ("impression", "assessment"),
    ("diagnosis", "assessment"),
    ("objective", "objective"),
    ("treatment", "plan"),
    ("findings", "objective"),
    ("subject", "subjective"),
    ("plan", "plan"),
)

# Compiled once at import time. Header keywords are word-boundary anchored
# and require a trailing colon, matching the original heuristic.
_HEADER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw, _ in _SOAP_HEADERS) + r")\s*:",
    re.IGNORECASE,
)
_HEADER_TO_SECTION = {kw.lower(): section for kw, section in _SOAP_HEADERS}


class OllamaError(Exception):
    """Custom exception for Ollama-related errors"""
    pass


def _verify_ollama_and_model(model: str) -> None:
    """Check Ollama is reachable and that `model` is loaded; pull if missing."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            raise OllamaError("Ollama server is not responding")
    except requests.ConnectionError:
        raise OllamaError("Cannot connect to Ollama server. Please ensure Ollama is running.")
    except requests.Timeout:
        raise OllamaError("Timeout connecting to Ollama server")

    try:
        available_models = response.json()
        model_names = [m['name'] for m in available_models.get('models', [])]
        if model not in model_names:
            print(f"Model {model} not found, attempting to pull...")
            pull_response = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": model},
                timeout=300,
            )
            if pull_response.status_code != 200:
                raise OllamaError(f"Failed to pull model {model}")
    except OllamaError:
        raise
    except Exception as e:
        # Non-fatal: log and let the /api/generate call surface any real issue.
        print(f"Warning: Could not verify model availability: {e}")


def generate_soap_with_ollama(transcription_text: str, model: str = "gemma4") -> Dict[str, str]:
    """
    Generate a SOAP note from transcription text using Ollama

    Args:
        transcription_text: The transcribed medical conversation
        model: The Ollama model to use (default: gemma4)

    Returns:
        Dictionary containing SOAP note sections
    """

    # Skip the /api/tags preflight after first successful verification this
    # process. Saves a round-trip on every analyze call.
    if model not in _verified_models:
        _verify_ollama_and_model(model)
        _verified_models.add(model)
    
    # Create the prompt for SOAP note generation
    prompt = f"""
As a medical AI assistant, analyze the following medical transcription and generate a structured SOAP note. 
Please extract relevant information and organize it into the four SOAP categories:

SUBJECTIVE: Patient's reported symptoms, concerns, and history
OBJECTIVE: Observable findings, measurements, and clinical observations  
ASSESSMENT: Clinical impression, diagnosis, or differential diagnosis
PLAN: Treatment plan, medications, follow-up instructions

Transcription:
{transcription_text}

Please provide a structured SOAP note in JSON format with the following structure:
{{
    "subjective": "Patient's reported symptoms and concerns...",
    "objective": "Observable findings and clinical data...",
    "assessment": "Clinical impression and diagnosis...",
    "plan": "Treatment plan and next steps..."
}}

Only return the JSON object, nothing else.
"""
    
    try:
        # Generate response using Ollama
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent medical responses
                    "top_p": 0.9,
                    "top_k": 40
                }
            },
            timeout=120  # 2 minutes timeout
        )
        
        if response.status_code != 200:
            raise OllamaError(f"Ollama API error: {response.status_code}")
        
        result = response.json()
        soap_text = result.get('response', '').strip()
        
        # Try to parse JSON response
        try:
            # Look for JSON in the response
            if '{' in soap_text and '}' in soap_text:
                json_start = soap_text.find('{')
                json_end = soap_text.rfind('}') + 1
                json_text = soap_text[json_start:json_end]
                soap_note = json.loads(json_text)
                
                # Validate required fields
                required_fields = ['subjective', 'objective', 'assessment', 'plan']
                for field in required_fields:
                    if field not in soap_note:
                        soap_note[field] = f"No {field} information provided"
                
                return soap_note
            else:
                # Fallback: try to parse as structured text
                return parse_structured_text(soap_text, transcription_text)
                
        except json.JSONDecodeError:
            # Fallback: try to parse as structured text
            return parse_structured_text(soap_text, transcription_text)
            
    except requests.Timeout:
        _verified_models.discard(model)
        raise OllamaError("Timeout waiting for Ollama response")
    except requests.ConnectionError:
        _verified_models.discard(model)
        raise OllamaError("Lost connection to Ollama server")
    except OllamaError:
        _verified_models.discard(model)
        raise
    except Exception as e:
        _verified_models.discard(model)
        raise OllamaError(f"Unexpected error: {str(e)}")

def parse_structured_text(text: str, original_text: str) -> Dict[str, str]:
    """
    Parse structured text response when JSON parsing fails
    """
    soap_note = {"subjective": "", "objective": "", "assessment": "", "plan": ""}

    # Single linear scan of all SOAP-header matches, then slice the text
    # between consecutive headers. First match per section wins (matches
    # the original heuristic).
    matches = list(_HEADER_PATTERN.finditer(text))
    for i, m in enumerate(matches):
        section = _HEADER_TO_SECTION.get(m.group(1).lower())
        if not section or soap_note[section]:
            continue
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[m.end():next_start].strip()
        if content:
            soap_note[section] = content

    if not any(soap_note.values()):
        return {
            "subjective": f"Patient encounter documented: {original_text[:200]}{'...' if len(original_text) > 200 else ''}",
            "objective": "Physical examination findings to be documented by healthcare provider",
            "assessment": "Clinical assessment to be completed by healthcare provider",
            "plan": "Treatment plan to be determined by healthcare provider",
        }

    return soap_note

def check_ollama_status() -> Dict[str, any]:
    """
    Check if Ollama is running and return status information
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json()
            return {
                'status': 'running',
                'models': [model['name'] for model in models.get('models', [])],
                'message': 'Ollama is running successfully'
            }
        else:
            return {
                'status': 'error',
                'models': [],
                'message': f'Ollama returned status code: {response.status_code}'
            }
    except requests.ConnectionError:
        return {
            'status': 'not_running',
            'models': [],
            'message': 'Cannot connect to Ollama server. Please start Ollama.'
        }
    except Exception as e:
        return {
            'status': 'error',
            'models': [],
            'message': f'Error checking Ollama status: {str(e)}'
        }
