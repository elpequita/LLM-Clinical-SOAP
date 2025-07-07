#!/usr/bin/env python3
"""
Clinical Documentation AI - Desktop Application
A local Python application for medical speech-to-text transcription and SOAP note generation.
"""

import os
import sys
import json
import threading
import tempfile
from datetime import datetime
from pathlib import Path
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import customtkinter as ctk
import whisper
import pyaudio
import wave
import numpy as np
from typing import Optional, Dict, List
import subprocess
import shutil
from llm_utils import generate_soap_with_ollama
from db_manager import DatabaseManager
from auth_manager import AuthManager
from security_manager import SecurityManager
import requests
import hashlib
import time

# Configure CustomTkinter
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class FFmpegInstaller:
    """Handles FFmpeg installation and setup for Whisper"""
    
    @staticmethod
    def check_ffmpeg():
        """Check if FFmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @staticmethod
    def install_ffmpeg_windows():
        """Install FFmpeg on Windows"""
        try:
            print("Installing FFmpeg for Windows...")
            
            # Try to install via conda/pip
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', 'ffmpeg-python'], check=True)
                print("✅ FFmpeg-python installed")
            except subprocess.CalledProcessError:
                pass
            
            # Check if ffmpeg is now available
            if FFmpegInstaller.check_ffmpeg():
                return True
                
            # Download portable FFmpeg for Windows
            ffmpeg_dir = os.path.join(os.path.dirname(__file__), 'ffmpeg')
            if not os.path.exists(ffmpeg_dir):
                os.makedirs(ffmpeg_dir)
            
            messagebox.showinfo("FFmpeg Required", 
                "FFmpeg is required but not found.\n\n"
                "Please download FFmpeg from:\n"
                "https://www.gyan.dev/ffmpeg/builds/\n\n"
                "Extract ffmpeg.exe to the application folder\n"
                "or install FFmpeg system-wide.")
            
            return False
            
        except Exception as e:
            print(f"Error installing FFmpeg: {e}")
            return False
    
    @staticmethod
    def setup_ffmpeg_path():
        """Setup FFmpeg path for the application"""
        # Add common FFmpeg locations to PATH
        ffmpeg_paths = [
            os.path.join(os.path.dirname(__file__), 'ffmpeg'),
            r'C:\ffmpeg\bin',
            r'C:\Program Files\ffmpeg\bin',
            os.path.join(os.path.expanduser('~'), 'ffmpeg', 'bin')
        ]
        
        current_path = os.environ.get('PATH', '')
        for path in ffmpeg_paths:
            if os.path.exists(path) and path not in current_path:
                os.environ['PATH'] = f"{path};{current_path}"
        
        return FFmpegInstaller.check_ffmpeg()

class AudioProcessor:
    """Enhanced audio processing with fallback options"""
    
    @staticmethod
    def convert_audio_format(input_file, output_file):
        """Convert audio to WAV format using alternative methods"""
        try:
            # Try with pydub first (doesn't require FFmpeg)
            from pydub import AudioSegment
            audio = AudioSegment.from_file(input_file)
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(output_file, format="wav")
            return True
        except ImportError:
            pass
        except Exception as e:
            print(f"Pydub conversion failed: {e}")
        
        # Fallback: Try direct copy if already WAV
        if input_file.lower().endswith('.wav'):
            try:
                shutil.copy2(input_file, output_file)
                return True
            except Exception as e:
                print(f"File copy failed: {e}")
        
        return False
    
    @staticmethod
    def preprocess_audio_for_whisper(audio_file):
        """Preprocess audio file for Whisper with error handling"""
        try:
            # Create temporary WAV file
            temp_wav = tempfile.mktemp(suffix='.wav')
            
            # Convert to proper format
            if AudioProcessor.convert_audio_format(audio_file, temp_wav):
                return temp_wav
            
            # If conversion failed, try to use original file
            if audio_file.lower().endswith(('.wav', '.mp3', '.m4a')):
                return audio_file
            
            raise Exception("Unable to process audio file format")
            
        except Exception as e:
            raise Exception(f"Audio preprocessing failed: {str(e)}")

class AudioRecorder:
    """Handles audio recording functionality"""
    
    def __init__(self):
        self.recording = False
        self.frames = []
        self.audio = None
        self.stream = None
        
    def start_recording(self):
        """Start recording audio"""
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                frames_per_buffer=1024
            )
            self.recording = True
            self.frames = []
            return True
        except Exception as e:
            print(f"Error starting recording: {e}")
            return False
    
    def record_audio(self):
        """Record audio in a separate thread"""
        while self.recording:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
            except Exception as e:
                print(f"Error during recording: {e}")
                break
    
    def stop_recording(self, filename: str) -> bool:
        """Stop recording and save to file"""
        try:
            self.recording = False
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.audio:
                self.audio.terminate()
            
            # Save audio file
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(44100)
                wf.writeframes(b''.join(self.frames))
            
            return True
        except Exception as e:
            print(f"Error stopping recording: {e}")
            return False

class MedicalAnalyzer:
    """Handles medical content analysis and SOAP note generation"""
    
    def __init__(self):
        self.medical_keywords = [
            'patient', 'symptoms', 'diagnosis', 'treatment', 'medication', 
            'pain', 'doctor', 'medical', 'health', 'hospital', 'clinic',
            'surgery', 'therapy', 'prescription', 'examination', 'vital signs',
            'blood pressure', 'temperature', 'heart rate', 'breathing',
            'chest pain', 'headache', 'nausea', 'fever', 'infection'
        ]
    
    def analyze_text(self, text: str) -> Dict:
        """Analyze transcribed text for medical content"""
        text_lower = text.lower()
        found_keywords = [kw for kw in self.medical_keywords if kw in text_lower]
        
        # Basic SOAP note generation using Ollama
        soap_note = self.generate_basic_soap(text)
        
        return {
            'medical_keywords': found_keywords,
            'medical_content_detected': len(found_keywords) > 0,
            'word_count': len(text.split()),
            'soap_note': soap_note
        }
    
    def generate_basic_soap(self, text: str) -> Dict:
        """
        Use local LLM to generate a SOAP note from transcription text.
        """
        try:
            # Call your local LLM function
            soap_note = generate_soap_with_ollama(text)
            
            # Ensure all fields exist in the returned dict
            for key in ['subjective', 'objective', 'assessment', 'plan']:
                if key not in soap_note:
                    soap_note[key] = ""
            
            return soap_note
        
        except Exception as e:
            print(f"Error generating SOAP with LLM: {e}")
            
            # Fallback: return original placeholder text
            return {
                'subjective': f"Patient reported: {text[:200]}..." if len(text) > 200 else text,
                'objective': "Clinical findings to be documented by healthcare provider",
                'assessment': "Medical assessment to be completed by healthcare provider", 
                'plan': "Treatment plan to be determined by healthcare provider"
            }

class LoginWindow:
    """Login window for user authentication"""
    
    def __init__(self, auth_manager: AuthManager, security_manager: SecurityManager):
        self.auth_manager = auth_manager
        self.security_manager = security_manager
        self.root = None
        self.user_id = None
        
    def show_login(self):
        """Display login window"""
        self.root = ctk.CTk()
        self.root.title("Clinical Documentation AI - Login")
        self.root.geometry("400x500")
        
        # Main frame
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="Clinical Documentation AI", 
                                 font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=(20, 10))
        
        # Check activation status
        if not self.security_manager.check_activation():
            error_label = ctk.CTkLabel(main_frame, 
                text="❌ Application has been deactivated.\nPlease contact support.",
                font=ctk.CTkFont(size=14), text_color="red")
            error_label.pack(pady=20)
            
            self.root.after(3000, self.root.destroy)
            self.root.mainloop()
            return None
        
        # Username
        ctk.CTkLabel(main_frame, text="Username:", font=ctk.CTkFont(size=14)).pack(pady=(20, 5))
        self.username_entry = ctk.CTkEntry(main_frame, width=300)
        self.username_entry.pack(pady=(0, 10))
        
        # Password
        ctk.CTkLabel(main_frame, text="Password:", font=ctk.CTkFont(size=14)).pack(pady=(10, 5))
        self.password_entry = ctk.CTkEntry(main_frame, width=300, show="*")
        self.password_entry.pack(pady=(0, 20))
        
        # Login button
        login_button = ctk.CTkButton(main_frame, text="Login", command=self.login, 
                                   height=40, width=200)
        login_button.pack(pady=10)
        
        # Register button
        register_button = ctk.CTkButton(main_frame, text="Register New User", 
                                      command=self.show_register, height=40, width=200)
        register_button.pack(pady=10)
        
        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")
        self.error_label.pack(pady=10)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda event: self.login())
        
        self.root.mainloop()
        return self.user_id
    
    def login(self):
        """Handle login attempt"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            self.error_label.configure(text="Please enter both username and password")
            return
        
        user_id = self.auth_manager.authenticate_user(username, password)
        if user_id:
            self.user_id = user_id
            self.root.destroy()
        else:
            self.error_label.configure(text="Invalid username or password")
    
    def show_register(self):
        """Show registration window"""
        register_window = ctk.CTkToplevel(self.root)
        register_window.title("Register New User")
        register_window.geometry("400x400")
        
        # Main frame
        main_frame = ctk.CTkFrame(register_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="Register New User", 
                                 font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=(20, 10))
        
        # Username
        ctk.CTkLabel(main_frame, text="Username:", font=ctk.CTkFont(size=14)).pack(pady=(20, 5))
        username_entry = ctk.CTkEntry(main_frame, width=300)
        username_entry.pack(pady=(0, 10))
        
        # Password
        ctk.CTkLabel(main_frame, text="Password:", font=ctk.CTkFont(size=14)).pack(pady=(10, 5))
        password_entry = ctk.CTkEntry(main_frame, width=300, show="*")
        password_entry.pack(pady=(0, 10))
        
        # Confirm Password
        ctk.CTkLabel(main_frame, text="Confirm Password:", font=ctk.CTkFont(size=14)).pack(pady=(10, 5))
        confirm_password_entry = ctk.CTkEntry(main_frame, width=300, show="*")
        confirm_password_entry.pack(pady=(0, 20))
        
        # Register button
        def register():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            confirm_password = confirm_password_entry.get().strip()
            
            if not username or not password:
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            if password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            if len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters")
                return
            
            if self.auth_manager.create_user(username, password):
                messagebox.showinfo("Success", "User registered successfully!")
                register_window.destroy()
            else:
                messagebox.showerror("Error", "Username already exists")
        
        register_button = ctk.CTkButton(main_frame, text="Register", command=register, 
                                      height=40, width=200)
        register_button.pack(pady=10)

