"""
TrustHire AI — Model router.
Swappable between local Ollama (VPS/dev) and OpenAI (Render/cloud).
Set LLM_PROVIDER env var to switch — zero code changes needed.
"""

import logging
from ...config import settings

logger = logging.getLogger(__name__)


def get_llm(task: str = "general"):
    provider = settings.llm_provider.lower()

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.llm_model or _groq_model_for_task(task),
            temperature=0.1,
            api_key=settings.groq_api_key,
            max_tokens=2048,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model or "gemini-1.5-flash",
            temperature=0.1,
            google_api_key=settings.gemini_api_key,
            max_output_tokens=2048,
        )

    if provider == "cohere":
        from langchain_cohere import ChatCohere
        return ChatCohere(
            model=settings.llm_model or "command-r",
            temperature=0.1,
            cohere_api_key=settings.cohere_api_key,
        )

    if provider == "mistral":
        from langchain_community.chat_models import ChatMistralAI
        return ChatMistralAI(
            model=settings.llm_model or "mistral-small-latest",
            temperature=0.1,
            mistral_api_key=settings.mistral_api_key,
        )

    if provider == "ollama":
        from langchain_community.llms import Ollama
        return Ollama(
            model=settings.llm_model or "llama3.2:8b",
            base_url=settings.ollama_base_url,
            temperature=0.1,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model or "gpt-4o-mini",
            temperature=0.1,
            api_key=settings.openai_api_key,
            max_tokens=2048,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
    
def _groq_model_for_task(task: str) -> str:
    return {
        "extraction": "llama-3.1-8b-instant",
        "email":      "llama-3.1-8b-instant",
        "voice":      "llama-3.1-8b-instant",
        "fraud":      "llama-3.3-70b-versatile",
        "report":     "llama-3.3-70b-versatile",
    }.get(task, "llama-3.3-70b-versatile")

async def ainvoke_llm(prompt: str, task: str = "general") -> str:
    try:
        model = get_llm(task)
        response = await model.ainvoke(prompt)
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response).strip()
    except Exception as primary_exc:
        logger.warning("Primary LLM (%s) failed: %s", settings.llm_provider, primary_exc)
        return await _fallback_llm(prompt, task, primary_exc)


async def _fallback_llm(prompt: str, task: str, original_exc: Exception) -> str:
    chain = []
    if settings.llm_provider != "groq" and settings.groq_api_key:
        chain.append(("groq", _invoke_groq(prompt, task)))
    if settings.llm_provider != "gemini" and settings.gemini_api_key:
        chain.append(("gemini", _invoke_gemini(prompt)))
    if settings.llm_provider != "cohere" and settings.cohere_api_key:
        chain.append(("cohere", _invoke_cohere(prompt)))

    for name, coro in chain:
        try:
            return await coro
        except Exception as exc:
            logger.warning("Fallback %s failed: %s", name, exc)

    raise RuntimeError(f"All LLM providers failed. Original: {original_exc}")


async def _invoke_groq(prompt: str, task: str) -> str:
    from langchain_groq import ChatGroq
    m = ChatGroq(model=_groq_model_for_task(task), temperature=0.1, api_key=settings.groq_api_key)
    r = await m.ainvoke(prompt)
    return r.content.strip()


async def _invoke_gemini(prompt: str) -> str:
    from langchain_google_genai import ChatGoogleGenerativeAI
    m = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.1, google_api_key=settings.gemini_api_key)
    r = await m.ainvoke(prompt)
    return r.content.strip()


async def _invoke_cohere(prompt: str) -> str:
    from langchain_cohere import ChatCohere
    m = ChatCohere(model="command-r", temperature=0.1, cohere_api_key=settings.cohere_api_key)
    r = await m.ainvoke(prompt)
    return r.content.strip()


async def transcribe_audio(audio_bytes: bytes) -> str:
    provider = settings.whisper_provider.lower()
    if provider == "groq":
        return await _transcribe_groq(audio_bytes)
    if provider == "openai":
        return await _transcribe_openai(audio_bytes)
    if provider == "local":
        return await _transcribe_local(audio_bytes)
    return await _transcribe_groq(audio_bytes)


async def _transcribe_groq(audio_bytes: bytes) -> str:
    """Free Whisper via Groq — same API key as LLM. 7,200 sec/day free."""
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        transcription = await client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text",
        )
        return str(transcription).strip()
    except Exception as exc:
        logger.error("Groq Whisper error: %s", exc)
        return ""


async def _transcribe_openai(audio_bytes: bytes) -> str:
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        transcript = await client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, language="en"
        )
        return transcript.text.strip()
    except Exception as exc:
        logger.error("OpenAI Whisper error: %s", exc)
        return ""


async def _transcribe_local(audio_bytes: bytes) -> str:
    try:
        from faster_whisper import WhisperModel
        import numpy as np
        model = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
        audio_np = _mulaw_to_float32(audio_bytes)
        segments, _ = model.transcribe(audio_np, language="en")
        return " ".join(s.text for s in segments).strip()
    except Exception as exc:
        logger.error("Local Whisper error: %s", exc)
        return ""


def _mulaw_to_float32(data: bytes):
    import numpy as np
    table = np.zeros(256, dtype=np.float32)
    for i in range(256):
        val = ~i & 0xFF
        sign = -1 if val & 0x80 else 1
        val &= 0x7F
        exp = (val >> 4) & 0x07
        man = val & 0x0F
        sample = sign * ((((man << 1) | 1) << (exp + 2)) - 33)
        table[i] = sample / 32768.0
    return table[np.frombuffer(data, dtype=np.uint8)]
