# Project V - Virtual Executive General Assistant

Project V is a sleek, AI-powered desktop assistant designed for modern workstations. Built on the Google ADK framework, it integrates voice interaction, real-time system telemetry, and autonomous context awareness into a unified dashboard.

## 🚀 Key Features

- **Voice Command Nexus**: Intuitive hands-free interaction with high-precision wake word detection using `openWakeWord`.
- **Real-time Telemetry HUD**: Constant monitoring of CPU, RAM, Disk, GPU, and Network activity through a futuristic glassmorphism interface.
- **Autonomous Context Observer**: Monitors your active window and system state to proactively suggest relevant actions and tool routes.
- **Dynamic Scene Transitions**: Shift your entire workstation between 'Focus', 'Work', or 'Unwind' modes with a single command.
- **Parallel Multi-Agent Brain**: Decoupled backend architecture allows Project V to speak and act simultaneously for zero-latency feedback.

## 🛠️ Tech Stack

### Backend
- **Framework**: Python 3.11+ / FastAPI / Socket.IO
- **AI Core**: Google Gemini 2.x (LLM) / Google Cloud TTS / openWakeWord
- **OS Integration**: psutil / PyAutoGUI / aiosqlite

### Frontend
- **Framework**: React 18+ / Vite / TypeScript
- **Styling**: Tailwind CSS / Lucide Icons / Framer Motion
- **Communication**: Socket.IO Client

## 📦 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Gemini API Key](https://aistudio.google.com/app/apikey)
- Google Cloud TTS Credentials (optional for premium voices)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd "Project V"
   ```

2. **Backend Setup**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
   Create a `.env` file in the `backend` folder:
   ```env
   GEMINI_API_KEY=your_key_here
   ```

3. **Frontend Setup**:
   ```bash
   cd ../frontend
   npm install
   ```

### Running Project V

1. **Start the Backend**:
   ```bash
   cd backend
   python main.py
   ```

2. **Start the Frontend**:
   ```bash
   cd ../frontend
   npm run dev
   ```

3. **Access the HUD**:
   Open your browser to `http://localhost:5173`.

## 📜 License

MIT License - Copyright (c) 2026 Project V Team.
