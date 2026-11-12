#!/usr/bin/env bash
# ============================================================
#  Запуск DeepSeek Harness (DSH) web
# ============================================================
#  - Убивает старые процессы DSH
#  - Освобождает порты 3080 / 3081
#  - Запускает DSH через pnpm dlx
#  - Ждёт готовности порта 3080 и LAN-порта 3081
#  - Показывает локальную и LAN-ссылки
#
#  Остановка: Ctrl+C
# ============================================================

set -euo pipefail

# ---------- Параметры ----------
DSH_PORT=3080
DSH_LAN_PORT=3081
LAN_HOST="192.168.10.130"
DSH_LOG="/tmp/dsh-start.log"
WAIT_SECONDS=120

# ---------- Цвета ----------
if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_DIM="\033[2m"
    C_RED="\033[31m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_BLUE="\033[34m"
    C_CYAN="\033[36m"
else
    C_RESET=""; C_BOLD=""; C_DIM=""
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_CYAN=""
fi

info()  { printf "${C_BLUE}==>${C_RESET} %s\n" "$*"; }
ok()    { printf "${C_GREEN} ✓${C_RESET} %s\n" "$*"; }
warn()  { printf "${C_YELLOW} !${C_RESET} %s\n" "$*"; }
err()   { printf "${C_RED} ✗${C_RESET} %s\n" "$*" >&2; }
dim()   { printf "${C_DIM}   %s${C_RESET}\n" "$*"; }

# ---------- nvm + pnpm ----------
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 22 >/dev/null 2>&1 || true

PNPM_BIN="$HOME/.nvm/versions/node/v22.23.3/bin/pnpm"
if [ ! -x "$PNPM_BIN" ]; then
    err "pnpm не найден: $PNPM_BIN"
    exit 1
fi

# ---------- Корпоративный TLS-инспектор (Kaspersky) ----------
export NODE_USE_SYSTEM_CA=1

cd "$HOME"

# ============================================================
#  1. Остановка старых процессов
# ============================================================
info "Останавливаю старые процессы DSH..."

pkill -f "dsh web" 2>/dev/null || true
pkill -f "pnpm dlx @deepseek-ai/dsh" 2>/dev/null || true
sleep 2

# Освобождаем порты
for p in "$DSH_PORT" "$DSH_LAN_PORT"; do
    if command -v fuser >/dev/null 2>&1; then
        sudo fuser -k "${p}/tcp" 2>/dev/null || true
    fi
done
sleep 2

# Добиваем, если что-то осталось
if ss -tln 2>/dev/null | grep -qE ":(${DSH_PORT}|${DSH_LAN_PORT}) "; then
    warn "Порты всё ещё заняты, применяю kill -9"
    for p in "$DSH_PORT" "$DSH_LAN_PORT"; do
        PID=$(sudo ss -tlnp 2>/dev/null | grep ":${p} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
        [ -n "${PID:-}" ] && sudo kill -9 "$PID" 2>/dev/null || true
    done
    sleep 2
fi

if ss -tln 2>/dev/null | grep -qE ":(${DSH_PORT}|${DSH_LAN_PORT}) "; then
    err "Не удалось освободить порты ${DSH_PORT}/${DSH_LAN_PORT}"
    sudo ss -tlnp | grep -E ":(${DSH_PORT}|${DSH_LAN_PORT})" >&2
    exit 1
fi
ok "Порты свободны"

# ============================================================
#  2. Запуск DSH
# ============================================================
: >"$DSH_LOG"
info "Запускаю DSH web"
dim "лог: $DSH_LOG"

"$PNPM_BIN" dlx @deepseek-ai/dsh web >"$DSH_LOG" 2>&1 &
DSH_PID=$!

# ============================================================
#  3. Ждём готовности порта 3080
# ============================================================
printf "${C_BLUE}==>${C_RESET} Ожидание готовности DSH (до ${WAIT_SECONDS}s) "
READY=0
for i in $(seq 1 "$WAIT_SECONDS"); do
    if ss -tln 2>/dev/null | grep -q ":${DSH_PORT} "; then
        printf "${C_GREEN}готов (%ss)${C_RESET}\n" "$i"
        READY=1
        break
    fi
    if ! kill -0 "$DSH_PID" 2>/dev/null; then
        printf "\n"
        err "DSH завершился до открытия порта"
        echo "--- лог ---"
        cat "$DSH_LOG"
        echo "-----------"
        exit 1
    fi
    printf "."
    sleep 1
done

if [ "$READY" -ne 1 ]; then
    printf "\n"
    err "Порт ${DSH_PORT} не открылся за ${WAIT_SECONDS}s"
    echo "--- лог ---"
    cat "$DSH_LOG"
    echo "-----------"
    kill "$DSH_PID" 2>/dev/null || true
    exit 1
fi

# ============================================================
#  4. Извлекаем токен
# ============================================================
TOKEN=""
for i in $(seq 1 30); do
    TOKEN=$(grep -oP 'token=\K[A-Za-z0-9_-]+' "$DSH_LOG" 2>/dev/null | tail -1 || true)
    [ -n "$TOKEN" ] && break
    sleep 0.5
done

# ============================================================
#  5. Ждём LAN-порт 3081
# ============================================================
printf "${C_BLUE}==>${C_RESET} Ожидание LAN-порта ${DSH_LAN_PORT} "
LAN_READY=0
for i in $(seq 1 30); do
    if ss -tln 2>/dev/null | grep -q ":${DSH_LAN_PORT} "; then
        printf "${C_GREEN}готов (%ss)${C_RESET}\n" "$i"
        LAN_READY=1
        break
    fi
    printf "."
    sleep 1
done
[ "$LAN_READY" -eq 0 ] && printf "${C_YELLOW}НЕ поднялся${C_RESET}\n"

# ============================================================
#  6. Итоговый вывод
# ============================================================
echo
printf "${C_BOLD}${C_CYAN}╭──────────────────────────────────────────╮${C_RESET}\n"
printf "${C_BOLD}${C_CYAN}│${C_RESET}  ${C_BOLD}DSH запущен${C_RESET}                              ${C_BOLD}${C_CYAN}│${C_RESET}\n"
printf "${C_BOLD}${C_CYAN}╰──────────────────────────────────────────╯${C_RESET}\n"
echo

# Локальная ссылка
if [ -n "$TOKEN" ]; then
    printf "  ${C_BOLD}Локально:${C_RESET}  ${C_GREEN}http://127.0.0.1:%s/?token=%s${C_RESET}\n" \
        "$DSH_PORT" "$TOKEN"
else
    printf "  ${C_BOLD}Локально:${C_RESET}  ${C_GREEN}http://127.0.0.1:%s/${C_RESET}\n" \
        "$DSH_PORT"
    dim "(токен не найден, см. $DSH_LOG)"
fi

# LAN-ссылка
if [ "$LAN_READY" -eq 1 ]; then
    printf "  ${C_BOLD}LAN:${C_RESET}       ${C_GREEN}https://%s:%s/${C_RESET}\n" \
        "$LAN_HOST" "$DSH_LAN_PORT"
    dim "(если в плагине включён HTTP — http://)"
else
    printf "  ${C_BOLD}LAN:${C_RESET}       ${C_RED}порт %s НЕ слушается${C_RESET}\n" \
        "$DSH_LAN_PORT"
    dim "проверь dsh-lan-guard"
fi

echo
printf "  ${C_DIM}Остановка: Ctrl+C${C_RESET}\n"
echo

# ============================================================
#  7. Ожидание и очистка
# ============================================================
cleanup() {
    echo
    info "Остановка DSH..."
    kill "$DSH_PID" 2>/dev/null || true
    ok "Готово"
}
trap cleanup INT TERM

wait "$DSH_PID"
cleanup