#!/usr/bin/env bash
# Install or update the FPL Bot collector on a fresh Ubuntu 22.04/24.04 server.
#
# Run as root. It is safe to run again: a second run updates the code and restarts the service.
#   curl -fsSL https://raw.githubusercontent.com/dgarcialuna/fpl_bot/main/deploy/install.sh | sudo bash
#
# What it does: creates an unprivileged `fplbot` user, installs the code into /opt/fpl-bot,
# starts a systemd service that samples the FPL API every 30 minutes, schedules a daily
# database backup, and turns on automatic security updates and a basic firewall.
set -euo pipefail

REPO_URL="${FPL_BOT_REPO:-https://github.com/dgarcialuna/fpl_bot.git}"
BRANCH="${FPL_BOT_BRANCH:-main}"
APP_DIR=/opt/fpl-bot
DATA_DIR=/var/lib/fpl-bot

if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must run as root (use sudo)." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip sqlite3 ufw unattended-upgrades >/dev/null

echo "==> Checking Python version"
python3 - <<'PY'
import sys

if sys.version_info < (3, 11):
    sys.exit(f"Python 3.11+ is required, found {sys.version.split()[0]}. Use Ubuntu 24.04.")
PY

echo "==> Creating service user and directories"
id -u fplbot >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin fplbot
install -d -o fplbot -g fplbot -m 750 "$DATA_DIR"
install -d -m 755 "$APP_DIR"

echo "==> Fetching the code"
if [[ -d "$APP_DIR/src/.git" ]]; then
    git -C "$APP_DIR/src" fetch --quiet origin "$BRANCH"
    git -C "$APP_DIR/src" reset --quiet --hard "origin/$BRANCH"
else
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR/src"
fi

echo "==> Installing the package"
[[ -d "$APP_DIR/venv" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet --upgrade "$APP_DIR/src"

echo "==> Installing systemd units"
install -m 755 "$APP_DIR/src/deploy/backup.sh" "$APP_DIR/backup.sh"
install -m 644 "$APP_DIR/src/deploy/fpl-bot-snapshot.service" /etc/systemd/system/
install -m 644 "$APP_DIR/src/deploy/fpl-bot-backup.service" /etc/systemd/system/
install -m 644 "$APP_DIR/src/deploy/fpl-bot-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now fpl-bot-snapshot.service fpl-bot-backup.timer
systemctl restart fpl-bot-snapshot.service

echo "==> Basic hardening (firewall allows only SSH; automatic security updates)"
ufw allow OpenSSH >/dev/null
ufw --force enable >/dev/null
echo 'APT::Periodic::Update-Package-Lists "1";' >/etc/apt/apt.conf.d/20auto-upgrades
echo 'APT::Periodic::Unattended-Upgrade "1";' >>/etc/apt/apt.conf.d/20auto-upgrades

echo
echo "Done. The collector is running. Useful commands:"
echo "  systemctl status fpl-bot-snapshot      # is it running?"
echo "  journalctl -u fpl-bot-snapshot -f      # live log (Ctrl+C to leave)"
echo "  sqlite3 $DATA_DIR/fpl_bot.db 'select count(*) from snapshots;'"
