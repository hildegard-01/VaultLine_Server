#!/usr/bin/env bash
# VaultLine Server — Ubuntu 22.04/24.04 배포 스크립트
# 사용: sudo bash deploy_ubuntu.sh
set -euo pipefail

APP_DIR="/opt/vaultline"
SERVICE_USER="vaultline"
PYTHON_MIN="3.11"

echo "=== VaultLine Server 배포 시작 ==="

# ─── Python 설치 확인 ───
if ! command -v python3 &>/dev/null; then
    echo "[1/5] Python3 설치 중..."
    apt-get update -qq
    apt-get install -y python3 python3-pip python3-venv
else
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "[1/5] Python $PY_VER 확인 완료"
fi

# Python 3.11+ 권장
apt-get install -y python3.11 python3.11-venv 2>/dev/null || true

# ─── 서비스 사용자 생성 ───
echo "[2/5] 서비스 사용자 확인..."
if ! id -u "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "  서비스 사용자 '$SERVICE_USER' 생성 완료"
fi

# ─── 앱 디렉토리 준비 ───
echo "[3/5] 앱 디렉토리 준비..."
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/data/cache"

# 현재 디렉토리의 프로젝트 파일을 앱 디렉토리로 복사 (이미 앱 디렉토리에서 실행 중이면 스킵)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ "$PROJECT_ROOT" != "$APP_DIR" ]; then
    echo "  $PROJECT_ROOT → $APP_DIR 복사 중..."
    rsync -a --exclude=".git" --exclude="data" --exclude="__pycache__" \
          --exclude="*.pyc" --exclude=".venv" --exclude="venv" \
          "$PROJECT_ROOT/" "$APP_DIR/"
fi

# ─── 가상환경 + 의존성 ───
echo "[4/5] Python 가상환경 설치..."
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --upgrade pip -q
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
echo "  의존성 설치 완료"

# 소유권 설정
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# ─── systemd 서비스 등록 ───
echo "[5/5] systemd 서비스 등록..."
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
systemctl restart vaultline

# 방화벽 허용 (ufw 사용 시)
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 8080/tcp comment "VaultLine Server" 2>/dev/null || true
    echo "  ufw 포트 8080 허용 완료"
fi

sleep 2
if systemctl is-active --quiet vaultline; then
    echo ""
    echo "=== 배포 완료 ==="
    echo "  서버 주소: http://$(hostname -I | awk '{print $1}'):8080"
    echo "  상태 확인: curl http://localhost:8080/health"
    echo "  로그 확인: journalctl -u vaultline -f"
    echo "  초기 관리자: admin / admin1234  ← 즉시 변경 필요"
else
    echo ""
    echo "[오류] 서비스 시작 실패. 로그를 확인하세요:"
    journalctl -u vaultline -n 30 --no-pager
    exit 1
fi
