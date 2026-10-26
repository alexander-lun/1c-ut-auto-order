#!/usr/bin/env bash
# Загрузка расширения «Автозаказ товаров» (и стенда для тестов) в файловую базу УТ 11 с проверкой модулей.
#   IB_USER="Администратор" [IB_PWD=...] scripts/build.sh <каталог базы УТ> [--no-stand | --stand-only]
set -euo pipefail

IB=$(realpath "${1:?каталог базы}")
cd "$(dirname "$0")/.."
V8=${V8:-$(ls -d /opt/1cv8/x86_64/*/ | sort -V | tail -1)}
DATA=${IBCMD_DATA:-$PWD/build/ibcmd}
AUTH=()
[[ -n ${IB_USER:-} ]] && AUTH=(--user="$IB_USER" --password="${IB_PWD:-}")
mkdir -p "$DATA"

load() {  # load <расширение> <каталог исходников> <безопасный режим yes|no>
  "$V8/ibcmd" infobase config import --data="$DATA" --db-path="$IB" "${AUTH[@]}" --extension="$1" "$2" </dev/null
  "$V8/ibcmd" infobase config extension update --data="$DATA" --db-path="$IB" "${AUTH[@]}" --name="$1" \
    --safe-mode="$3" --unsafe-action-protection="$3" </dev/null
  "$V8/ibcmd" infobase config apply --data="$DATA" --db-path="$IB" "${AUTH[@]}" --extension="$1" --force </dev/null
}

check() {  # проверка модулей конфигуратором: при загрузке из XML модули не компилируются
  local log; log=$(mktemp)
  if ! "$V8/1cv8" DESIGNER /F "$IB" ${IB_USER:+/N "$IB_USER"} ${IB_PWD:+/P "$IB_PWD"} /DisableStartupDialogs \
       /DisableStartupMessages /CheckModules -ThinClient -Server -Extension "$1" /Out "$log"; then
    cat "$log"; rm -f "$log"; exit 1
  fi
  rm -f "$log"
}

if [[ ${2:-} != --stand-only ]]; then
  load АвтозаказТоваров src yes
  check АвтозаказТоваров
  echo "Расширение АвтозаказТоваров загружено в $IB"
fi

if [[ ${2:-} != --no-stand ]]; then
  load СтендАвтозаказа stand yes
  check СтендАвтозаказа
  echo "Стенд СтендАвтозаказа загружен"
fi
