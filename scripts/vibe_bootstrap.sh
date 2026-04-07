#!/usr/bin/env bash
# Bootstrap script for the devstral-vibe container.
# Writes a Vibe config pointing at the shared Ollama backend if one doesn't
# already exist, then executes the passed command (default: tail -f /dev/null).

set -euo pipefail

CONFIG_DIR="${HOME}/.config/vibe"
CONFIG_FILE="${CONFIG_DIR}/config.json"

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
VIBE_MODEL="${VIBE_MODEL:-devstral:24b-small-2505}"

if [ ! -f "${CONFIG_FILE}" ]; then
    echo "[vibe-bootstrap] Writing initial Vibe config to ${CONFIG_FILE}"
    mkdir -p "${CONFIG_DIR}"
    cat > "${CONFIG_FILE}" <<EOF
{
  "provider": "ollama",
  "model": "${VIBE_MODEL}",
  "ollama": {
    "base_url": "${OLLAMA_BASE_URL}"
  }
}
EOF
    echo "[vibe-bootstrap] Config written."
else
    echo "[vibe-bootstrap] Existing config found at ${CONFIG_FILE}, skipping write."
fi

exec "$@"
