#!/bin/bash
# Nightly GitHub backup for grainbidcalc
# Commits and pushes code changes. Secrets and data are excluded via .gitignore.
#
# Cron setup (run as root on the droplet):
#   crontab -e
#   0 2 * * * /bin/bash /opt/grainbidcalc/deploy/github-backup.sh >> /opt/grainbidcalc/data/backup.log 2>&1

set -e

REPO="/opt/grainbidcalc"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

cd "$REPO"

if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "[$TIMESTAMP] No changes to commit."
    exit 0
fi

git add -A
git commit -m "Auto-backup: $TIMESTAMP"
git push origin master

echo "[$TIMESTAMP] Backup pushed successfully."
