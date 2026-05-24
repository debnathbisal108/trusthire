from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    domain: str = "trusthire-bdbp.onrender.com"
    frontend_url: str = "https://trusthire-bdbp.onrender.com"
    log_level: str = "INFO"

    # Database
    database_url: str
    redis_url: str

    # Auth
    nextauth_secret: str = ""
    jwt_algorithm: str = "HS256"

    # ── LLM ───────────────────────────────────────────────────────────────
    # Local dev:   LLM_PROVIDER=ollama  LLM_MODEL=llama3.2:8b
    # Render/prod: LLM_PROVIDER=openai  OPENAI_API_KEY=sk-...
    llm_provider: str = "openai"           # default to openai for Render
    llm_model: str = "gpt-4o-mini"        # cheap + fast
    ollama_base_url: str = "http://ollama:11434"
    openai_api_key: str = ""

    # ── STT / TTS (cloud only on Render — local on VPS) ──────────────────
    # Render: use OpenAI Whisper API  (set WHISPER_PROVIDER=openai)
    # VPS:    use faster-whisper      (set WHISPER_PROVIDER=local)
    whisper_provider: str = "openai"       # openai | local
    whisper_model_size: str = "base"       # only used when provider=local
    piper_model_path: str = "/models/piper/en_US-amy-medium.onnx"

    # ── S3-compatible storage ─────────────────────────────────────────────
    # Cloudflare R2: set S3_ENDPOINT_URL=https://ACCOUNT.r2.cloudflarestorage.com
    # Local MinIO:   set S3_ENDPOINT_URL=http://minio:9000
    # AWS S3:        leave S3_ENDPOINT_URL empty
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin123"
    s3_bucket: str = "trusthire-documents"
    s3_region: str = "auto"               # "auto" for R2, "us-east-1" for S3

    # ── Vector DB ─────────────────────────────────────────────────────────
    # Local:        http://qdrant:6333
    # Qdrant Cloud: https://xxxx.us-east4-0.gcp.cloud.qdrant.io
    qdrant_url: str = "https://60be325c-1cb9-4b61-88cc-f09ac03c4375.sa-east-1-0.aws.cloud.qdrant.io"
    qdrant_api_key: str = ""

    # ── Twilio ────────────────────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    webhook_base_url: str = "https://trusthire-bdbp.onrender.com"

    # ── Email ─────────────────────────────────────────────────────────────
    email_provider: str = "smtp"
    resend_api_key: str = ""
    from_email: str = "verify@example.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    # ── Security ──────────────────────────────────────────────────────────
    encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
