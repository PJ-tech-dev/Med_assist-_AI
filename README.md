# MedAssist AI 🏥
**A Multi-Agent Intelligent Healthcare Assistant for Patient Care Automation**

MedAssist AI is a state-of-the-art, multi-agent AI system designed to revolutionize patient care, emergency response, and medical record management. Built with a powerful **FastAPI & LangGraph backend** and a stunning, highly responsive **Next.js frontend**, MedAssist acts as a 24/7 autonomous medical companion.

---

## ✨ Core Features

### 🚨 Real-Time Emergency SOS & Triage
- **Keyword & Symptom Detection:** Instantly detects critical symptoms (e.g., "heart attack", "chest pain", "can't breathe") through natural language chat.
- **Native WhatsApp Integration:** Instantly launches the WhatsApp Desktop app via native deep-linking to message emergency contacts with pre-filled data and live GPS coordinates.
- **Backend Twilio Fallback:** A dedicated backend service ensures that automated emergency text messages are dispatched securely via the Twilio API.
- **Location & Hospital Routing:** Automatically fetches your live GPS coordinates and provides immediate directions to the nearest hospitals.

### 🤖 Multi-Agent LLM Architecture
Powered by LangGraph and Gemini/GPT models, MedAssist uses a swarm of specialized AI agents:
1. **Orchestrator Agent:** The brain of the system that routes user intents to the correct specialized sub-agent.
2. **Emergency Triage Agent:** Rapidly assesses critical conditions and triggers SOS protocols.
3. **Report Analysis Agent:** Parses uploaded medical documents to extract lab values and flag anomalies.
4. **Medicine Safety Agent:** Checks drug interactions and verifies prescription safety.
5. **Pharmacy Order Agent:** Assists in locating and ordering medications.

### 📄 Intelligent Medical Report Analysis (OCR)
- Upload blood tests, MRI reports, and general clinical documents.
- The system permanently stores the reports and utilizes advanced Optical Character Recognition (OCR) and LLMs to extract critical biomarkers (WBC, RBC, Glucose, etc.).
- Results are automatically cross-referenced against normal ranges and permanently logged in the patient's medical history for longitudinal data analysis.

### 💊 Pharmacy & Medication Management
- Real-time search for medicines with external PharmEasy integration.
- Track active prescriptions, dosage schedules, and set up daily medication reminders.

---

## 🛠️ Technology Stack

**Frontend:**
- Next.js (App Router), React, TypeScript
- TailwindCSS, Framer Motion (Micro-animations)
- Lucide Icons
- LocalStorage state persistence

**Backend:**
- Python 3, FastAPI, Uvicorn
- LangChain & LangGraph (Multi-Agent framework)
- Google Gemini API / Puter AI integrations
- Twilio API for emergency SMS/WhatsApp dispatch
- SQLite (local development) / MongoDB (production data persistence)

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Google Gemini API Key
- Twilio Account Credentials (Optional, for backend SOS dispatch)

### Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/PJ-tech-dev/Med_assist-_AI.git
   cd Med_assist-_AI
   ```

2. **Start the Backend:**
   ```bash
   python main.py
   ```
   *(This script automatically sets up your Python virtual environment, installs dependencies from `requirements.txt`, and launches the FastAPI server on `localhost:8000`)*

3. **Start the Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   *(The Next.js application will be available at `localhost:3000`)*

---

## 🔒 Security & Privacy
- **API Keys are not hardcoded:** The application requires API keys to be provided via Environment Variables or secure local client storage.
- **No unprompted popups:** The SOS emergency redirect adheres to modern browser security policies, leveraging native app URIs (`whatsapp://send`) to ensure immediate action without popup blockers interfering.

---
*Developed for intelligent, automated, and empathetic healthcare.*
