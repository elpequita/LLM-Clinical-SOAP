"""
Script to create standalone executable for the clinical documentation application
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def create_spec_file():
    """Create PyInstaller spec file"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['clinical_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('db_config.json', '.'),
        ('*.py', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'mysql.connector',
        'whisper',
        'torch',
        'numpy',
        'pydub',
        'pyaudio',
        'requests',
        'PIL',
        'tkinter',
        'threading',
        'json',
        'hashlib',
        'uuid',
        'datetime',
        'tempfile',
        'wave',
        'pathlib',
        'shutil',
        'subprocess',
        'os',
        'sys',
        'time',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ClinicalDocumentationAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
'''
    
    with open('clinical_app.spec', 'w') as f:
        f.write(spec_content)
    
    print("✅ PyInstaller spec file created")

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✅ PyInstaller is already installed")
        return True
    except ImportError:
        print("📦 Installing PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✅ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install PyInstaller")
            return False

def create_executable():
    """Create standalone executable"""
    if not install_pyinstaller():
        return False
    
    print("🏗️ Creating executable...")
    
    # Create spec file
    create_spec_file()
    
    # Run PyInstaller
    try:
        cmd = [sys.executable, "-m", "PyInstaller", "clinical_app.spec", "--clean"]
        subprocess.check_call(cmd)
        print("✅ Executable created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create executable: {e}")
        return False

def create_installer():
    """Create installer using Inno Setup (Windows only)"""
    if platform.system().lower() != "windows":
        print("⚠️ Installer creation is only supported on Windows")
        return False
    
    # Create Inno Setup script
    iss_content = '''
[Setup]
AppName=Clinical Documentation AI
AppVersion=1.0
DefaultDirName={pf}\\Clinical Documentation AI
DefaultGroupName=Clinical Documentation AI
UninstallDisplayIcon={app}\\ClinicalDocumentationAI.exe
Compression=lzma2
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=ClinicalDocumentationAI_Setup

[Files]
Source: "dist\\ClinicalDocumentationAI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "db_config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "activation_service.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements_desktop.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\\Clinical Documentation AI"; Filename: "{app}\\ClinicalDocumentationAI.exe"
Name: "{group}\\Activation Service"; Filename: "{sys}\\cmd.exe"; Parameters: "/k cd /d ""{app}"" && python activation_service.py"
Name: "{group}\\Uninstall"; Filename: "{uninstallexe}"
Name: "{commondesktop}\\Clinical Documentation AI"; Filename: "{app}\\ClinicalDocumentationAI.exe"

[Run]
Filename: "{app}\\ClinicalDocumentationAI.exe"; Description: "Launch Clinical Documentation AI"; Flags: postinstall nowait skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not FileExists(ExpandConstant('{sys}\\python.exe')) then
  begin
    if MsgBox('Python is not installed. Do you want to download it now?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://www.python.org/downloads/', '', '', SW_SHOW, ewNoWait, ErrorCode);
      Result := False;
    end;
  end;
end;
'''
    
    with open('installer_script.iss', 'w') as f:
        f.write(iss_content)
    
    print("✅ Inno Setup script created")
    print("📋 To create installer:")
    print("   1. Install Inno Setup from https://jrsoftware.org/isinfo.php")
    print("   2. Open installer_script.iss in Inno Setup")
    print("   3. Click 'Build' to create installer")
    
    return True

def optimize_executable():
    """Optimize the executable"""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("❌ Dist directory not found")
        return False
    
    exe_path = dist_dir / "ClinicalDocumentationAI.exe"
    if not exe_path.exists():
        print("❌ Executable not found")
        return False
    
    # Check executable size
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"📊 Executable size: {size_mb:.1f} MB")
    
    if size_mb > 500:
        print("⚠️ Executable is quite large. Consider:")
        print("   - Excluding unused modules")
        print("   - Using virtual environment")
        print("   - Splitting into multiple files")
    
    return True

def create_distribution_package():
    """Create distribution package"""
    print("📦 Creating distribution package...")
    
    # Create distribution directory
    dist_name = "ClinicalDocumentationAI_v1.0"
    dist_path = Path(dist_name)
    
    if dist_path.exists():
        shutil.rmtree(dist_path)
    
    dist_path.mkdir()
    
    # Copy files
    files_to_copy = [
        "dist/ClinicalDocumentationAI.exe",
        "activation_service.py",
        "setup_mysql.py",
        "install_dependencies.py",
        "requirements_desktop.txt",
        "README.md",
        "db_config.json"
    ]
    
    for file_path in files_to_copy:
        src = Path(file_path)
        if src.exists():
            if src.is_file():
                shutil.copy2(src, dist_path / src.name)
            else:
                shutil.copytree(src, dist_path / src.name)
    
    # Create README for distribution
    readme_content = '''
# Clinical Documentation AI - Desktop Application

## Quick Start

1. **Install Dependencies**
   - Run: `python install_dependencies.py`
   - This will install all required Python packages

2. **Setup MySQL Database**
   - Run: `python setup_mysql.py`
   - Follow the prompts to configure MySQL

3. **Install Ollama**
   - Download from: https://ollama.ai/
   - Install and run: `ollama pull gemma4`

4. **Start Activation Service**
   - Run: `python activation_service.py`
   - This runs the licensing service

5. **Run Application**
   - Double-click `ClinicalDocumentationAI.exe`
   - OR run: `python clinical_app.py`

## System Requirements

- Windows 10/11 (64-bit)
- Python 3.8 or higher
- 4GB RAM minimum, 8GB recommended
- 5GB free disk space
- Microphone for audio recording
- Internet connection for activation

## Features

- Speech-to-text transcription using Whisper
- SOAP note generation using local LLM
- MySQL database for secure storage
- User authentication system
- Remote activation/deactivation
- Copy SOAP notes to clipboard
- Standalone executable

## Support

For technical support, please contact the development team.
'''
    
    with open(dist_path / "README.txt", "w") as f:
        f.write(readme_content)
    
    print(f"✅ Distribution package created: {dist_name}")
    return True

def main():
    """Main function"""
    print("🏥 Clinical Documentation AI - Executable Creator")
    print("=================================================")
    
    # Check if we're in the right directory
    if not os.path.exists("clinical_app.py"):
        print("❌ clinical_app.py not found. Please run from the application directory.")
        sys.exit(1)
    
    # Create executable
    if not create_executable():
        print("❌ Failed to create executable")
        sys.exit(1)
    
    # Optimize executable
    optimize_executable()
    
    # Create installer script
    create_installer()
    
    # Create distribution package
    create_distribution_package()
    
    print("\n🎉 Executable creation completed!")
    print("\n📋 Files created:")
    print("   - dist/ClinicalDocumentationAI.exe (Main executable)")
    print("   - installer_script.iss (Inno Setup script)")
    print("   - ClinicalDocumentationAI_v1.0/ (Distribution package)")
    
    print("\n📋 Next steps:")
    print("   1. Test the executable: dist/ClinicalDocumentationAI.exe")
    print("   2. Create installer with Inno Setup")
    print("   3. Test on a clean Windows system")
    print("   4. Distribute the installation package")

if __name__ == "__main__":
    main()