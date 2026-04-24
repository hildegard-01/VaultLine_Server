#!/usr/bin/env bash
# VaultLine Server — 소스 업데이트 (git pull)
# Ubuntu 서버 전용: /VaultLine/VaultLine_Server
set -euo pipefail

APP_DIR="/VaultLine/VaultLine_Server"

cd "$APP_DIR"

echo "=== VaultLine 소스 업데이트 ==="

# ─── config.yaml 로컬 변경 보존 ───
if git diff --quiet -- config.yaml 2>/dev/null; then
    CONFIG_MODIFIED=false
else
    echo "config.yaml 로컬 변경 감지 → 백업..."
    cp config.yaml config.yaml.local
    CONFIG_MODIFIED=true
fi

# ─── git pull ───
BEFORE=$(git rev-parse --short HEAD)
git pull --ff-only
AFTER=$(git rev-parse --short HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
    echo "이미 최신 ($BEFORE)"
else
    echo "$BEFORE → $AFTER"
    git log --oneline "$BEFORE..$AFTER"
fi

# ─── config.yaml 복원 ───
if [ "$CONFIG_MODIFIED" = true ]; then
    cp config.yaml.local config.yaml
    echo "config.yaml 복원 완료"
fi

# ─── 의존성 변경 시 pip 업데이트 ───
if [ "$BEFORE" != "$AFTER" ] && git diff "$BEFORE" "$AFTER" --name-only | grep -q "requirements.txt"; then
    echo "requirements.txt 변경 감지 → pip 업데이트..."
    .venv/bin/pip install -r requirements.txt -q
fi

# ─── 서버 재시작 ───
if systemctl is-active --quiet vaultline 2>/dev/null; then
    systemctl restart vaultline
    echo "서비스 재시작 완료"
else
    pkill -f "uvicorn main:app" 2>/dev/null || true
    sleep 1
    nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --reload \
        >> vaultline.log 2>&1 &
    echo "프로세스 재시작 완료"
fi

echo "=== 완료 ==="
