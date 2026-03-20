# AI Shastri 🕉️

An end-to-end conversational AI for Kannada Shastric philosophy. Speak in Kannada, get wisdom back.

## Architecture

```
frontend/   → Next.js 14 (App Router) + Tailwind CSS
backend/    → Python FastAPI + WebSocket
```

**Pipeline (per conversation turn):**
```
User mic → WebSocket → Sarvam ASR → RAG retrieval → LLM → Sarvam TTS → WebSocket → Browser audio
```

---

## Prerequisites

- Node.js 18+
- Python 3.10+
- pip

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your API keys
```

### 2. Frontend

```bash
cd frontend
npm install
```

---

## Running

### Backend (terminal 1)

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Frontend (terminal 2)

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## WebSocket Protocol

| Direction       | Format         | Description                        |
|----------------|----------------|------------------------------------|
| Client → Server | binary         | Raw audio chunks (webm/opus)       |
| Client → Server | JSON `{"type":"end"}` | Signals end of user speech  |
| Server → Client | binary         | Streaming TTS audio bytes (WAV)    |

---

## Roadmap

- [ ] Sarvam AI ASR (Kannada transcription)
- [ ] Vector DB + RAG for Shastric texts
- [ ] LLM response generation (Claude / GPT-4o)
- [ ] Sarvam AI TTS (Kannada speech synthesis)
- [ ] Auth + conversation history
