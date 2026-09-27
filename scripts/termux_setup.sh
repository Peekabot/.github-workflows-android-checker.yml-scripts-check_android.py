#!/data/data/com.termux/files/usr/bin/bash
# Run this once on a fresh Termux install to set up the X Chat Android checker.
# Usage: bash scripts/termux_setup.sh

set -e

echo "=== Termux setup for X Chat Android Checker ==="

# --- Core packages ---
pkg update -y
pkg install -y python git cronie

# --- Python dependencies ---
pip install --upgrade pip
pip install requests beautifulsoup4 anthropic

# --- Environment file ---
ENV_FILE="$HOME/.xchat_checker_env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" <<'EOF'
# Fill in the values below, then source before running:
#   source ~/.xchat_checker_env && python scripts/check_android.py

# --- Local Devstral via Ollama (preferred, free, offline) ---
export OLLAMA_HOST="http://localhost:11434"   # default Ollama address
export OLLAMA_MODEL="devstral"               # model name as pulled in Ollama

# --- Claude API fallback (optional, used only if Ollama is unreachable) ---
export ANTHROPIC_API_KEY=""                  # https://console.anthropic.com

# --- Notification channels (at least one recommended) ---
export TELEGRAM_BOT_TOKEN=""
export TELEGRAM_CHAT_ID=""
export SLACK_WEBHOOK_URL=""
export DISCORD_WEBHOOK=""
EOF
    echo "Created $ENV_FILE — edit it and add your keys."
else
    echo "$ENV_FILE already exists, skipping."
fi

# --- Verify Ollama + Devstral are reachable ---
OLLAMA_OK=false
if curl -sf http://localhost:11434/api/tags | grep -q "devstral"; then
    echo "Ollama + devstral detected."
    OLLAMA_OK=true
else
    echo "WARNING: Ollama not running or devstral not pulled."
    echo "  Start Ollama: ollama serve"
    echo "  Pull model:   ollama pull devstral"
fi

# --- Cron job: run every 2 hours ---
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRON_CMD="0 */2 * * * source $ENV_FILE && cd $REPO_DIR && python scripts/check_android.py >> $REPO_DIR/checker.log 2>&1"

# Append only if not already present
(crontab -l 2>/dev/null | grep -qF "check_android.py") || \
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

# Start cron daemon (Termux needs this manually)
crond 2>/dev/null && echo "crond started." || echo "crond already running or unavailable."

echo ""
echo "=== Done ==="
echo "Next steps:"
echo "  1. Edit $ENV_FILE and add your API keys"
echo "  2. Test manually:  source $ENV_FILE && python $REPO_DIR/scripts/check_android.py"
echo "  3. Cron will run automatically every 2 hours once crond is active"
echo ""
echo "To keep crond alive after Termux restarts, add to ~/.bashrc:"
echo "  crond 2>/dev/null || true"
