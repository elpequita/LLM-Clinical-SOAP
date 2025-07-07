# Clinical Documentation AI - Desktop Application

A comprehensive Python desktop application for medical speech-to-text transcription and SOAP note generation, featuring user authentication, remote activation, and MySQL database integration.

## 🏥 Features

### Core Features
- **Speech-to-Text Transcription**: Uses OpenAI Whisper for accurate medical transcription
- **SOAP Note Generation**: Leverages local LLM (Ollama) for structured medical documentation
- **Audio Recording**: Built-in microphone recording and file upload support
- **Medical Analysis**: Keyword extraction and medical content analysis

### Enhanced Features (New)
- **✅ Copy Button for SOAP Notes**: One-click clipboard copying with user feedback
- **✅ Remote Deactivation**: SAAS security with online activation verification
- **✅ MySQL Database Integration**: Robust database with user data isolation
- **✅ User Authentication**: Secure login system with password hashing
- **✅ Standalone Executable**: Complete .exe package with installer

### Security Features
- User authentication with secure password hashing
- Remote activation/deactivation via API
- Simple API key-based security
- Periodic activation status checks
- User session management

## 🚀 Quick Start

### 1. Install Dependencies
```bash
python install_dependencies.py
```

### 2. Setup MySQL Database
```bash
python setup_mysql.py
```

### 3. Install and Setup Ollama
```bash
# Download from https://ollama.ai/
# Then install the model:
ollama pull llama3.2
```

### 4. Start Activation Service
```bash
python activation_service.py
```

### 5. Run Application
```bash
python clinical_app.py
```

## 📋 System Requirements

- **Operating System**: Windows 10/11 (64-bit), Linux, macOS
- **Python**: 3.8 or higher
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 5GB free disk space
- **Audio**: Microphone for recording
- **Network**: Internet connection for activation
- **Database**: MySQL 5.7 or higher

## 📦 Installation Guide