class ClinicalDocumentationApp:
    """Main desktop application class"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.root = ctk.CTk()
        self.root.title("Clinical Documentation AI")
        self.root.geometry("1200x800")
        
        # Initialize components
        self.recorder = AudioRecorder()
        self.db = DatabaseManager()
        self.analyzer = MedicalAnalyzer()
        self.security_manager = SecurityManager()
        
        # Setup FFmpeg
        self.ffmpeg_available = self.setup_ffmpeg()
        
        # Load Whisper model
        self.whisper_model = None
        self.load_whisper_model()
        
        # UI State
        self.recording = False
        self.current_audio_file = None
        self.current_transcription = None
        
        # Start security check timer
        self.start_security_timer()
        
        # Create UI
        self.create_ui()
    
    def setup_ffmpeg(self):
        """Setup FFmpeg for Whisper"""
        if FFmpegInstaller.check_ffmpeg():
            print("✅ FFmpeg is available")
            return True
        
        print("⚠️ FFmpeg not found, attempting setup...")
        if FFmpegInstaller.setup_ffmpeg_path():
            print("✅ FFmpeg path configured")
            return True
        
        # On Windows, try to install FFmpeg
        if sys.platform.startswith('win'):
            return FFmpegInstaller.install_ffmpeg_windows()
        
        print("❌ FFmpeg not available - some audio formats may not work")
        return False
    
    def start_security_timer(self):
        """Start periodic security checks"""
        def check_security():
            if not self.security_manager.check_activation():
                messagebox.showerror("Security Alert", 
                    "Application has been deactivated remotely.\nThe application will now close.")
                self.root.destroy()
                return
            
            # Schedule next check in 5 minutes
            self.root.after(300000, check_security)
        
        # Start first check after 30 seconds
        self.root.after(30000, check_security)
    
    def load_whisper_model(self):
        """Load Whisper model in background"""
        def load_model():
            try:
                print("Loading Whisper model...")
                self.whisper_model = whisper.load_model("base")
                print("Whisper model loaded successfully!")
                self.root.after(0, self.update_model_status, True)
            except Exception as e:
                print(f"Error loading Whisper model: {e}")
                self.root.after(0, self.update_model_status, False)
        
        threading.Thread(target=load_model, daemon=True).start()
    
    def update_model_status(self, loaded: bool):
        """Update UI with model loading status"""
        if hasattr(self, 'status_label'):
            whisper_status = "✅ Ready" if loaded else "❌ Error loading model"
            ffmpeg_status = "✅ Available" if self.ffmpeg_available else "⚠️ Limited"
            self.status_label.configure(text=f"Whisper: {whisper_status} | FFmpeg: {ffmpeg_status}")
    
    def create_ui(self):
        """Create the main user interface"""
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="Clinical Documentation AI", 
                                 font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=(20, 10))
        
        subtitle_label = ctk.CTkLabel(main_frame, 
            text="Record clinical encounters and generate structured medical notes",
            font=ctk.CTkFont(size=14))
        subtitle_label.pack(pady=(0, 20))
        
        # Status bar
        self.status_label = ctk.CTkLabel(main_frame, text="Loading...")
        self.status_label.pack(pady=(0, 20))
        
        # FFmpeg warning if not available
        if not self.ffmpeg_available:
            warning_frame = ctk.CTkFrame(main_frame, fg_color="orange")
            warning_frame.pack(fill="x", padx=20, pady=(0, 10))
            
            warning_label = ctk.CTkLabel(
                warning_frame, 
                text="⚠️ FFmpeg not found - Only WAV files fully supported. For MP3/M4A support, install FFmpeg",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="white"
            )
            warning_label.pack(pady=10)
        
        # Create notebook for tabs
        self.notebook = ctk.CTkTabview(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=10)
        
        # Create tabs
        self.create_recording_tab()
        self.create_transcription_tab()
        self.create_history_tab()
    
    def create_recording_tab(self):
        """Create the audio recording tab"""
        recording_tab = self.notebook.add("Recording")
        
        # Recording controls frame
        controls_frame = ctk.CTkFrame(recording_tab)
        controls_frame.pack(fill="x", padx=20, pady=20)
        
        # Recording button
        self.record_button = ctk.CTkButton(
            controls_frame,
            text="🎤 Start Recording",
            command=self.toggle_recording,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.record_button.pack(pady=20)
        
        # File upload button
        upload_button = ctk.CTkButton(
            controls_frame,
            text="📁 Upload Audio File",
            command=self.upload_audio_file,
            height=40
        )
        upload_button.pack(pady=10)
        
        # Audio file info
        self.audio_info_label = ctk.CTkLabel(controls_frame, text="No audio file selected")
        self.audio_info_label.pack(pady=10)
        
        # Transcribe button
        self.transcribe_button = ctk.CTkButton(
            controls_frame,
            text="🧠 Transcribe Audio",
            command=self.transcribe_audio,
            state="disabled",
            height=40
        )
        self.transcribe_button.pack(pady=10)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(controls_frame)
        self.progress_bar.pack(fill="x", padx=20, pady=10)
        self.progress_bar.set(0)
    
    def create_transcription_tab(self):
        """Create the transcription results tab"""
        transcription_tab = self.notebook.add("Transcription")
        
        # Transcription text area
        self.transcription_text = ctk.CTkTextbox(
            transcription_tab,
            height=300,
            font=ctk.CTkFont(size=14)
        )
        self.transcription_text.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Analysis frame
        analysis_frame = ctk.CTkFrame(transcription_tab)
        analysis_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Analyze button
        self.analyze_button = ctk.CTkButton(
            analysis_frame,
            text="🏥 Analyze Medical Content",
            command=self.analyze_medical_content,
            state="disabled",
            height=40
        )
        self.analyze_button.pack(pady=10)

        # Save Transcription button
        self.save_button = ctk.CTkButton(
            analysis_frame,
            text="💾 Save Transcription",
            command=self.save_transcription,
            state="disabled",
            height=40
        )
        self.save_button.pack(pady=10)

        # SOAP note display
        self.soap_text = ctk.CTkTextbox(
            analysis_frame,
            height=400,
            font=ctk.CTkFont(size=14),
            wrap="word"
        )
        self.soap_text.pack(fill="both", expand=False, padx=20, pady=(0, 10))       
       
        # Copy SOAP note button
        self.copy_button = ctk.CTkButton(
            analysis_frame,
            text="📋 Copy SOAP Note",
            command=self.copy_soap_text,
            height=40
        )
        self.copy_button.pack(pady=(10,20))

    def create_history_tab(self):
        """Create the transcription history tab"""
        history_tab = self.notebook.add("History")
        
        # Refresh button
        refresh_button = ctk.CTkButton(
            history_tab,
            text="🔄 Refresh History",
            command=self.load_history
        )
        refresh_button.pack(pady=20)
        
        # History list
        self.history_frame = ctk.CTkScrollableFrame(history_tab)
        self.history_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Load initial history
        self.load_history()
    
    def toggle_recording(self):
        """Toggle audio recording"""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start audio recording"""
        if self.recorder.start_recording():
            self.recording = True
            self.record_button.configure(text="⏹️ Stop Recording")
            self.record_button.configure(fg_color="red")
            
            # Start recording in background thread
            threading.Thread(target=self.recorder.record_audio, daemon=True).start()
        else:
            messagebox.showerror("Error", "Failed to start recording. Please check your microphone.")
    
    def stop_recording(self):
        """Stop audio recording"""
        temp_file = tempfile.mktemp(suffix=".wav")
        if self.recorder.stop_recording(temp_file):
            self.recording = False
            self.record_button.configure(text="🎤 Start Recording")
            self.record_button.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            
            self.current_audio_file = temp_file
            self.audio_info_label.configure(text=f"Recorded audio ready: {os.path.basename(temp_file)}")
            self.transcribe_button.configure(state="normal")
        else:
            messagebox.showerror("Error", "Failed to stop recording.")
    
    def upload_audio_file(self):
        """Upload an audio file"""
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[
                ("Audio Files", "*.wav *.mp3 *.m4a *.ogg *.flac"),
                ("All Files", "*.*")
            ]
        )
        
        if file_path:
            self.current_audio_file = file_path
            self.audio_info_label.configure(text=f"Audio file: {os.path.basename(file_path)}")
            self.transcribe_button.configure(state="normal")
    
    def transcribe_audio(self):
        """Transcribe the current audio file with enhanced error handling"""
        if not self.current_audio_file or not self.whisper_model:
            messagebox.showerror("Error", "No audio file or Whisper model not loaded.")
            return
        
        # Check if file exists
        if not os.path.exists(self.current_audio_file):
            messagebox.showerror("Error", f"Audio file not found: {self.current_audio_file}")
            return
        
        # Disable button and show progress
        self.transcribe_button.configure(state="disabled", text="Transcribing...")
        self.progress_bar.set(0.2)
        
        def transcribe_worker():
            try:
                # Preprocess audio file
                self.root.after(0, lambda: self.progress_bar.set(0.3))
                
                processed_file = None
                try:
                    processed_file = AudioProcessor.preprocess_audio_for_whisper(self.current_audio_file)
                    self.root.after(0, lambda: self.progress_bar.set(0.5))
                except Exception as e:
                    # Try to use original file as fallback
                    processed_file = self.current_audio_file
                    print(f"Audio preprocessing warning: {e}")
                
                # Transcribe audio with multiple fallback options
                result = None
                errors = []
                
                # Method 1: Standard Whisper transcription
                try:
                    result = self.whisper_model.transcribe(
                        processed_file, 
                        language=None, 
                        task="transcribe",
                        fp16=False
                    )
                except Exception as e:
                    errors.append(f"Standard transcription: {str(e)}")
                
                # Method 2: Fallback with basic parameters
                if not result:
                    try:
                        result = self.whisper_model.transcribe(
                            processed_file,
                            temperature=0,
                            best_of=1,
                            beam_size=1,
                            fp16=False
                        )
                    except Exception as e:
                        errors.append(f"Basic transcription: {str(e)}")
                
                # Method 3: Try loading audio manually
                if not result:
                    try:
                        import whisper.audio
                        audio = whisper.load_audio(processed_file)
                        audio = whisper.pad_or_trim(audio)
                        
                        # Get mel spectrogram
                        mel = whisper.log_mel_spectrogram(audio).to(self.whisper_model.device)
                        
                        # Detect language
                        _, probs = self.whisper_model.detect_language(mel)
                        detected_language = max(probs, key=probs.get)
                        
                        # Decode
                        options = whisper.DecodingOptions(
                            language=detected_language,
                            without_timestamps=True,
                            fp16=False
                        )
                        result_obj = whisper.decode(self.whisper_model, mel, options)
                        
                        result = {
                            'text': result_obj.text,
                            'language': detected_language,
                            'segments': []
                        }
                        
                    except Exception as e:
                        errors.append(f"Manual transcription: {str(e)}")
                
                if result:
                    transcription_data = {
                        'filename': os.path.basename(self.current_audio_file),
                        'text': result['text'].strip(),
                        'language': result.get('language', 'unknown'),
                        'segments': result.get('segments', [])
                    }
                    
                    # Update UI on main thread
                    self.root.after(0, self.update_transcription_ui, transcription_data)
                else:
                    # All methods failed
                    error_msg = "All transcription methods failed:\n" + "\n".join(errors)
                    self.root.after(0, self.transcription_error, error_msg)
                
                # Clean up temporary file
                if processed_file != self.current_audio_file and os.path.exists(processed_file):
                    try:
                        os.unlink(processed_file)
                    except:
                        pass
                
            except Exception as e:
                self.root.after(0, self.transcription_error, str(e))
        
        threading.Thread(target=transcribe_worker, daemon=True).start()
    
    def update_transcription_ui(self, transcription_data):
        """Update UI with transcription results"""
        self.current_transcription = transcription_data
        
        # Update transcription text
        self.transcription_text.delete("1.0", "end")
        self.transcription_text.insert("1.0", transcription_data['text'])
        
        # Switch to transcription tab
        self.notebook.set("Transcription")
        
        # Enable analysis and save buttons
        self.analyze_button.configure(state="normal")
        self.save_button.configure(state="normal")
        
        # Reset transcribe button
        self.transcribe_button.configure(state="normal", text="🧠 Transcribe Audio")
        self.progress_bar.set(1.0)
        
        messagebox.showinfo("Success", f"Transcription completed!\nLanguage: {transcription_data['language']}")

    def copy_soap_text(self):
        """Copy the contents of the SOAP note textbox to the clipboard."""
        text = self.soap_text.get("1.0", "end").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Copied", "SOAP note copied to clipboard!")
        else:
            messagebox.showwarning("No Content", "SOAP note is empty and cannot be copied.")
    
    def transcription_error(self, error_msg):
        """Handle transcription error"""
        self.transcribe_button.configure(state="normal", text="🧠 Transcribe Audio")
        self.progress_bar.set(0)
        messagebox.showerror("Transcription Error", f"Failed to transcribe audio:\n{error_msg}")
    
    def analyze_medical_content(self):
        """Analyze transcription for medical content"""
        if not self.current_transcription:
            return
        
        # Analyze text
        analysis = self.analyzer.analyze_text(self.current_transcription['text'])
        self.current_transcription.update(analysis)
        
        # Update SOAP note display
        soap_note = analysis['soap_note']
        soap_text = f"""SUBJECTIVE:
{soap_note['subjective']}

OBJECTIVE:
{soap_note['objective']}

ASSESSMENT:
{soap_note['assessment']}

PLAN:
{soap_note['plan']}


"""
        
        self.soap_text.delete("1.0", "end")
        self.soap_text.insert("1.0", soap_text)
        
        messagebox.showinfo("Analysis Complete", 
                          f"Found {len(analysis['medical_keywords'])} medical keywords")
    
    def save_transcription(self):
        """Save transcription to database"""
        if not self.current_transcription:
            return
        
        try:
            # Add user_id to transcription data
            self.current_transcription['user_id'] = self.user_id
            transcription_id = self.db.save_transcription(self.current_transcription)
            messagebox.showinfo("Success", f"Transcription saved!\nID: {transcription_id}")
            self.load_history()  # Refresh history
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save transcription:\n{str(e)}")
    
    def load_history(self):
        """Load and display transcription history"""
        # Clear existing history
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        
        # Load transcriptions for current user
        transcriptions = self.db.get_transcriptions(self.user_id)
        
        if not transcriptions:
            no_data_label = ctk.CTkLabel(self.history_frame, text="No transcriptions found")
            no_data_label.pack(pady=20)
            return
        
        # Display transcriptions
        for trans in transcriptions:
            trans_frame = ctk.CTkFrame(self.history_frame)
            trans_frame.pack(fill="x", padx=10, pady=5)
            
            # Transcription info
            info_label = ctk.CTkLabel(
                trans_frame,
                text=f"📄 {trans['filename']} | {trans['created_at']} | {trans['status']}",
                font=ctk.CTkFont(weight="bold")
            )
            info_label.pack(anchor="w", padx=10, pady=5)
            
            # Preview text
            preview_label = ctk.CTkLabel(
                trans_frame,
                text=trans['text'],
                wraplength=800
            )
            preview_label.pack(anchor="w", padx=10, pady=5)
            
            # View button
            view_button = ctk.CTkButton(
                trans_frame,
                text="👁️ View Details",
                command=lambda t_id=trans['id']: self.view_transcription(t_id),
                width=120
            )
            view_button.pack(anchor="e", padx=10, pady=5)
    
    def view_transcription(self, transcription_id: str):
        """View detailed transcription"""
        transcription = self.db.get_transcription_by_id(transcription_id)
        if not transcription:
            messagebox.showerror("Error", "Transcription not found")
            return
        
        # Create detail window
        detail_window = ctk.CTkToplevel(self.root)
        detail_window.title(f"Transcription Details - {transcription['filename']}")
        detail_window.geometry("800x600")
        
        # Transcription text
        text_area = ctk.CTkTextbox(detail_window, height=300)
        text_area.pack(fill="both", expand=True, padx=20, pady=20)
        text_area.insert("1.0", transcription['text'])
        
        # SOAP note if available
        if transcription['soap_note']:
            soap_label = ctk.CTkLabel(detail_window, text="SOAP Note:", 
                                    font=ctk.CTkFont(size=16, weight="bold"))
            soap_label.pack(anchor="w", padx=20, pady=(10, 5))
            
            soap_area = ctk.CTkTextbox(detail_window, height=200)
            soap_area.pack(fill="x", padx=20, pady=(0, 20))
            
            soap_note = transcription['soap_note']
            soap_text = f"""SUBJECTIVE: {soap_note.get('subjective', 'N/A')}

OBJECTIVE: {soap_note.get('objective', 'N/A')}

ASSESSMENT: {soap_note.get('assessment', 'N/A')}

PLAN: {soap_note.get('plan', 'N/A')}"""
            
            soap_area.insert("1.0", soap_text)
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        # Initialize security manager
        security_manager = SecurityManager()
        
        # Initialize authentication manager
        auth_manager = AuthManager()
        
        # Show login window
        login_window = LoginWindow(auth_manager, security_manager)
        user_id = login_window.show_login()
        
        if user_id:
            # Start main application
            app = ClinicalDocumentationApp(user_id)
            app.run()
        else:
            print("Login cancelled or failed")
        
    except Exception as e:
        print(f"Error starting application: {e}")
        messagebox.showerror("Error", f"Failed to start application:\n{str(e)}")

if __name__ == "__main__":
    main()