#!/usr/bin/env python3
"""
Clinical Documentation AI - Desktop Application
A local Python application for medical speech-to-text transcription and SOAP note generation.
"""

import os
# Anaconda + CTranslate2 (faster-whisper backend) ship different OpenMP runtimes
# that conflict at import time on Windows ("OMP: Error #15: libiomp5md.dll already
# initialized"). This setdefault must run BEFORE faster_whisper is imported. It's
# Intel's documented workaround for this exact case.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# Suppress the symlink-fallback warning HuggingFace prints on Windows when not
# running as admin / with Developer Mode on. The model still downloads correctly.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import logging
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
from faster_whisper import WhisperModel
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

# PHI-aware logger. The transcription pipeline can echo patient content back
# inside exception messages, audio file paths, and LLM responses. To avoid
# accidental PHI exposure in stdout/log aggregators, sensitive code paths log
# only exception types (not exception text) and never log file paths.
# Operators can route to a file via the CLINICAL_LOG_FILE env var; otherwise
# logging goes to stderr at WARNING and above.
logger = logging.getLogger("clinical_app")
if not logger.handlers:
    _log_file = os.environ.get("CLINICAL_LOG_FILE", "").strip()
    _handler = logging.FileHandler(_log_file) if _log_file else logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False

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
            # Create temporary WAV file (NamedTemporaryFile avoids the mktemp
            # TOCTOU race that could let another process replace the file).
            tf = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            tf.close()
            temp_wav = tf.name
            
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
            # Cache sample width while the PortAudio session is still alive.
            # Some PyAudio builds route get_sample_size through the C session
            # and return garbage (or raise) after terminate(); paInt16 is always
            # 2 bytes but the safe-default fallback keeps the WAV header valid.
            sample_width = self.audio.get_sample_size(pyaudio.paInt16) if self.audio else 2
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.audio:
                self.audio.terminate()

            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(sample_width)
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
            # Log only the exception type — `e` may echo prompt content
            # including transcribed PHI back to stdout/log aggregators.
            logger.warning("Local LLM call failed (%s); using fallback SOAP template", type(e).__name__)

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
        self.username = None
        
    def show_login(self):
        """Display login window"""
        self.root = ctk.CTk()
        self.root.title("Clinical Documentation AI")
        self.root.geometry("460x640")
        self.root.resizable(False, False)
        ctk.set_appearance_mode("system")

        # Activation check first — render a different screen if deactivated
        if not self.security_manager.check_activation():
            self._render_deactivated_screen()
            return None

        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=44, pady=36)

        # Brand area
        ctk.CTkLabel(container, text="🩺", font=ctk.CTkFont(size=56)).pack(pady=(12, 6))
        ctk.CTkLabel(
            container,
            text="Clinical Documentation AI",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            container,
            text="Dictate · Transcribe · Document",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
        ).pack(pady=(2, 28))

        # Form card
        form = ctk.CTkFrame(container, corner_radius=12)
        form.pack(fill="x")

        ctk.CTkLabel(
            form, text="Username",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=22, pady=(20, 4))
        self.username_entry = ctk.CTkEntry(
            form, placeholder_text="Enter your username", height=38,
        )
        self.username_entry.pack(fill="x", padx=22, pady=(0, 14))

        ctk.CTkLabel(
            form, text="Password",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=22, pady=(4, 4))
        pwd_row = ctk.CTkFrame(form, fg_color="transparent")
        pwd_row.pack(fill="x", padx=22, pady=(0, 22))
        self.password_entry = ctk.CTkEntry(
            pwd_row, placeholder_text="Enter your password", show="•", height=38,
        )
        self.password_entry.pack(side="left", fill="x", expand=True)
        self._password_visible = False
        self._toggle_pwd_btn = ctk.CTkButton(
            pwd_row, text="👁", width=38, height=38,
            fg_color="transparent", hover_color=("gray86", "gray26"),
            text_color=("gray35", "gray70"),
            command=self._toggle_password_visibility,
        )
        self._toggle_pwd_btn.pack(side="right", padx=(6, 0))

        # Primary action
        ctk.CTkButton(
            container, text="Sign In", command=self.login,
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(fill="x", pady=(18, 10))

        # Inline error (kept reserved height even when empty so layout doesn't jump)
        self.error_label = ctk.CTkLabel(
            container, text="", text_color=("#C53030", "#FC8181"),
            font=ctk.CTkFont(size=12), height=18,
        )
        self.error_label.pack()

        # Register secondary action
        ctk.CTkButton(
            container, text="Need an account?  Register",
            command=self.show_register,
            fg_color="transparent", hover_color=("gray90", "gray20"),
            text_color=("gray30", "gray70"),
            font=ctk.CTkFont(size=12), height=32,
        ).pack(pady=(14, 0))

        self.root.bind("<Return>", lambda event: self.login())
        self.username_entry.focus()
        self.root.mainloop()
        return self.user_id

    def _toggle_password_visibility(self):
        self._password_visible = not self._password_visible
        self.password_entry.configure(show="" if self._password_visible else "•")
        self._toggle_pwd_btn.configure(text="🙈" if self._password_visible else "👁")

    def _render_deactivated_screen(self):
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        ctk.CTkLabel(container, text="⛔", font=ctk.CTkFont(size=72)).pack(pady=(140, 16))
        ctk.CTkLabel(
            container, text="Application Deactivated",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            container,
            text="This application has been deactivated remotely.\nPlease contact your administrator.",
            font=ctk.CTkFont(size=13), text_color=("gray40", "gray60"),
        ).pack(pady=(10, 0))
        self.root.after(4000, self.root.destroy)
        self.root.mainloop()
    
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
            self.username = username
            self.root.destroy()
        else:
            self.error_label.configure(text="Invalid username or password")
    
    def show_register(self):
        """Show registration window"""
        register_window = ctk.CTkToplevel(self.root)
        register_window.title("Create Account")
        register_window.geometry("440x560")
        register_window.resizable(False, False)
        register_window.transient(self.root)
        register_window.grab_set()

        container = ctk.CTkFrame(register_window, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=32)

        ctk.CTkLabel(container, text="✨", font=ctk.CTkFont(size=44)).pack(pady=(8, 6))
        ctk.CTkLabel(
            container, text="Create Your Account",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            container, text="Used to sign in and tag your transcriptions",
            font=ctk.CTkFont(size=12), text_color=("gray40", "gray60"),
        ).pack(pady=(2, 22))

        form = ctk.CTkFrame(container, corner_radius=12)
        form.pack(fill="x")

        ctk.CTkLabel(
            form, text="Username", font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=22, pady=(18, 4))
        username_entry = ctk.CTkEntry(form, placeholder_text="Choose a username", height=38)
        username_entry.pack(fill="x", padx=22, pady=(0, 12))

        ctk.CTkLabel(
            form, text="Password (min 6 characters)",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=22, pady=(4, 4))
        password_entry = ctk.CTkEntry(
            form, placeholder_text="Choose a password", show="•", height=38,
        )
        password_entry.pack(fill="x", padx=22, pady=(0, 12))

        ctk.CTkLabel(
            form, text="Confirm Password",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=22, pady=(4, 4))
        confirm_password_entry = ctk.CTkEntry(
            form, placeholder_text="Re-enter your password", show="•", height=38,
        )
        confirm_password_entry.pack(fill="x", padx=22, pady=(0, 20))

        inline_error = ctk.CTkLabel(
            container, text="", text_color=("#C53030", "#FC8181"),
            font=ctk.CTkFont(size=12), height=18,
        )

        def show_error(msg):
            inline_error.configure(text=msg)

        def register():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            confirm_password = confirm_password_entry.get().strip()

            if not username or not password:
                show_error("Please fill in all fields")
                return
            if password != confirm_password:
                show_error("Passwords do not match")
                return
            if len(password) < 6:
                show_error("Password must be at least 6 characters")
                return
            if self.auth_manager.create_user(username, password):
                messagebox.showinfo("Success", "Account created. You can now sign in.")
                register_window.destroy()
            else:
                show_error("That username is already taken")

        ctk.CTkButton(
            container, text="Create Account", command=register,
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(fill="x", pady=(14, 8))
        inline_error.pack()
        register_window.bind("<Return>", lambda event: register())
        username_entry.focus()

class ClinicalDocumentationApp:
    """Main desktop application class"""
    
    def __init__(self, user_id: str, username: str = "User"):
        self.user_id = user_id
        self._username = username
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

        # UI state must exist before create_ui references any of it
        self.recording = False
        self.current_audio_file = None
        self.current_transcription = None
        self.whisper_model = None

        # Build UI first so whisper_status_label exists when background loaders fire
        self.create_ui()

        # Hook the close button so we can release the mic / cancel timers cleanly.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Now safe to spawn the Whisper loader thread and the security timer
        self.load_whisper_model()
        self.start_security_timer()

    def _on_close(self):
        """Window close handler — releases recording resources before destroy.

        Without this, closing the window mid-recording leaves the PortAudio
        stream open. On Windows the OS holds the mic until Python GC collects
        the AudioRecorder, which can be seconds-to-never depending on refs.
        """
        try:
            if self.recording:
                self.recording = False
                self._stop_recording_timer()
                try:
                    if self.recorder.stream:
                        self.recorder.stream.stop_stream()
                        self.recorder.stream.close()
                    if self.recorder.audio:
                        self.recorder.audio.terminate()
                except Exception as e:
                    print(f"Recorder cleanup warning: {e}")
            # Cancel any in-flight tick (defensive — _stop_recording_timer
            # above handles the recording case but not other after callbacks).
            after_id = getattr(self, "_recording_after_id", None)
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
            # Release this thread's DB connection back to the pool / OS.
            try:
                self.db.close()
            except Exception:
                pass
        finally:
            self.root.destroy()
    
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
    
    WHISPER_MODEL_NAME = "large-v3-turbo"

    def load_whisper_model(self):
        """Load Whisper model in background (faster-whisper / CTranslate2 backend)."""
        def load_model():
            try:
                print(f"Loading Whisper model ({self.WHISPER_MODEL_NAME})...")
                # device="auto" picks CUDA if a compatible GPU is present, else CPU.
                # compute_type="int8" keeps memory tight on CPU and is still very fast;
                # it auto-promotes to int8_float16 on GPU for accuracy.
                self.whisper_model = WhisperModel(
                    self.WHISPER_MODEL_NAME,
                    device="auto",
                    compute_type="int8",
                )
                print("Whisper model loaded successfully!")
                self.root.after(0, self.update_model_status, True)
            except Exception as e:
                print(f"Error loading Whisper model: {e}")
                self.root.after(0, self.update_model_status, False)

        threading.Thread(target=load_model, daemon=True).start()
    
    # ----- Status bar plumbing -----------------------------------------

    def update_model_status(self, loaded: bool):
        """Background Whisper loader callback — updates the bottom status bar."""
        self._whisper_loaded = loaded
        if hasattr(self, "whisper_status_label"):
            label = (
                f"Whisper · {self.WHISPER_MODEL_NAME} · ✅ Ready"
                if loaded
                else f"Whisper · {self.WHISPER_MODEL_NAME} · ❌ Error"
            )
            self.whisper_status_label.configure(
                text=label,
                text_color=("#2F855A", "#68D391") if loaded else ("#C53030", "#FC8181"),
            )

    # ----- UI construction --------------------------------------------

    def create_ui(self):
        """Top bar · two-column main area (Capture | Document) · status footer."""
        self.root.geometry("1320x860")
        self.root.minsize(1100, 720)

        # Recording timer state
        self._recording_seconds = 0
        self._recording_after_id = None
        self._whisper_loaded = False

        # Root grid: top / main / footer
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self._build_top_bar(self.root)
        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(8, 8))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1, minsize=480)
        body.grid_columnconfigure(1, weight=1, minsize=540)
        self._build_capture_pane(body)
        self._build_document_pane(body)
        self._build_status_bar(self.root)

        # FFmpeg banner above the capture pane if missing
        if not self.ffmpeg_available:
            banner = ctk.CTkFrame(self.root, fg_color=("#FED7AA", "#7C2D12"))
            banner.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))
            ctk.CTkLabel(
                banner,
                text="⚠ FFmpeg not found — only WAV files will work. Install FFmpeg for MP3/M4A support.",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("#7C2D12", "#FED7AA"),
            ).pack(pady=6)

        self._bind_shortcuts()

    def _build_top_bar(self, parent):
        bar = ctk.CTkFrame(parent, corner_radius=0, height=52, fg_color=("#FFFFFF", "#1F2024"))
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            bar, text="🩺  Clinical Documentation AI",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=12)

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=12, pady=8)

        ctk.CTkLabel(
            right, text=f"👤 {self._username}",
            font=ctk.CTkFont(size=12), text_color=("gray35", "gray70"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            right, text="📚  History", width=104, height=32,
            command=self._open_history_window,
            fg_color="transparent", border_width=1,
            border_color=("gray70", "gray35"),
            text_color=("gray20", "gray85"),
            hover_color=("gray90", "gray22"),
        ).pack(side="left", padx=4)

        self._theme_button = ctk.CTkButton(
            right, text="🌙", width=36, height=32,
            command=self._toggle_theme,
            fg_color="transparent",
            text_color=("gray25", "gray80"),
            hover_color=("gray90", "gray22"),
        )
        self._theme_button.pack(side="left", padx=4)

    def _build_capture_pane(self, parent):
        col = ctk.CTkFrame(parent, fg_color=("#F7F8FA", "#22242A"), corner_radius=14)
        col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        col.grid_columnconfigure(0, weight=1)
        col.grid_rowconfigure(2, weight=1)

        # --- Section header
        ctk.CTkLabel(
            col, text="CAPTURE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray45", "gray60"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))

        # --- Recording control card
        rec_card = ctk.CTkFrame(col, corner_radius=10)
        rec_card.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 12))
        rec_card.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(rec_card, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        btn_row.grid_columnconfigure(0, weight=2)
        btn_row.grid_columnconfigure(1, weight=1)

        self.record_button = ctk.CTkButton(
            btn_row, text="⏺  Record   (F2)",
            command=self.toggle_recording,
            height=46, font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.record_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="📁  Upload",
            command=self.upload_audio_file,
            height=46, fg_color="transparent", border_width=1,
            border_color=("gray70", "gray35"),
            text_color=("gray20", "gray85"),
            hover_color=("gray90", "gray22"),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        info_row = ctk.CTkFrame(rec_card, fg_color="transparent")
        info_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        info_row.grid_columnconfigure(1, weight=1)

        self.timer_label = ctk.CTkLabel(
            info_row, text="00:00",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("gray35", "gray75"), width=68, anchor="w",
        )
        self.timer_label.grid(row=0, column=0, sticky="w")

        self.audio_info_label = ctk.CTkLabel(
            info_row, text="No audio loaded",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray60"), anchor="w",
        )
        self.audio_info_label.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # --- Transcript editable pane
        ctk.CTkLabel(
            col, text="Transcript  (editable)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray35", "gray70"),
        ).grid(row=2, column=0, sticky="nw", padx=20, pady=(4, 4))

        self.transcription_text = ctk.CTkTextbox(
            col, font=ctk.CTkFont(size=13), wrap="word", corner_radius=8,
        )
        self.transcription_text.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 12))
        col.grid_rowconfigure(3, weight=1)

        # --- Bottom action row
        action_row = ctk.CTkFrame(col, fg_color="transparent")
        action_row.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 14))
        action_row.grid_columnconfigure(0, weight=1)

        self.transcribe_button = ctk.CTkButton(
            action_row, text="🧠  Transcribe   (F3)",
            command=self.transcribe_audio, state="disabled",
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.transcribe_button.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(col)
        self.progress_bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.progress_bar.set(0)

    def _build_document_pane(self, parent):
        col = ctk.CTkFrame(parent, fg_color=("#F7F8FA", "#22242A"), corner_radius=14)
        col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        col.grid_columnconfigure(0, weight=1)
        col.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            col, text="SOAP NOTE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray45", "gray60"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        # Scrollable section list (lets all four sections fit on smaller screens)
        sections = ctk.CTkScrollableFrame(col, fg_color="transparent")
        sections.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        sections.grid_columnconfigure(0, weight=1)

        self._soap_textboxes = {}
        for i, (key, label) in enumerate([
            ("subjective", "Subjective"),
            ("objective", "Objective"),
            ("assessment", "Assessment"),
            ("plan", "Plan"),
        ]):
            ctk.CTkLabel(
                sections, text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("gray30", "gray80"), anchor="w",
            ).grid(row=i * 2, column=0, sticky="ew", padx=8, pady=(8 if i else 4, 4))
            box = ctk.CTkTextbox(
                sections, height=120, font=ctk.CTkFont(size=13),
                wrap="word", corner_radius=8,
            )
            box.grid(row=i * 2 + 1, column=0, sticky="ew", padx=8, pady=(0, 4))
            self._soap_textboxes[key] = box

        # Sticky action bar
        action_row = ctk.CTkFrame(col, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 14))
        action_row.grid_columnconfigure(0, weight=1)
        action_row.grid_columnconfigure(1, weight=0)
        action_row.grid_columnconfigure(2, weight=0)

        self.analyze_button = ctk.CTkButton(
            action_row, text="🏥  Analyze   (F4)",
            command=self.analyze_medical_content, state="disabled",
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.analyze_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.copy_button = ctk.CTkButton(
            action_row, text="📋  Copy",
            command=self.copy_soap_text,
            height=42, width=110,
            fg_color="transparent", border_width=1,
            border_color=("gray70", "gray35"),
            text_color=("gray20", "gray85"),
            hover_color=("gray90", "gray22"),
        )
        self.copy_button.grid(row=0, column=1, padx=6)

        self.save_button = ctk.CTkButton(
            action_row, text="💾  Save",
            command=self.save_transcription, state="disabled",
            height=42, width=128,
            fg_color=("#2F855A", "#38A169"),
            hover_color=("#276749", "#2F855A"),
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.save_button.grid(row=0, column=2, padx=(6, 0))

    def _build_status_bar(self, parent):
        bar = ctk.CTkFrame(parent, height=30, corner_radius=0,
                            fg_color=("#EFF1F4", "#1A1B1F"))
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)

        self.whisper_status_label = ctk.CTkLabel(
            bar, text="Whisper · loading…",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray70"),
        )
        self.whisper_status_label.pack(side="left", padx=(16, 14), pady=6)

        ctk.CTkLabel(
            bar, text=f"Ollama · gemma4",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray70"),
        ).pack(side="left", padx=(0, 14), pady=6)

        ffmpeg_text = "FFmpeg · ✅" if self.ffmpeg_available else "FFmpeg · ⚠ missing"
        ctk.CTkLabel(
            bar, text=ffmpeg_text,
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray70"),
        ).pack(side="left", padx=(0, 14), pady=6)

        self.recording_status_label = ctk.CTkLabel(
            bar, text="Idle",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray70"),
        )
        self.recording_status_label.pack(side="right", padx=16, pady=6)

    # ----- Misc helpers -----------------------------------------------

    def _bind_shortcuts(self):
        self.root.bind("<F2>", lambda e: self.toggle_recording())
        self.root.bind("<F3>", lambda e: self.transcribe_audio()
                                  if self.transcribe_button.cget("state") == "normal" else None)
        self.root.bind("<F4>", lambda e: self.analyze_medical_content()
                                  if self.analyze_button.cget("state") == "normal" else None)
        self.root.bind("<Control-s>", lambda e: self.save_transcription()
                                  if self.save_button.cget("state") == "normal" else None)
        self.root.bind("<Control-S>", lambda e: self.save_transcription()
                                  if self.save_button.cget("state") == "normal" else None)
        self.root.bind("<Control-h>", lambda e: self._open_history_window())
        self.root.bind("<Control-H>", lambda e: self._open_history_window())

    def _toggle_theme(self):
        new_mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self._theme_button.configure(text="☀️" if new_mode == "dark" else "🌙")

    def _start_recording_timer(self):
        self._recording_seconds = 0
        self._tick_recording_timer()

    def _tick_recording_timer(self):
        if not self.recording:
            return
        mm, ss = divmod(self._recording_seconds, 60)
        text = f"{mm:02d}:{ss:02d}"
        self.timer_label.configure(text=text, text_color=("#C53030", "#FC8181"))
        self.recording_status_label.configure(
            text=f"● Recording  {text}",
            text_color=("#C53030", "#FC8181"),
        )
        self._recording_seconds += 1
        self._recording_after_id = self.root.after(1000, self._tick_recording_timer)

    def _stop_recording_timer(self):
        if self._recording_after_id is not None:
            self.root.after_cancel(self._recording_after_id)
            self._recording_after_id = None
        self.timer_label.configure(text="00:00", text_color=("gray35", "gray75"))
        self.recording_status_label.configure(
            text="Idle", text_color=("gray35", "gray70"),
        )

    def _open_history_window(self):
        if getattr(self, "_history_window", None) is not None and self._history_window.winfo_exists():
            self._history_window.lift()
            self._history_window.focus()
            return
        self._history_window = ctk.CTkToplevel(self.root)
        self._history_window.title("Transcription History")
        self._history_window.geometry("680x720")

        header = ctk.CTkFrame(self._history_window, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            header, text="History",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="🔄  Refresh", width=100, height=32,
            command=self.load_history,
        ).pack(side="right")

        self.history_frame = ctk.CTkScrollableFrame(self._history_window)
        self.history_frame.pack(fill="both", expand=True, padx=14, pady=(4, 14))
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
            self.record_button.configure(
                text="⏹  Stop   (F2)",
                fg_color=("#C53030", "#9B2C2C"),
                hover_color=("#9B2C2C", "#742A2A"),
            )
            self._start_recording_timer()
            threading.Thread(target=self.recorder.record_audio, daemon=True).start()
        else:
            messagebox.showerror("Error", "Failed to start recording. Please check your microphone.")

    def stop_recording(self):
        """Stop audio recording"""
        tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tf.close()
        temp_file = tf.name
        if self.recorder.stop_recording(temp_file):
            self.recording = False
            self._stop_recording_timer()
            self.record_button.configure(
                text="⏺  Record   (F2)",
                fg_color=["#3B8ED0", "#1F6AA5"],
                hover_color=("#36719F", "#144870"),
            )
            self.current_audio_file = temp_file
            self.audio_info_label.configure(
                text=f"Recorded · {os.path.basename(temp_file)}",
                text_color=("gray25", "gray80"),
            )
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
            self.audio_info_label.configure(
                text=f"Loaded · {os.path.basename(file_path)}",
                text_color=("gray25", "gray80"),
            )
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
                    # Try to use original file as fallback. Suppress exception
                    # text and file paths from logs — they're PHI-adjacent.
                    processed_file = self.current_audio_file
                    logger.warning("Audio preprocessing failed (%s); using original file", type(e).__name__)
                
                # faster-whisper: transcribe() returns (segments_generator, info).
                # VAD filter trims long silences and hallucinations on quiet audio.
                # Beam size 5 is the recommended default for accuracy.
                result = None
                errors = []
                try:
                    segments_iter, info = self.whisper_model.transcribe(
                        processed_file,
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                    )
                    # Materialize generator (it streams as the model decodes).
                    segments = list(segments_iter)
                    full_text = "".join(seg.text for seg in segments).strip()
                    result = {
                        "text": full_text,
                        "language": info.language,
                        "segments": [
                            {
                                "id": seg.id,
                                "start": seg.start,
                                "end": seg.end,
                                "text": seg.text,
                            }
                            for seg in segments
                        ],
                    }
                except Exception as e:
                    errors.append(f"Transcription: {str(e)}")

                if result:
                    transcription_data = {
                        'filename': os.path.basename(self.current_audio_file),
                        'text': result['text'],
                        'language': result.get('language', 'unknown'),
                        'segments': result.get('segments', [])
                    }
                    
                    # Update UI on main thread
                    self.root.after(0, self.update_transcription_ui, transcription_data)
                else:
                    # All methods failed
                    error_msg = "All transcription methods failed:\n" + "\n".join(errors)
                    self.root.after(0, self.transcription_error, error_msg)
                
                # Clean up temporary file (PHI audio — best effort).
                # Don't log the path; even the temp filename is PHI-adjacent
                # because it reveals that a recording was made.
                if processed_file != self.current_audio_file and os.path.exists(processed_file):
                    try:
                        os.unlink(processed_file)
                    except OSError as cleanup_err:
                        logger.warning("Temp audio cleanup failed (%s)", type(cleanup_err).__name__)
                
            except Exception as e:
                self.root.after(0, self.transcription_error, str(e))
        
        threading.Thread(target=transcribe_worker, daemon=True).start()
    
    def update_transcription_ui(self, transcription_data):
        """Populate the editable transcript pane and unlock downstream actions."""
        self.current_transcription = transcription_data

        self.transcription_text.delete("1.0", "end")
        self.transcription_text.insert("1.0", transcription_data['text'])

        self.analyze_button.configure(state="normal")
        self.save_button.configure(state="normal")
        self.transcribe_button.configure(state="normal", text="🧠  Transcribe   (F3)")
        self.progress_bar.set(1.0)

        lang = transcription_data.get('language', 'unknown')
        self.recording_status_label.configure(
            text=f"Transcribed · language: {lang}",
            text_color=("#2F855A", "#68D391"),
        )

    def copy_soap_text(self):
        """Concatenate the four SOAP sections from their textboxes and copy."""
        parts = []
        for key, label in (("subjective", "SUBJECTIVE"), ("objective", "OBJECTIVE"),
                            ("assessment", "ASSESSMENT"), ("plan", "PLAN")):
            text = self._soap_textboxes[key].get("1.0", "end").strip()
            if text:
                parts.append(f"{label}:\n{text}")
        assembled = "\n\n".join(parts)
        if assembled:
            self.root.clipboard_clear()
            self.root.clipboard_append(assembled)
            messagebox.showinfo("Copied", "SOAP note copied to clipboard.")
        else:
            messagebox.showwarning("No Content", "SOAP note is empty.")

    def transcription_error(self, error_msg):
        """Handle transcription error"""
        self.transcribe_button.configure(state="normal", text="🧠  Transcribe   (F3)")
        self.progress_bar.set(0)
        self.recording_status_label.configure(text="Idle", text_color=("gray35", "gray70"))
        messagebox.showerror("Transcription Error", f"Failed to transcribe audio:\n{error_msg}")
    
    def analyze_medical_content(self):
        """Analyze transcription for medical content (Ollama call runs in a worker thread)"""
        if not self.current_transcription:
            return

        # Pick up edits the clinician may have made to the transcript before
        # clicking Analyze. save_transcription already does this; analyze must
        # too or Ollama receives the stale unedited text.
        edited = self.transcription_text.get("1.0", "end").strip()
        if edited:
            self.current_transcription['text'] = edited

        # Disable the button while the LLM runs — Ollama can take up to the
        # configured timeout (120s) and would otherwise freeze the UI.
        self.analyze_button.configure(state="disabled", text="Analyzing...")

        text = self.current_transcription['text']

        def analyze_worker():
            try:
                analysis = self.analyzer.analyze_text(text)
                self.root.after(0, self._on_analysis_complete, analysis)
            except Exception as e:
                self.root.after(0, self._on_analysis_error, str(e))

        threading.Thread(target=analyze_worker, daemon=True).start()

    def _on_analysis_complete(self, analysis):
        """Populate each editable SOAP section with the LLM output."""
        self.current_transcription.update(analysis)

        soap_note = analysis['soap_note']
        for key in ("subjective", "objective", "assessment", "plan"):
            box = self._soap_textboxes[key]
            box.delete("1.0", "end")
            box.insert("1.0", soap_note.get(key, ""))

        self.analyze_button.configure(state="normal", text="🏥  Analyze   (F4)")
        self.recording_status_label.configure(
            text=f"Analyzed · {len(analysis['medical_keywords'])} keywords",
            text_color=("#2F855A", "#68D391"),
        )

    def _on_analysis_error(self, error_msg):
        """Restore the UI when the analyze worker fails."""
        self.analyze_button.configure(state="normal", text="🏥  Analyze   (F4)")
        messagebox.showerror("Analysis Error", f"Failed to analyze content:\n{error_msg}")
    
    def save_transcription(self):
        """Save transcription + the (possibly clinician-edited) SOAP sections."""
        if not self.current_transcription:
            return

        # Pick up any edits made directly in the transcript and SOAP textboxes
        # before persisting. The user can correct the LLM's output before save.
        edited_transcript = self.transcription_text.get("1.0", "end").strip()
        if edited_transcript:
            self.current_transcription['text'] = edited_transcript

        soap_note = self.current_transcription.get('soap_note') or {}
        for key in ("subjective", "objective", "assessment", "plan"):
            soap_note[key] = self._soap_textboxes[key].get("1.0", "end").strip()
        self.current_transcription['soap_note'] = soap_note

        try:
            self.current_transcription['user_id'] = self.user_id
            transcription_id = self.db.save_transcription(self.current_transcription)
            messagebox.showinfo("Saved", f"Transcription saved.\nID: {transcription_id}")
            if getattr(self, "_history_window", None) is not None and self._history_window.winfo_exists():
                self.load_history()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save transcription:\n{str(e)}")

    def load_history(self):
        """Render history list inside the history window's scrollable frame."""
        if not getattr(self, "history_frame", None) or not self.history_frame.winfo_exists():
            return

        for widget in self.history_frame.winfo_children():
            widget.destroy()

        transcriptions = self.db.get_transcriptions(self.user_id)

        if not transcriptions:
            empty = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            empty.pack(fill="x", pady=40)
            ctk.CTkLabel(empty, text="📭", font=ctk.CTkFont(size=42)).pack(pady=(0, 8))
            ctk.CTkLabel(
                empty, text="No transcriptions yet",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack()
            ctk.CTkLabel(
                empty,
                text="Record or upload audio, transcribe, then save to start a record.",
                font=ctk.CTkFont(size=12),
                text_color=("gray45", "gray60"),
            ).pack(pady=(2, 0))
            return

        for trans in transcriptions:
            card = ctk.CTkFrame(self.history_frame, corner_radius=10)
            card.pack(fill="x", padx=4, pady=6)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(10, 0))

            ctk.CTkLabel(
                top, text=f"📄  {trans['filename']}",
                font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                top, text=str(trans['created_at']),
                font=ctk.CTkFont(size=11),
                text_color=("gray45", "gray60"),
            ).pack(side="right")

            ctk.CTkLabel(
                card, text=trans['text'] or "(empty transcription)",
                wraplength=580, justify="left", anchor="w",
                font=ctk.CTkFont(size=12),
                text_color=("gray30", "gray75"),
            ).pack(anchor="w", padx=14, pady=(4, 6))

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=10, pady=(0, 10))
            ctk.CTkButton(
                actions, text="Open  →", width=90, height=28,
                command=lambda t_id=trans['id']: self.view_transcription(t_id),
            ).pack(side="right")

    def view_transcription(self, transcription_id: str):
        """Open a detail window with the transcript and the four SOAP sections."""
        transcription = self.db.get_transcription_by_id(transcription_id)
        if not transcription:
            messagebox.showerror("Error", "Transcription not found")
            return

        win = ctk.CTkToplevel(self.root)
        win.title(f"{transcription['filename']}  ·  {transcription['created_at']}")
        win.geometry("780x700")

        body = ctk.CTkScrollableFrame(win)
        body.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            body, text="Transcript",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray35", "gray70"), anchor="w",
        ).pack(fill="x", padx=2, pady=(0, 4))
        t_box = ctk.CTkTextbox(body, height=180, font=ctk.CTkFont(size=13), wrap="word")
        t_box.pack(fill="x", padx=2, pady=(0, 14))
        t_box.insert("1.0", transcription['text'] or "")
        t_box.configure(state="disabled")

        soap_note = transcription.get('soap_note') or {}
        for key, label in (("subjective", "Subjective"), ("objective", "Objective"),
                            ("assessment", "Assessment"), ("plan", "Plan")):
            ctk.CTkLabel(
                body, text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("gray35", "gray70"), anchor="w",
            ).pack(fill="x", padx=2, pady=(6, 4))
            box = ctk.CTkTextbox(body, height=110, font=ctk.CTkFont(size=13), wrap="word")
            box.pack(fill="x", padx=2, pady=(0, 4))
            box.insert("1.0", soap_note.get(key, ""))
            box.configure(state="disabled")
    
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
            app = ClinicalDocumentationApp(user_id, login_window.username or "User")
            app.run()
        else:
            print("Login cancelled or failed")
        
    except Exception as e:
        print(f"Error starting application: {e}")
        messagebox.showerror("Error", f"Failed to start application:\n{str(e)}")

if __name__ == "__main__":
    main()