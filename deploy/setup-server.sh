#!/bin/bash
# grainbidcalc server setup — run once on the DigitalOcean droplet
# Usage: bash setup-server.sh

set -e

echo "=== Installing system packages ==="
apt-get update
apt-get install -y python3 python3-pip python3-venv redis-server tesseract-ocr poppler-utils

echo "=== Creating /opt/grainbidcalc ==="
mkdir -p /opt/grainbidcalc/credentials /opt/grainbidcalc/data /opt/grainbidcalc/tests/sample_data

echo "=== Setting up Python virtual environment ==="
python3 -m venv /opt/grainbidcalc/venv

echo "=== Installing Python dependencies ==="
/opt/grainbidcalc/venv/bin/pip install --upgrade pip
/opt/grainbidcalc/venv/bin/pip install -r /opt/grainbidcalc/requirements.txt

echo "=== Installing systemd services ==="
cp /opt/grainbidcalc/deploy/grainbidcalc.service /etc/systemd/system/
cp /opt/grainbidcalc/deploy/grainbidcalc-worker.service /etc/systemd/system/
cp /opt/grainbidcalc/deploy/grainbidcalc-beat.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable grainbidcalc grainbidcalc-worker grainbidcalc-beat
systemctl enable redis-server

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Copy .env to /opt/grainbidcalc/.env"
echo "  2. Copy credentials/ if needed"
echo "  3. Run database migrations via Supabase SQL editor"
echo "  4. Seed data: venv/bin/python scripts/seed_commodities.py && venv/bin/python scripts/seed_buyers.py"
echo "  5. Start services: systemctl start grainbidcalc grainbidcalc-worker grainbidcalc-beat"
echo "  6. Check status: systemctl status grainbidcalc"
