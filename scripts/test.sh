#!/usr/bin/env bash
# Тесты через стенд: база УТ со стендом опубликована (HTTP-сервисы расширений включены).
#   STAND_URL=http://127.0.0.1:8081/<публикация>/hs/auto-order-stand scripts/test.sh [аргументы pytest]
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}
"$PYTHON" -m pytest tests "$@"
