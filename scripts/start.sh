#!/usr/bin/env bash
# VaultLine Server — 개발 서버 실행
# 사용: bash scripts/start.sh
set -euo pipefail

# scripts/ 안에서 실행하든 프로젝트 루트에서 실행하든 main.py 위치로 탐지
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$_SELF_DIR/main.py" ]; then
    APP_DIR="$_SELF_DIR"
else
    APP_DIR="$(cd "$_SELF_DIR/.." && pwd)"
fi
VENV="$APP_DIR/.venv"

cd "$APP_DIR"

# python3-venv 없으면 자동 설치
if ! python3 -m venv --help &>/dev/null 2>&1; then
    echo "python3-venv 설치 중... (sudo 필요)"
    sudo apt-get install -y python3-venv
fi

# venv 없으면 생성
if [ ! -d "$VENV" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip -q
    "$VENV/bin/pip" install -r requirements.txt -q
    echo "패키지 설치 완료"
fi

# data 디렉토리
mkdir -p data/cache

echo "=== VaultLine Server 시작 ==="
echo "  주소: http://0.0.0.0:8080"
echo "  문서: http://$(hostname -I | awk '{print $1}'):8080/docs"
echo "  종료: Ctrl+C"
echo ""

"$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8080 --reload
