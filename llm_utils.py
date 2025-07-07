"""
LLM utilities for generating SOAP notes using Ollama
"""

import requests
import json
from typing import Dict, Optional

class OllamaError(Exception):
    """Custom exception for Ollama-related errors"""
    pass

def generate_soap_with_ollama(transcription_text: str, model: str = "llama3.2") -> Dict[str, str]:
    """
    Generate a SOAP note from transcription text using Ollama
    
    Args:
        transcription_text: The transcribed medical conversation
        model: The Ollama model to use (default: llama3.2)
    
    Returns:
        Dictionary containing SOAP note sections
    """
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            raise OllamaError("Ollama server is not responding")
    except requests.ConnectionError:
        raise OllamaError("Cannot connect to Ollama server. Please ensure Ollama is running.")
    except requests.Timeout:
        raise OllamaError("Timeout connecting to Ollama server")
    
    # Check if model is available
    try:
        available_models = response.json()
        model_names = [model['name'] for model in available_models.get('models', [])]
        if model not in model_names:
            # Try to pull the model
            print(f"Model {model} not found, attempting to pull...")
            pull_response = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": model},
                timeout=300  # 5 minutes timeout for model download
            )
            if pull_response.status_code != 200:
                raise OllamaError(f"Failed to pull model {model}")
    except Exception as e:
        print(f"Warning: Could not verify model availability: {e}")
    
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
        raise OllamaError("Timeout waiting for Ollama response")
    except requests.ConnectionError:
        raise OllamaError("Lost connection to Ollama server")
    except Exception as e:
        raise OllamaError(f"Unexpected error: {str(e)}")

def parse_structured_text(text: str, original_text: str) -> Dict[str, str]:
    """
    Parse structured text response when JSON parsing fails
    """
    soap_note = {
        'subjective': '',
        'objective': '',
        'assessment': '',
        'plan': ''
    }
    
    # Try to extract sections from text
    text_lower = text.lower()
    sections = {
        'subjective': ['subjective:', 'subject:', 'patient reports:', 'patient states:'],
        'objective': ['objective:', 'physical exam:', 'examination:', 'findings:'],
        'assessment': ['assessment:', 'impression:', 'diagnosis:', 'clinical impression:'],
        'plan': ['plan:', 'treatment:', 'recommendations:', 'next steps:']
    }
    
    for section, keywords in sections.items():
        for keyword in keywords:
            if keyword in text_lower:
                start_idx = text_lower.find(keyword)
                # Find the end of this section (next section or end of text)
                end_idx = len(text)
                for other_section, other_keywords in sections.items():
                    if other_section != section:
                        for other_keyword in other_keywords:
                            keyword_idx = text_lower.find(other_keyword, start_idx + len(keyword))
                            if keyword_idx != -1 and keyword_idx < end_idx:
                                end_idx = keyword_idx
                
                content = text[start_idx + len(keyword):end_idx].strip()
                if content:
                    soap_note[section] = content
                break
    
    # If no structured content found, provide basic fallback
    if not any(soap_note.values()):
        soap_note = {
            'subjective': f"Patient encounter documented: {original_text[:200]}{'...' if len(original_text) > 200 else ''}",
            'objective': "Physical examination findings to be documented by healthcare provider",
            'assessment': "Clinical assessment to be completed by healthcare provider",
            'plan': "Treatment plan to be determined by healthcare provider"
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

def install_ollama_model(model_name: str = "llama3.2") -> bool:
    """
    Install a specific Ollama model
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/pull",
            json={"name": model_name},
            timeout=600  # 10 minutes timeout for model download
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error installing model {model_name}: {e}")
        return False