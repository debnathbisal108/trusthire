"""
TrustHire AI — Model router.
Swappable between local Ollama (VPS/dev) and OpenAI (Render/cloud).
Set LLM_PROVIDER env var to switch — zero code changes needed.
"""

import logging
from ...config import settings

logger = logging.getLogger(__name__)


def get_llm(task: str = "general"):
    """Return a LangChain-compatible LLM based on LLM_PROVIDER."""
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        from langchain_community.llms import Ollama
        return Ollama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
            num_predict=2048,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,     # gpt-4o-mini by default
            temperature=0.1,
            api_key=settings.openai_api_key,
            max_tokens=2048,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. Use 'ollama' or 'openai'."
    )


async def ainvoke_llm(prompt: str, task: str = "general") -> str:
    """Invoke LLM and return plain text response."""
    model = get_llm(task)
    response = await model.ainvoke(prompt)
    if hasattr(response, "content"):
        return response.content.strip()
    return str(response).strip()


async def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Speech-to-text.
    WHISPER_PROVIDER=local  → faster-whisper (VPS, free)
    WHISPER_PROVIDER=openai → OpenAI Whisper API (Render, ~$0.006/min)
    """
    provider = settings.whisper_provider.lower()

    if provider == "openai":
        return await _transcribe_openai(audio_bytes)
    return await _transcribe_local(audio_bytes)


async def _transcribe_openai(audio_bytes: bytes) -> str:
    """OpenAI Whisper API — works on any platform, costs ~$0.006/min."""
    try:
        from openai import AsyncOpenAI
        import io

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
        )
        return transcript.text.strip()
    except Exception as exc:
        logger.error("OpenAI Whisper error: %s", exc)
        return ""


async def _transcribe_local(audio_bytes: bytes) -> str:
    """faster-whisper — local only, requires model download."""
    try:
        from faster_whisper import WhisperModel
        import numpy as np

        model = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
        audio_np = _mulaw_to_float32(audio_bytes)
        segments, _ = model.transcribe(audio_np, language="en")
        return " ".join(s.text for s in segments).strip()
    except ImportError:
        logger.warning("faster-whisper not installed — transcription unavailable")
        return ""
    except Exception as exc:
        logger.error("Local Whisper error: %s", exc)
        return ""


def _mulaw_to_float32(data: bytes):
    import numpy as np
    BIAS = 33
    table = np.zeros(256, dtype=np.float32)
    for i in range(256):
        val = ~i & 0xFF
        sign = -1 if val & 0x80 else 1
        val &= 0x7F
        exp = (val >> 4) & 0x07
        man = val & 0x0F
        sample = sign * ((((man << 1) | 1) << (exp + 2)) - BIAS)
        table[i] = sample / 32768.0
    return table[np.frombuffer(data, dtype=np.uint8)]
