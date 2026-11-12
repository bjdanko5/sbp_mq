#!/usr/bin/env bash
# ============================================================
# Диагностика старта DSH через strace
# - Корректно убивает старые процессы
# - Запускает DSH в фоне
# - Ждёт готовности порта 3080
# - Находит правильный node-PID
# - Запускает strace с записью в $HOME/dsh-strace.log
# - По Ctrl+C корректно всё останавливает
# ============================================================

set -euo pipefail

# --- Параметры ---
DSH_PORT=3080
DSH_LAN_PORT=3081
DSH_LOG="$HOME/dsh-start.log"
TRACE_LOG="$HOME/dsh-strace.log"
WAIT_SECONDS=120

# --- nvm ---
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 22 >/dev/null 2>&1 || true

PNPM_BIN="$HOME/.nvm/versions/node/v22.23.3/bin/pnpm"
if [ ! -x "$PNPM_BIN" ]; then
    echo "Ошибка: pnpm не найден: $PNPM_BIN" >&2
    exit 1
fi

export NODE_USE_SYSTEM_CA=1
cd "$HOME"

DSH_PID=""
NODE_PID=""
STRACE_PID=""

# ============================================================
# cleanup — вызывается всегда при выходе
# ============================================================
cleanup() {
    echo
    echo "==> Останавливаю диагностику..."

    # Убить tail (если висит)
    if [ -n "${TAIL_PID:-}" ] && kill -0 "$TAIL_PID" 2>/dev/null; then
        kill "$TAIL_PID" 2>/dev/null || true
    fi

    # Убить strace
    if [ -n "${STRACE_PID:-}" ] && kill -0 "$STRACE_PID" 2>/dev/null; then
        kill "$STRACE_PID" 2>/dev/null || true
        sleep 1
        kill -9 "$STRACE_PID" 2>/dev/null || true
    fi

    # Убить node (реальный процесс DSH)
    if [ -n "${NODE_PID:-}" ] && kill -0 "$NODE_PID" 2>/dev/null; then
        kill "$NODE_PID" 2>/dev/null || true
        sleep 1
        kill -9 "$NODE_PID" 2>/dev/null || true
    fi

    # Убить launcher (pnpm)
    if [ -n "${DSH_PID:-}" ] && kill -0 "$DSH_PID" 2>/dev/null; then
        kill "$DSH_PID" 2>/dev/null || true
        sleep 1
        kill -9 "$DSH_PID" 2>/dev/null || true
    fi

    # Добить всё, что связано с dsh
    pkill -9 -f "dsh web" 2>/dev/null || true

    # Освободить порты
    if command -v fuser >/dev/null 2>&1; then
        sudo fuser -k "${DSH_PORT}/tcp" 2>/dev/null || true
        sudo fuser -k "${DSH_LAN_PORT}/tcp" 2>/dev/null || true
    fi

    echo "==> Готово. Логи:"
    echo "    DSH:    $DSH_LOG"
    echo "    strace: $TRACE_LOG"
}
trap cleanup EXIT INT TERM

# ============================================================
# 1. Убиваем старые процессы
# ============================================================
echo "==> Останавливаю старые процессы DSH..."
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

