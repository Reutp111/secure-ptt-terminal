#!/bin/bash

set -e

echo "======================================"
echo " Secure PTT Terminal - Linux Installer"
echo "======================================"
echo

echo "[+] Installing system dependencies..."
sudo apt update
sudo apt install -y curl python3 python3-venv python3-pip espeak ffmpeg libespeak1

echo
read -p "Install/enable Tailscale? (y/n): " USE_TAILSCALE

if [ "$USE_TAILSCALE" = "y" ] || [ "$USE_TAILSCALE" = "Y" ]; then
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "[+] Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
  else
    echo "[+] Tailscale already installed."
  fi

  if [ -n "$TAILSCALE_AUTHKEY" ]; then
    echo "[+] Connecting to Tailscale using auth key..."
    sudo tailscale up --auth-key="$TAILSCALE_AUTHKEY"
  else
    echo
    echo "[!] No TAILSCALE_AUTHKEY provided."
    echo "[!] Running interactive Tailscale login."
    echo "[!] A login URL may appear. Open it and approve this machine."
    echo
    sudo tailscale up
  fi

  echo
  echo "[+] Tailscale status:"
  tailscale status || true

  echo
  echo "[+] This machine Tailscale IP:"
  tailscale ip -4 || true
fi

echo
read -p "Enter relay server URL, for example ws://100.x.x.x:3000 or ws://192.168.56.1:3000: " SERVER_URL

if [ -z "$SERVER_URL" ]; then
  SERVER_URL="ws://localhost:3000"
fi

export SERVER_URL

echo "[+] Updating SERVER_URL inside client.py..."
python3 - << 'PY'
import os
from pathlib import Path

server_url = os.environ["SERVER_URL"]

path = Path("client.py")
text = path.read_text(encoding="utf-8")

new_lines = []

for line in text.splitlines():
    if line.strip().startswith("SERVER_URL ="):
        new_lines.append(f'SERVER_URL = "{server_url}"')
    else:
        new_lines.append(line)

path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
PY

echo "[+] Removing old virtual environment and build files..."
rm -rf venv build dist client.spec

echo "[+] Creating Python virtual environment..."
python3 -m venv venv

echo "[+] Installing Python dependencies..."
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[+] Creating run.sh..."
cat > run.sh << 'RUNEOF'
#!/bin/bash
cd "$(dirname "$0")"

if [ -f "./dist/client" ]; then
  ./dist/client
else
  source venv/bin/activate
  python client.py
fi
RUNEOF

chmod +x run.sh

echo
echo "[+] Installation completed."
echo "[+] Start the client with:"
echo "./run.sh"