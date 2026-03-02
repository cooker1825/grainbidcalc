#!/bin/bash
# Deploy grainbidcalc to the DigitalOcean droplet
# Usage: bash deploy/deploy.sh <droplet-ip>
# Run from the project root

set -e

if [ -z "$1" ]; then
    echo "Usage: bash deploy/deploy.sh <droplet-ip>"
    exit 1
fi

IP="$1"
REMOTE="/opt/grainbidcalc"

echo "=== Deploying grainbidcalc to $IP ==="

# Copy all Python source files and project files
scp -r config db ingestion parsing calculation distribution api workers scripts tests \
    requirements.txt CLAUDE.md \
    root@${IP}:${REMOTE}/

# Copy deploy scripts
scp -r deploy root@${IP}:${REMOTE}/

# Copy .env if present (careful — contains secrets)
if [ -f .env ]; then
    scp .env root@${IP}:${REMOTE}/.env
    echo "Copied .env"
fi

# Reinstall dependencies and restart service
ssh root@${IP} "cd ${REMOTE} && venv/bin/pip install -r requirements.txt && systemctl restart grainbidcalc && systemctl restart grainbidcalc-worker && systemctl restart grainbidcalc-beat"

echo "=== Deploy complete ==="
echo "Check status: ssh root@${IP} 'systemctl status grainbidcalc'"
