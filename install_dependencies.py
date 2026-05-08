"""
Dependency installer for the clinical documentation desktop application
"""

import subprocess
import sys
import os
import platform
import importlib.util

def install_package(package_name, pip_name=None):
    """Install a Python package using pip"""
    if pip_name is None:
        pip_name = package_name
    
    try:
        # Check if package is already installed
        spec = importlib.util.find_spec(package_name)
        if spec is not None:
            print(f"✅ {package_name} is already installed")
            return True
    except ImportError:
        pass
    
    try:
        print(f"📦 Installing {pip_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        print(f"✅ {pip_name} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {pip_name}: {e}")
        return False

def install_system_dependencies():
    """Install system-level dependencies"""
    system = platform.system().lower()
    
    print(f"🖥️ Detected system: {system}")
    
    if system == "windows":
        print("🪟 Windows-specific setup:")
        print("   - Make sure Microsoft Visual C++ Redistributables are installed")
        print("   - PyAudio may require additional setup")
        
        # Try to install PyAudio for Windows
        try:
            print("📦 Installing PyAudio for Windows...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyaudio"])
            print("✅ PyAudio installed successfully")
        except subprocess.CalledProcessError:
            print("❌ PyAudio installation failed")
            print("💡 Try installing manually:")
            print("   pip install pipwin")
            print("   pipwin install pyaudio")
    
    elif system == "linux":
        print("🐧 Linux-specific setup:")
        print("   Install system dependencies:")
        print("   sudo apt-get update")
        print("   sudo apt-get install portaudio19-dev python3-pyaudio")
        print("   sudo apt-get install ffmpeg")
        
        # Check if running in a container or have sudo access
        try:
            subprocess.check_call(["which", "apt-get"], stdout=subprocess.DEVNULL)
            print("   Run the above commands before proceeding")
        except subprocess.CalledProcessError:
            print("   Use your distribution's package manager")
    
    elif system == "darwin":  # macOS
        print("🍎 macOS-specific setup:")
        print("   Install system dependencies:")
        print("   brew install portaudio")
        print("   brew install ffmpeg")
        
        try:
            subprocess.check_call(["which", "brew"], stdout=subprocess.DEVNULL)
            print("   Run the above commands before proceeding")
        except subprocess.CalledProcessError:
            print("   Install Homebrew first: https://brew.sh/")

def install_python_dependencies():
    """Install Python dependencies"""
    print("🐍 Installing Python dependencies...")
    
    # Core dependencies
    dependencies = [
        ("customtkinter", "customtkinter==5.2.0"),
        ("requests", "requests>=2.31.0"),
        ("flask", "flask==3.0.0"),
        ("mysql.connector", "mysql-connector-python==8.2.0"),
        ("pydub", "pydub==0.25.1"),
        ("numpy", "numpy>=1.24.0"),
        ("torch", "torch==2.1.0"),
        ("whisper", "openai-whisper==20240930"),
        ("PIL", "Pillow>=10.0.0"),
        ("dotenv", "python-dotenv>=1.0.0"),
    ]
    
    success_count = 0
    
    for package_name, pip_name in dependencies:
        if install_package(package_name, pip_name):
            success_count += 1
    
    print(f"\n📊 Installation Summary:")
    print(f"   ✅ {success_count}/{len(dependencies)} packages installed successfully")
    
    if success_count < len(dependencies):
        print("⚠️ Some packages failed to install. Please install them manually.")
        return False
    
    return True

def check_ffmpeg():
    """Check if FFmpeg is available"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg is available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found")
        return False

def install_ffmpeg():
    """Provide FFmpeg installation instructions"""
    system = platform.system().lower()
    
    print("🎬 FFmpeg Installation:")
    
    if system == "windows":
        print("🪟 Windows:")
        print("   1. Download from https://www.gyan.dev/ffmpeg/builds/")
        print("   2. Extract to C:\\ffmpeg")
        print("   3. Add C:\\ffmpeg\\bin to system PATH")
        print("   OR use chocolatey: choco install ffmpeg")
    
    elif system == "linux":
        print("🐧 Linux:")
        print("   sudo apt-get install ffmpeg")
        print("   OR: sudo yum install ffmpeg")
    
    elif system == "darwin":
        print("🍎 macOS:")
        print("   brew install ffmpeg")

def create_desktop_shortcut():
    """Create desktop shortcut (Windows only)"""
    if platform.system().lower() != "windows":
        return
    
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Clinical Documentation AI.lnk")
        target = os.path.join(os.getcwd(), "clinical_app.py")
        wDir = os.getcwd()
        icon = target
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{target}"'
        shortcut.WorkingDirectory = wDir
        shortcut.IconLocation = icon
        shortcut.save()
        
        print("🖥️ Desktop shortcut created")
        
    except ImportError:
        print("⚠️ Could not create desktop shortcut (missing winshell)")
    except Exception as e:
        print(f"⚠️ Could not create desktop shortcut: {e}")

def main():
    """Main installation function"""
    print("🏥 Clinical Documentation AI - Dependency Installer")
    print("===================================================")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Install system dependencies
    install_system_dependencies()
    
    # Install Python dependencies
    print("\n" + "="*50)
    if not install_python_dependencies():
        print("❌ Dependency installation failed")
        sys.exit(1)
    
    # Check FFmpeg
    print("\n" + "="*50)
    if not check_ffmpeg():
        install_ffmpeg()
    
    # Create desktop shortcut
    create_desktop_shortcut()
    
    print("\n🎉 Installation completed!")
    print("\n📋 Next steps:")
    print("   1. Set up MySQL database: python setup_mysql.py")
    print("   2. Install Ollama: https://ollama.ai/")
    print("   3. Pull Ollama model: ollama pull gemma4")
    print("   4. Start activation service: python activation_service.py")
    print("   5. Run application: python clinical_app.py")
    
    print("\n🔧 Troubleshooting:")
    print("   - If PyAudio fails on Windows, try: pip install pipwin && pipwin install pyaudio")
    print("   - If MySQL connection fails, check MySQL server is running")
    print("   - If Whisper is slow, install CUDA for GPU acceleration")

if __name__ == "__main__":
    main()