#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1; then echo "Docker is required." >&2; exit 1; fi
if [ ! -f .env ]; then
  API_KEY="$(openssl rand -hex 32)"
  DB_PASSWORD="$(openssl rand -hex 24)"
  SECRET_KEY="$(openssl rand -hex 48)"
  cat > .env <<ENV
SHLINK_DOMAIN=s.sagarkerhalkar.com
SHLINK_API_KEY=$API_KEY
POSTGRES_PASSWORD=$DB_PASSWORD
SECRET_KEY=$SECRET_KEY
GEOLITE_LICENSE_KEY=
SESSION_COOKIE_SECURE=0
ENV
fi
docker compose up -d --build shlink-db shlink
docker compose run --rm dashboard flask --app run.py init-db
if ! docker compose run --rm dashboard flask --app run.py has-admin >/dev/null 2>&1; then
  docker compose run --rm dashboard flask --app run.py create-admin
fi
docker compose up -d dashboard
echo "Link Analytics: http://localhost:2331"
