#!/usr/bin/env bash
# VaultLine Server — 업데이트 스크립트
# git pull 하면서 로컬 config.yaml 을 보존하고 서버를 재시작
# 사용: bash scripts/update.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$APP_DIR/config.yaml"
CONFIG_BACKUP="$APP_DIR/config.yaml.local"

cd "$APP_DIR"

echo "=== VaultLine Server 업데이트 ==="

# ─── 현재 커밋 기록 ───
BEFORE=$(git rev-parse --short HEAD)

# ─── config.yaml 보존 ───
CONFIG_MODIFIED=false
if git diff --quiet -- config.yaml 2>/dev/null; then
    echo "[1/4] config.yaml 변경 없음 — 그대로 유지"
else
    echo "[1/4] config.yaml 로컬 변경 감지 → 백업 중..."
    cp "$CONFIG_FILE" "$CONFIG_BACKUP"
    CONFIG_MODIFIED=true
    echo "  백업 위치: $CONFIG_BACKUP"
fi

# ─── git pull ───
echo "[2/4] 소스 업데이트 (git pull)..."
git pull --ff-only

AFTER=$(git rev-parse --short HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
    echo "  이미 최신 상태 ($BEFORE)"
else
    echo "  $BEFORE → $AFTER"
    git log --oneline "$BEFORE..$AFTER"
fi

# ─── config.yaml 복원 ───
if [ "$CONFIG_MODIFIED" = true ]; then
    echo "[3/4] config.yaml 복원 중..."

    # git이 config.yaml을 변경했는지 확인
    if ! diff -q "$CONFIG_BACKUP" "$CONFIG_FILE" &>/dev/null; then
        # 원격 변경이 있으면 두 파일을 나란히 보여줌
        echo ""
        echo "  *** 주의: 원격 저장소의 config.yaml이 변경되었습니다 ***"
        echo "  로컬 설정(config.yaml.local)을 우선 적용합니다."
        echo "  원격 변경 사항을 직접 확인하세요:"
        echo "    diff $CONFIG_BACKUP $CONFIG_FILE"
        echo ""
    fi

    cp "$CONFIG_BACKUP" "$CONFIG_FILE"
    echo "  config.yaml 복원 완료"
else
    echo "[3/4] config.yaml 복원 불필요 — 스킵"
fi

# ─── 의존성 변경 시 재설치 ───
echo "[4/4] 의존성 확인..."
if [ "$BEFORE" != "$AFTER" ] && git diff "$BEFORE" "$AFTER" --name-only | grep -q "requirements.txt"; then
    echo "  requirements.txt 변경 감지 → pip 업데이트 중..."
    "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
    echo "  패키지 업데이트 완료"
else
    echo "  requirements.txt 변경 없음 — 스킵"
fi

# ─── 서버 재시작 ───
echo ""
echo "=== 서버 재시작 ==="
if systemctl is-active --quiet vaultline 2>/dev/null; then
    systemctl restart vaultline
    sleep 2
    if systemctl is-active --quiet vaultline; then
        echo "  서비스 재시작 완료"
    else
        echo "  [오류] 재시작 실패. 로그:"
        journalctl -u vaultline -n 20 --no-pager
        exit 1
    fi
elif [ -f "$APP_DIR/.venv/bin/uvicorn" ]; then
    # systemd 없이 직접 실행 중인 경우
    pkill -f "uvicorn main:app" 2>/dev/null || true
    sleep 1
    nohup "$APP_DIR/.venv/bin/uvicorn" main:app \
        --host 0.0.0.0 --port 8080 --workers 1 \
        >> "$APP_DIR/vaultline.log" 2>&1 &
    sleep 2
    echo "  프로세스 재시작 완료 (PID: $!)"
    echo "  로그: tail -f $APP_DIR/vaultline.log"
else
    echo "  [경고] 실행 중인 서버를 찾을 수 없습니다. 수동으로 재시작하세요."
fi

echo ""
HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null || echo "연결 실패")
echo "  헬스 체크: $HEALTH"
echo ""
echo "=== 업데이트 완료: $BEFORE → $AFTER ==="
