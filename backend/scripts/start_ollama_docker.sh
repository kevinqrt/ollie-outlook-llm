#!/usr/bin/env bash

set -euo pipefail

CONTAINER_NAME="${OLLAMA_CONTAINER_NAME:-ollama}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
OLLAMA_VOLUME="${OLLAMA_VOLUME:-ollama}"
OLLAMA_START_TIMEOUT="${OLLAMA_START_TIMEOUT:-30}"

if docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  echo "Ollama container '$CONTAINER_NAME' laeuft bereits."
elif docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  echo "Starte vorhandenen Ollama container '$CONTAINER_NAME' ..."
  docker start "$CONTAINER_NAME" >/dev/null
else
  echo "Erstelle und starte Ollama container '$CONTAINER_NAME' ..."
  docker run -d \
    -v "${OLLAMA_VOLUME}:/root/.ollama" \
    -p "${OLLAMA_PORT}:11434" \
    --name "$CONTAINER_NAME" \
    ollama/ollama >/dev/null
fi

echo "Warte auf Ollama server im Container ..."
for ((i = 1; i <= OLLAMA_START_TIMEOUT; i++)); do
  if docker exec "$CONTAINER_NAME" ollama list >/dev/null 2>&1; then
    break
  fi

  if [[ "$i" -eq "$OLLAMA_START_TIMEOUT" ]]; then
    echo "Ollama wurde im Container nicht rechtzeitig bereit."
    echo "Container-Logs:"
    docker logs "$CONTAINER_NAME" || true
    exit 1
  fi

  sleep 1
done

echo "Ziehe Modell '$OLLAMA_MODEL' ..."
docker exec "$CONTAINER_NAME" ollama pull "$OLLAMA_MODEL"

echo "Ollama ist bereit unter http://127.0.0.1:${OLLAMA_PORT}"
