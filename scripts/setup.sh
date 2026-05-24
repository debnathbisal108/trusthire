#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# TrustHire AI — One-command setup script
# Usage: chmod +x scripts/setup.sh && ./scripts/setup.sh
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo ""
echo "  ████████╗██████╗ ██╗   ██╗███████╗████████╗██╗  ██╗██╗██████╗ ███████╗"
echo "     ██╔══╝██╔══██╗██║   ██║██╔════╝╚══██╔══╝██║  ██║██║██╔══██╗██╔════╝"
echo "     ██║   ██████╔╝██║   ██║███████╗   ██║   ███████║██║██████╔╝█████╗  "
echo "     ██║   ██╔══██╗██║   ██║╚════██║   ██║   ██╔══██║██║██╔══██╗██╔══╝  "
echo "     ██║   ██║  ██║╚██████╔╝███████║   ██║   ██║  ██║██║██║  ██║███████╗"
echo "     ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚══════╝"
echo ""
echo "  AI-powered Background Verification Platform"
echo ""

# ── Prerequisites ──────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || fail "Docker not found. Install from https://docs.docker.com/get-docker/"
command -v docker compose >/dev/null 2>&1 || fail "Docker Compose v2 not found."
command -v python3 >/dev/null 2>&1 || fail "Python 3 not found."
log "Prerequisites OK"

# ── Environment file ───────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  log "Created .env from .env.example"
else
  warn ".env already exists — skipping"
fi

# Generate NEXTAUTH_SECRET if empty
if grep -q "^NEXTAUTH_SECRET=$" .env 2>/dev/null || grep -q "^NEXTAUTH_SECRET= *$" .env 2>/dev/null; then
  SECRET=$(openssl rand -base64 32 | tr -d '\n')
  # macOS-compatible sed
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|^NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=${SECRET}|" .env
  else
    sed -i "s|^NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=${SECRET}|" .env
  fi
  log "Generated NEXTAUTH_SECRET"
fi

# Generate ENCRYPTION_KEY if empty
if grep -q "^ENCRYPTION_KEY=$" .env 2>/dev/null || grep -q "^ENCRYPTION_KEY= *$" .env 2>/dev/null; then
  ENC_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
  if [ -n "$ENC_KEY" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENC_KEY}|" .env
    else
      sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENC_KEY}|" .env
    fi
    log "Generated ENCRYPTION_KEY"
  else
    warn "Could not generate ENCRYPTION_KEY (cryptography not installed locally). Will be generated in container."
  fi
fi

# ── Start core infrastructure ───────────────────────────────────────────────
echo ""
echo "Starting core services (postgres, redis, minio, qdrant)…"
docker compose up -d postgres redis minio qdrant

echo "Waiting for PostgreSQL to be ready…"
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U trusthire >/dev/null 2>&1; then
    log "PostgreSQL ready"
    break
  fi
  sleep 2
  if [ $i -eq 30 ]; then
    fail "PostgreSQL did not become ready in time"
  fi
done

# ── Database migrations ────────────────────────────────────────────────────
echo "Running database migrations…"
docker compose run --rm api alembic upgrade head 2>/dev/null || \
  docker compose run --rm api python -c "
from database import engine, Base
from models import *
import asyncio
asyncio.run(engine.begin().__aenter__().__await__())
" 2>/dev/null || warn "Migration run skipped — tables will be created on first start"
log "Database ready"

# ── Start Ollama and pull model ────────────────────────────────────────────
echo "Starting Ollama…"
docker compose up -d ollama

echo "Waiting for Ollama to be ready…"
for i in $(seq 1 20); do
  if docker compose exec -T ollama ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

echo "Pulling Llama 3.2 model (this may take 5–10 minutes on first run)…"
docker compose exec -T ollama ollama pull llama3.2:8b || \
  warn "Model pull failed — try: docker compose exec ollama ollama pull llama3.2:8b"
log "LLM model ready"

# ── Start all services ────────────────────────────────────────────────────
echo "Starting all services…"
docker compose up -d
sleep 5

# ── Status ────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  TrustHire AI is running! 🚀"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  🌐  Frontend:    http://localhost:3000"
echo "  📡  API docs:    http://localhost:8000/api/docs"
echo "  🌸  Celery:      http://localhost:5555  (admin / admin)"
echo "  📊  Grafana:     http://localhost:3001  (admin / admin)"
echo "  📦  MinIO:       http://localhost:9001  (minioadmin / minioadmin123)"
echo "  🔵  Qdrant:      http://localhost:6333/dashboard"
echo ""
echo "  ⚠️  REQUIRED BEFORE LOGIN:"
echo "     Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env"
echo "     then run: docker compose restart web"
echo ""
echo "  ⚠️  OPTIONAL (for voice calls):"
echo "     Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER"
echo "     then run: docker compose restart api worker-verification"
echo ""
echo "  Run 'docker compose logs -f' to see all service logs"
echo "  Run 'docker compose down' to stop everything"
echo ""
