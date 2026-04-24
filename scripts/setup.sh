#!/usr/bin/env bash
# VaultLine Server — 최초 설치 스크립트
# git clone 직후 한 번만 실행
# 사용: bash scripts/setup.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SUDO_USER:-$(whoami)}"

echo "=== VaultLine Server 초기 설치 ==="
echo "  앱 경로: $APP_DIR"
echo "  실행 사용자: $SERVICE_USER"
echo ""

# ─── Python venv ───
echo "[1/4] Python 가상환경 생성..."
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
    echo "  .venv 생성 완료"
else
    echo "  .venv 이미 존재 — 스킵"
fi

"$APP_DIR/.venv/bin/pip" install --upgrade pip -q
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
echo "  패키지 설치 완료"

# ─── 데이터 디렉토리 ───
echo "[2/4] 데이터 디렉토리 준비..."
mkdir -p "$APP_DIR/data/cache"
echo "  data/ 디렉토리 준비 완료"

# ─── config.yaml 확인 ───
echo "[3/4] 설정 파일 확인..."
if [ ! -f "$APP_DIR/config.yaml" ]; then
    echo "  [경고] config.yaml 없음 — 기본값으로 실행됩니다"
else
    echo "  config.yaml 존재 확인"
    echo ""
    echo "  *** 운영 환경이라면 아래 항목을 반드시 수정하세요 ***"
    echo "  - auth.jwt_secret: 랜덤 문자열로 변경"
    echo "  - server.debug: false"
    echo "  - 파일: $APP_DIR/config.yaml"
fi

# ─── systemd 서비스 등록 (root 실행 시만) ───
echo ""
echo "[4/4] systemd 서비스 등록..."
if [ "$EUID" -ne 0 ]; then
    echo "  root가 아닌 경우 systemd 등록을 건너뜁니다."
    echo "  수동 실행: $APP_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080"
    echo ""
    echo "=== 설치 완료 (수동 실행 모드) ==="
    exit 0
fi

cat > /etc/systemd/system/vaultline.service <<EOF
[Unit]
Description=VaultLine Server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vaultline

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vaultline
systemctl start vaultline

sleep 2
if systemctl is-active --quiet vaultline; then
    echo ""
    echo "=== 설치 완료 ==="
    echo "  서버 주소: http://$(hostname -I | awk '{print $1}'):8080"
    echo "  상태 확인: curl http://localhost:8080/health"
    echo "  로그 확인: journalctl -u vaultline -f"
    echo "  초기 관리자: admin / admin1234  ← 즉시 변경 필요"
else
    echo "[오류] 서비스 시작 실패. 로그:"
    journalctl -u vaultline -n 20 --no-pager
    exit 1
fi
