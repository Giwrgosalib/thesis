# 📦 Installation Guide: eBay AI Assistant

This project includes a **One-Click Installer** for Windows to simplify the setup of both the Python Backend (NextGen GPU) and Vue.js Frontend.

## ✅ Prerequisites

Before running the installer, ensure you have:

1.  **Python 3.10+**: [Download Here](https://www.python.org/downloads/) (Make sure to check "Add Python to PATH").
2.  **Node.js (LTS)**: [Download Here](https://nodejs.org/) (Required for the frontend interface).
3.  **NVIDIA Driver**: Latest drivers for your GPU (Required for AI acceleration).

---

## 🚀 Quick Start (Automatic)

**Step 1. Run the Installer**
Double-click `setup_windows.bat` in this folder.

- It creates a virtual environment.
- It installs PyTorch with **CUDA/GPU support**.
- It installs all backend and frontend dependencies.

**Step 2. Configure Credentials**
Create a file named `ebay-credentials.yaml` in this root folder:

```yaml
appid: "YOUR_EBAY_APP_ID"
devid: "YOUR_EBAY_DEV_ID"
certid: "YOUR_EBAY_CERT_ID"
ruaname: "YOUR_RUA_NAME"
token: "YOUR_OAUTH_USER_TOKEN"
refresh_token: "YOUR_REFRESH_TOKEN"
```

**Step 3. Start Secure Tunnel (Critical)**
For "Sign in with eBay" to work, you must run ngrok with your specific domain.
Double-click `start_ngrok.bat` or run:

```powershell
.\start_ngrok.bat
```

_Keep this window open._

**Step 4. Run the App**
Open a terminal and run:

```powershell
python scripts/start_dev.py
```

Open your browser to `http://localhost:8080`.

---

## 🛠️ Manual Setup (If installer fails)

If you prefer to install manually, follow these commands:

### 1. Backend Setup

```powershell
python -m venv venv
.\venv\Scripts\activate

# Install GPU-Accelerated PyTorch (Critical!)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install other requirements
pip install -r backend/requirements.txt
```

### 2. Frontend Setup

```powershell
cd frontend
npm install
cd ..
```

### 3. Running

```powershell
.\venv\Scripts\activate
python scripts/start_dev.py
```

---

## 🐳 Docker Setup (Alternative)

If you have Docker Desktop installed, you can run the entire system (Backend + Frontend) in containers.

**Prerequisites:**

- Docker Desktop with **WSL 2** backend.
- NVIDIA Container Toolkit (for GPU support).

**Run:**

```powershell
docker-compose up --build
```

- **Backend**: `http://localhost:5000`
- **Frontend**: `http://localhost:8080`