### Prerequisites
1. **Python 3.8+**: Download from [python.org](https://python.org)
2. **MySQL**: Install MySQL Server
3. **Ollama**: Download from [ollama.ai](https://ollama.ai)

### Step-by-Step Installation

1. **Clone/Download Application**
   ```bash
   # Extract the application files to your desired directory
   cd clinical-documentation-ai
   ```

2. **Install Dependencies**
   ```bash
   python install_dependencies.py
   ```

3. **Setup MySQL Database**
   ```bash
   python setup_mysql.py
   ```
   - Enter MySQL root credentials
   - Database and user will be created automatically

4. **Install Ollama Model**
   ```bash
   ollama pull llama3.2
   ```

5. **Start Activation Service**
   ```bash
   python activation_service.py
   ```
   - This runs on http://localhost:5000
   - Required for license verification

6. **Run Application**
   ```bash
   python clinical_app.py
   ```

## 🔧 Configuration

### Database Configuration
Database settings are stored in `db_config.json`:
```json
{
  "host": "localhost",
  "port": 3306,
  "user": "clinical_user",
  "password": "clinical_password",
  "database": "clinical_docs"
}
```

### Activation Service
The activation service provides:
- License verification
- Remote activation/deactivation
- API key validation

**API Keys:**
- User Key: `clinical_api_key_2025`
- Admin Key: `admin_key_2025`
- Backup Key: `backup_key_2025`

### Activation Endpoints
- `GET /api/check_activation` - Check activation status
- `POST /admin/activate` - Activate application (admin)
- `POST /admin/deactivate` - Deactivate application (admin)

## 🖥️ Usage Guide

### First Time Setup
1. **Register User**: Create your account on first launch
2. **Login**: Use your credentials to access the application
3. **Test Recording**: Try the microphone recording feature
4. **Upload Audio**: Test with existing audio files

### Recording Audio
1. Click "🎤 Start Recording"
2. Speak clearly into the microphone
3. Click "⏹️ Stop Recording" when finished
4. Click "🧠 Transcribe Audio" to process

### Generating SOAP Notes
1. After transcription, click "🏥 Analyze Medical Content"
2. Review the generated SOAP note
3. Click "📋 Copy SOAP Note" to copy to clipboard
4. Click "💾 Save Transcription" to store in database

### Viewing History
- Access the "History" tab to view past transcriptions
- Click "👁️ View Details" to see full transcription and SOAP note
- All data is user-specific and secure

## 🏗️ Creating Executable

### Build Standalone Executable
```bash
python create_executable.py
```

This creates:
- `dist/ClinicalDocumentationAI.exe` - Main executable
- `installer_script.iss` - Inno Setup installer script
- `ClinicalDocumentationAI_v1.0/` - Distribution package

### Create Installer
1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Open `installer_script.iss`
3. Click "Build" to create Windows installer

## 🔐 Security Features

### User Authentication
- Secure password hashing (SHA-256)
- User session management
- Account activation/deactivation

### Remote Activation
- Periodic license verification
- Simple API key authentication
- Graceful fallback to local verification

### Data Security
- User data isolation in MySQL
- Encrypted password storage
- Secure API communications

## 🛠️ Troubleshooting

### Common Issues

**PyAudio Installation Failed (Windows)**
```bash
pip install pipwin
pipwin install pyaudio
```

**MySQL Connection Error**
- Ensure MySQL server is running
- Check credentials in `db_config.json`
- Verify user has proper permissions

**FFmpeg Not Found**
- Download from [ffmpeg.org](https://ffmpeg.org)
- Add to system PATH
- Or use portable version in app directory

**Whisper Model Loading Slow**
- Install CUDA for GPU acceleration
- Use smaller model (base instead of large)
- Ensure sufficient RAM available

**Ollama Connection Error**
- Start Ollama service: `ollama serve`
- Check model is installed: `ollama list`
- Verify service running on localhost:11434

### Performance Optimization
- Use GPU for Whisper transcription
- Increase RAM allocation
- Use SSD storage for database
- Close unnecessary applications

## 📁 File Structure

```
clinical-documentation-ai/
├── clinical_app.py          # Main application
├── llm_utils.py            # Ollama LLM integration
├── db_manager.py           # MySQL database manager
├── auth_manager.py         # User authentication
├── security_manager.py     # Remote activation
├── activation_service.py   # License server
├── setup_mysql.py          # Database setup
├── install_dependencies.py # Dependency installer
├── create_executable.py    # Executable builder
├── requirements_desktop.txt # Dependencies list
├── db_config.json         # Database configuration
└── README.md              # This file
```

## 🔄 API Reference

### Activation Service API

**Check Activation**
```bash
GET /api/check_activation
Authorization: Bearer clinical_api_key_2025
```

**Activate Application (Admin)**
```bash
POST /admin/activate
Authorization: Bearer admin_key_2025
```

**Deactivate Application (Admin)**
```bash
POST /admin/deactivate
Authorization: Bearer admin_key_2025
```

## 📊 Database Schema

### Users Table
```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

### Transcriptions Table
```sql
CREATE TABLE transcriptions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    transcription_text TEXT,
    language VARCHAR(50),
    medical_keywords JSON,
    soap_note JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'completed',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### App Settings Table
```sql
CREATE TABLE app_settings (
    id VARCHAR(36) PRIMARY KEY,
    setting_key VARCHAR(255) UNIQUE NOT NULL,
    setting_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 🎯 Development Notes

### Architecture
- **GUI**: CustomTkinter for modern desktop interface
- **Audio**: PyAudio for recording, Whisper for transcription
- **Database**: MySQL with connection pooling
- **LLM**: Ollama for local SOAP note generation
- **Security**: JWT-style API key authentication

### Extension Points
- Add more LLM models
- Implement voice commands
- Add template customization
- Integrate with EHR systems
- Add multi-language support

## 📄 License

This application is proprietary software with remote activation licensing.

## 🤝 Support

For technical support and issues:
- Check troubleshooting section
- Review log files
- Contact development team

---

**Version**: 1.0.0  
**Last Updated**: March 2025  
**Python Version**: 3.8+  
**Platform**: Windows 10/11, Linux, macOS