"""
AI Shastri — FastAPI WebSocket backend
---------------------------------------
Pipeline per conversation turn:
    Audio bytes  →  transcribe_kannada_audio   (Sarvam ASR — placeholder)
                 →  retrieve_shastra_context   (ChromaDB vector search ✅)
                 →  generate_llm_response      (Gemini 2.0 Flash ✅)
                 →  synthesize_sarvam_tts_stream (Sarvam TTS — placeholder)
"""

import asyncio
import json
import os
from typing import AsyncGenerator

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
SARVAM_API_KEY  = os.getenv("SARVAM_API_KEY")
CHROMA_PATH     = "./chroma_db"
COLLECTION_NAME = "shastra_texts"
TOP_K           = 4

gemini = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI(title="AI Shastri", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── ChromaDB setup (lazy, loaded once on first request) ────────────────────────

class GeminiEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        result = gemini.models.embed_content(
            model="gemini-embedding-001",
            contents=input,
        )
        return [e.values for e in result.embeddings]

_collection = None

def get_collection():
    global _collection
    if _collection is None:
        chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = chroma.get_collection(
            name=COLLECTION_NAME,
            embedding_function=GeminiEmbeddingFunction(),
        )
        print(f"[chroma] Loaded '{COLLECTION_NAME}' ({_collection.count()} chunks)")
    return _collection


# ── Pipeline steps ─────────────────────────────────────────────────────────────

async def transcribe_kannada_audio(audio_bytes: bytes) -> str:
    """Transcribe Kannada audio using Sarvam AI ASR."""
    print(f"[asr] transcribing {len(audio_bytes)} bytes via Sarvam")

    import httpx
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"API-Subscription-Key": SARVAM_API_KEY},
            files={"file": ("audio.webm", audio_bytes, "audio/webm")},
            data={"language_code": "kn-IN"},
        )
        response.raise_for_status()
        transcript = response.json().get("transcript", "")
        print(f"[asr] transcript: {transcript}")
        return transcript


async def retrieve_shastra_context(text: str) -> str:
    """
    Embed the (Kannada) query with text-embedding-004 and retrieve
    the top-k most relevant English passages from ChromaDB.

    text-embedding-004 is multilingual — it can match a Kannada query
    against English document embeddings cross-lingually.
    """
    print(f"[rag] querying: {text[:80]}")
    try:
        collection = get_collection()
        results = collection.query(
            query_texts=[text],
            n_results=TOP_K,
        )
        passages = results["documents"][0]   # list of top-k strings
        context  = "\n\n---\n\n".join(passages)
        print(f"[rag] retrieved {len(passages)} passages")
        return context
    except Exception as e:
        print(f"[rag] error: {e} — returning empty context")
        return ""


async def generate_llm_response(context: str, user_text: str) -> str:
    """
    Send the retrieved context + user question to Gemini 2.0 Flash.
    Instructs the model to answer in simple Kannada.
    """
    print(f"[llm] generating response for: {user_text[:80]}")

    system_prompt = """You are AI Shastri (ಎಐ ಶಾಸ್ತ್ರಿ), an expert in Indian philosophy —
specifically Madhva's Dvaita Vedanta, Shastric philosophy, and the Reign of Realism.

Rules:
- ALWAYS answer in Kannada (ಕನ್ನಡ), no matter what language the question is in.
- Keep answers concise: 2–4 sentences maximum.
- Ground your answer strictly in the provided context passages.
- Use respectful, classical Kannada — avoid overly technical Sanskrit without explanation.
- If the context does not contain enough information, say so in Kannada politely.
- Never make up facts not present in the context."""

    prompt = f"""Context from the Shastric texts:
{context}

User's question: {user_text}

Please answer in Kannada:"""

    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    answer = response.text.strip()
    print(f"[llm] response: {answer[:120]}")
    return answer


async def synthesize_sarvam_tts_stream(text: str) -> AsyncGenerator[bytes, None]:
    """Stream Kannada TTS audio using Sarvam AI (bulbul:v2)."""
    import base64
    import httpx

    print(f"[tts] synthesising via Sarvam: {text[:60]}…")

    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={
                "API-Subscription-Key": SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "inputs": [text],
                "target_language_code": "kn-IN",
                "speaker": "abhilash",
                "model": "bulbul:v2",
                "enable_preprocessing": True,
            },
        )
        if response.status_code != 200:
            print(f"[tts] Sarvam error {response.status_code}: {response.text}")
        response.raise_for_status()
        data = response.json()

    # Sarvam returns base64-encoded WAV in data["audios"][0]
    audio_b64  = data["audios"][0]
    audio_data = base64.b64decode(audio_b64)
    print(f"[tts] received {len(audio_data)} bytes of audio")

    # Stream back in 4 KB chunks
    chunk_size = 4_096
    for i in range(0, len(audio_data), chunk_size):
        yield audio_data[i : i + chunk_size]
        await asyncio.sleep(0.01)


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    print("[ws] client connected")

    audio_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                audio_buffer.extend(message["bytes"])

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                if payload.get("type") == "end":
                    print(f"[ws] end signal — {len(audio_buffer)} audio bytes buffered")

                    # ── Full pipeline ─────────────────────────────────────────
                    transcript = await transcribe_kannada_audio(bytes(audio_buffer))
                    context    = await retrieve_shastra_context(transcript)
                    response   = await generate_llm_response(context, transcript)

                    # Stream TTS audio back
                    async for chunk in synthesize_sarvam_tts_stream(response):
                        await websocket.send_bytes(chunk)

                    await websocket.close()
                    break

    except WebSocketDisconnect:
        print("[ws] client disconnected")
    except Exception as exc:
        print(f"[ws] error: {exc}")
        await websocket.close()


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    try:
        count = get_collection().count()
        db_status = f"ok ({count} chunks)"
    except Exception:
        db_status = "not ingested yet — run python ingest.py"

    return {
        "status": "ok",
        "service": "AI Shastri",
        "vector_db": db_status,
    }
