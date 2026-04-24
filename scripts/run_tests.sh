#!/usr/bin/env bash
# VaultLine Server — 통합테스트 실행
# 사용: bash scripts/run_tests.sh [서버_URL]
# 예시: bash scripts/run_tests.sh http://192.168.100.10:8080
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_URL="${1:-http://localhost:8080}"

echo "=== VaultLine 통합테스트 ==="
echo "  대상 서버: $SERVER_URL"
echo ""

# 테스트 의존성 설치
if [ ! -f "$APP_DIR/.venv/bin/pytest" ] && [ ! -f "$APP_DIR/.venv/Scripts/pytest" ]; then
    echo "pytest 설치 중..."
    "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements-test.txt" -q
fi

# 헬스 체크 먼저
echo "서버 연결 확인 중..."
if ! curl -sf "$SERVER_URL/health" > /dev/null; then
    echo "[오류] $SERVER_URL 에 연결할 수 없습니다."
    exit 1
fi
echo "  연결 확인 완료"
echo ""

# 테스트 실행
cd "$APP_DIR"
VAULTLINE_BASE_URL="$SERVER_URL" \
    "$APP_DIR/.venv/bin/pytest" integration/ -v --tb=short "$@" || true

echo ""
echo "=== 테스트 완료 ==="
