#!/usr/bin/env bash
# Render build script for FastAPI
# Set as Build Command in Render dashboard: bash build.sh

set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
alembic upgrade head

echo "Build complete."