# Проверка
if ss -tln 2>/dev/null | grep -qE ":(${DSH_PORT}|${DSH_LAN_PORT}) "; then
    echo "    ВНИМАНИЕ: порты всё ещё заняты. Добиваю..."
    for p in "$DSH_PORT" "$DSH_LAN_PORT"; do
        PID=$(sudo ss -tlnp 2>/dev/null | grep ":${p} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
        [ -n "${PID:-}" ] && sudo kill -9 "$PID" 2>/dev/null || true
    done
    sleep 2
fi

if ss -tln 2>/dev/null | grep -qE ":(${DSH_PORT}|${DSH_LAN_PORT}) "; then
    echo "Ошибка: не удалось освободить порты." >&2
    sudo ss -tlnp | grep -E ":(${DSH_PORT}|${DSH_LAN_PORT})" >&2
    exit 1
fi
echo "    Порты свободны."

# ============================================================
# 2. Запуск DSH
# ============================================================
rm -f "$DSH_LOG" "$TRACE_LOG"

echo "==> Запускаю DSH (лог: $DSH_LOG)"
"$PNPM_BIN" dlx @deepseek-ai/dsh web >"$DSH_LOG" 2>&1 &
DSH_PID=$!
echo "    Launcher PID: $DSH_PID"

# ============================================================
# 3. Ожидание готовности порта 3080
# ============================================================
echo -n "==> Ожидание готовности DSH (до ${WAIT_SECONDS}s)"
READY=0
for i in $(seq 1 "$WAIT_SECONDS"); do
    if ss -tln 2>/dev/null | grep -q ":${DSH_PORT} "; then
        echo " — готов (${i}s)"
        READY=1
        break
    fi
    if ! kill -0 "$DSH_PID" 2>/dev/null; then
        echo
        echo "Ошибка: DSH завершился до открытия порта. Лог:" >&2
        cat "$DSH_LOG" >&2
        exit 1
    fi
    echo -n "."
    sleep 1
done

if [ "$READY" -ne 1 ]; then
    echo
    echo "Ошибка: порт ${DSH_PORT} не открылся за ${WAIT_SECONDS}s. Лог:" >&2
    cat "$DSH_LOG" >&2
    exit 1
fi

# ============================================================
# 4. Находим правильный node-PID
# ============================================================
echo -n "==> Ищу node-PID DSH"
for i in $(seq 1 20); do
    CANDIDATES=$(ps -eo pid,ppid,cmd --no-headers | grep -E "node.*dsh|dsh.*web" | grep -v grep | awk '{print $1}')
    for pid in $CANDIDATES; do
        CMD=$(ps -o cmd= -p "$pid" 2>/dev/null || true)
        if echo "$CMD" | grep -qE "^node |/node "; then
            PPID_CMD=$(ps -o cmd= -p "$(ps -o ppid= -p "$pid" | tr -d ' ')" 2>/dev/null || true)
            if echo "$PPID_CMD" | grep -qE "pnpm"; then
                NODE_PID="$pid"
                echo " — найден PID: $NODE_PID"
                break 2
            fi
        fi
    done
    echo -n "."
    sleep 1
done

if [ -z "${NODE_PID:-}" ]; then
    echo
    echo "Ошибка: не удалось найти node-PID." >&2
    ps -eo pid,ppid,cmd | grep -E "dsh|pnpm" | grep -v grep >&2
    exit 1
fi

# --- Состояние процесса ---
echo
echo "==> Состояние процесса $NODE_PID:"
ps -o pid,ppid,stat,%cpu,%mem,etime,wchan -p "$NODE_PID" 2>/dev/null || true

# ============================================================
# 5. strace — пишем через sudo tee в файл (без Permission denied)
# ============================================================
echo
echo "==> strace пишет в $TRACE_LOG"
echo "    Смотри вывод: tail -f $TRACE_LOG"
echo "    Ctrl+C для остановки диагностики."
echo

# Убираем старый файл и создаём пустой (чтобы tee имел куда писать)
rm -f "$TRACE_LOG"
touch "$TRACE_LOG"
chmod 666 "$TRACE_LOG"

sudo strace -f -p "$NODE_PID" \
    -e trace=openat,read,stat,connect \
    -T -tt 2>&1 | tee -a "$TRACE_LOG" >/dev/null &
STRACE_PID=$!

# --- Ждём, пока strace реально начнёт писать ---
sleep 2

if ! kill -0 "$STRACE_PID" 2>/dev/null; then
    echo "Ошибка: strace не запустился. Возможно, нет прав sudo." >&2
    exit 1
fi

# ============================================================
# 6. Показываем лог в реальном времени
# ============================================================
tail -f "$TRACE_LOG" &
TAIL_PID=$!

# ============================================================
# 7. Ждём strace (пока не упадёт DSH или не нажмёшь Ctrl+C)
# ============================================================
wait "$STRACE_PID" 2>/dev/null || true