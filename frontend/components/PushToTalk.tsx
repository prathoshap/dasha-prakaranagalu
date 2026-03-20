'use client';

import { useRef, useState, useCallback } from 'react';

type Status = 'idle' | 'recording' | 'processing' | 'playing';

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws/chat';

export default function PushToTalk() {
  const [status, setStatus] = useState<Status>('idle');

  const wsRef            = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef   = useRef<Uint8Array[]>([]);
  const audioCtxRef      = useRef<AudioContext | null>(null);
  const streamRef        = useRef<MediaStream | null>(null);

  // ── Audio playback ────────────────────────────────────────────────────────
  const playAudio = useCallback(async (chunks: Uint8Array[]) => {
    if (chunks.length === 0) return;

    audioCtxRef.current ??= new AudioContext();
    const ctx = audioCtxRef.current;

    // Concatenate all received chunks into one buffer
    const totalLen = chunks.reduce((n, c) => n + c.length, 0);
    const combined = new Uint8Array(totalLen);
    let offset = 0;
    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.length;
    }

    try {
      const audioBuffer = await ctx.decodeAudioData(combined.buffer);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      source.start();
      source.onended = () => setStatus('idle');
    } catch (err) {
      console.error('[PushToTalk] Audio decode error:', err);
      setStatus('idle');
    }
  }, []);

  // ── Start recording ───────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    if (status !== 'idle') return;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
    } catch {
      console.error('[PushToTalk] Microphone access denied');
      return;
    }

    audioChunksRef.current = [];

    const ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      // Start capturing audio once WebSocket is open
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data); // stream audio chunk to backend
        }
      };

      recorder.start(100); // emit chunks every 100 ms
      setStatus('recording');
    };

    // Receive TTS audio chunks from backend
    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        audioChunksRef.current.push(new Uint8Array(event.data));
      }
    };

    // WebSocket closed → all audio received → play it
    ws.onclose = async () => {
      stream.getTracks().forEach((t) => t.stop());
      if (audioChunksRef.current.length > 0) {
        setStatus('playing');
        await playAudio(audioChunksRef.current);
      } else {
        setStatus('idle');
      }
    };

    ws.onerror = (err) => {
      console.error('[PushToTalk] WebSocket error:', err);
      stream.getTracks().forEach((t) => t.stop());
      setStatus('idle');
    };
  }, [status, playAudio]);

  // ── Stop recording ────────────────────────────────────────────────────────
  const stopRecording = useCallback(() => {
    if (status !== 'recording') return;

    mediaRecorderRef.current?.stop();
    setStatus('processing');

    // Tell the backend the user has finished speaking.
    // Do NOT close the WebSocket here — the server closes it after
    // streaming the full TTS response back.
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'end' }));
    }
  }, [status]);

  // ── Derived UI state ──────────────────────────────────────────────────────
  const label: Record<Status, string> = {
    idle:       'Hold to speak',
    recording:  'Listening…',
    processing: 'Thinking…',
    playing:    'Speaking…',
  };

  const isActive    = status === 'recording';
  const isDisabled  = status === 'processing' || status === 'playing';

  return (
    <div className="flex flex-col items-center gap-6 select-none">
      {/* Ripple rings behind the button */}
      <div className="relative flex items-center justify-center">
        {isActive && (
          <>
            <span className="ripple absolute inline-flex h-24 w-24 rounded-full bg-orange-500 opacity-30" />
            <span className="ripple absolute inline-flex h-24 w-24 rounded-full bg-orange-500 opacity-20 [animation-delay:0.4s]" />
          </>
        )}

        <button
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
          onTouchEnd={(e)   => { e.preventDefault(); stopRecording();  }}
          disabled={isDisabled}
          aria-label="Push to talk"
          className={[
            'relative z-10 flex h-20 w-20 items-center justify-center rounded-full',
            'transition-all duration-150 focus:outline-none shadow-lg',
            isActive
              ? 'bg-red-600 scale-110 shadow-red-900'
              : isDisabled
              ? 'bg-stone-700 cursor-not-allowed opacity-60'
              : 'bg-saffron-600 hover:bg-saffron-500 active:scale-95 shadow-orange-900',
          ].join(' ')}
        >
          {/* Mic icon */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="h-8 w-8 text-white"
          >
            <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4Z" />
            <path d="M19 10a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.93V19H9a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.07A7 7 0 0 0 19 10Z" />
          </svg>
        </button>
      </div>

      {/* Status label */}
      <p
        className={[
          'text-sm font-medium tracking-wide transition-colors duration-300',
          isActive ? 'text-red-400' : 'text-stone-400',
        ].join(' ')}
      >
        {label[status]}
      </p>
    </div>
  );
}
