# Грабли проекта SBP MQ

> **Зачем этот файл:** неочевидные механизмы, которые приводят к багам
> или потере времени. Записываем **в момент**, когда наступили.
>
> **Формат:** симптом → причина → как не наступить → дата.
>
> **Как добавлять:** в конец файла, с датой. Не редактируй старые записи —
> если что-то устарело, добавь новую запись с пометкой «устарело».

---

## `deploy.sh` сам рестартует воркеры (через `run_debug.sh`)

**Симптом:** после `./deploy.sh` воркеры внезапно стартуют заново,
хотя в `deploy.sh` нет `systemctl restart sbp_mq-worker*`.
В `journalctl -u sbp_mq-worker.service` видно `Stopping` → `Stopped` → `Started`.

**Причина:** цепочка вызовов:

    deploy.sh
      → git merge dev → main
      → sudo systemctl restart sbp_mq-debug.service
          → ExecStart = run_debug.sh
              → pkill uvicorn/debugpy
              → systemctl restart sbp_mq-worker*   ← ВОТ ОНО
              → запуск uvicorn

`run_debug.sh` ищет воркеры по паттерну (`sbp_mq-dev-worker*` в DEV,
`sbp_mq-worker*` в PROD) и рестартует **все активные**.

**Как не наступить:**
- **НЕ рестартовать воркеры вручную** после `deploy.sh` — они уже рестартнуты.
- Если кажется, что воркеры не рестартнули — проверить:
  `journalctl -u sbp_mq-worker.service -n 20 --no-pager`
  там будет `Stopping` / `Started` от `run_debug.sh`.

**Дата:** 2026-09-21

---

## Pylance: `Optional[X]` в сигнатурах и narrowing

**Симптом:** Pylance ругается:
`Argument of type "Any | None" cannot be assigned to parameter "bank" of type "str" in function "_handle_abort"`

**Причина:** локальные переменные объявлены как `bank = base = job_id = None`
(тип `Optional[Any]`), а сигнатура `_handle_abort(bank: str, ...)` ожидает `str`.
Pylance видит `None` и ругается.

**Как не наступить:**

1. **Early-return** в `process_message`, если abort пришёл до парсинга:

       except asyncio.CancelledError:
           if bank is None or base is None or job_id is None:
               await message.nack(requeue=False)
               raise
           # после этой проверки Pylance понимает, что bank/base/job_id — не None
           await self._handle_abort(bank=bank, ...)
           raise

2. **`Optional[str]` в сигнатуре**, если поле необязательное:

       async def _handle_abort(
           self,
           task_id: Optional[str],   # может быть None
           job_name: Optional[str],  # может быть None
       ):

3. **`assert x is not None`** после проверки, если Pylance не понимает narrowing:

       if bank is None:
           ...
           raise
       assert bank is not None  # явное сужение для Pylance

**Дата:** 2026-09-21

---

## `time.sleep` в `async def` блокирует event loop

**Симптом:** во время обработки Job `Ctrl+C` не срабатывает. В логе
`⚠️ Получен SIGINT` появляется только **после** завершения `time.sleep`.
Abort не запускается мгновенно.

**Причина:** `time.sleep` — **синхронный**, блокирует весь event loop.
`CancelledError` не доставляется в корутину, пока `time.sleep` не закончится.
Signal handler (`loop.add_signal_handler`) тоже не может выполниться,
пока поток занят.

**Как не наступить:**
- В `async def` использовать `await asyncio.sleep(...)`, а не `time.sleep(...)`.
- Для **блокирующих** вызовов (HTTP через `requests`, файловые операции,
  `zeep`) — `await asyncio.to_thread(blocking_func, ...)`.
- В **моках** для тестов abort'а — всегда `await asyncio.sleep`, иначе
  `Ctrl+C` не сработает.

**Проверка:** `grep -rn "time.sleep" modules/ --include="*.py" | grep "async def" -B5`

**Дата:** 2026-09-21

---

## `soap_notify` 404 на WSDL в DEV — это НЕ баг

**Симптом:** при abort'е (или ошибке Job) `soap_notify` падает:
`HTTPError: 404 Client Error: Not Found for url: http://192.168.10.238/zkh_ursv2/ws/WebLK?wsdl`

**Причина:** в DEV **намеренно** добавлены **несуществующие базы**
(`zkh_ursv2`, `zkh_ursv3` и т.п.) для проверки отображения ошибок
в мониторе. Этих баз нет в реальном 1С → WSDL отдаёт 404.

**Это не баг.** Так и задумано. В PROD используются реальные базы
(`zkh_ursv` и т.п.), и `soap_notify` работает.

**Как не наступить:**
- Если видишь 404 на WSDL в DEV — **проверь, какая база**:
  - `zkh_ursv2`, `zkh_ursv3` — тестовые, 404 **ожидаем**
  - `zkh_ursv` — реальная, 404 **проблема** (передать 1С-отделу)
- В PROD 404 на **реальной** базе — **проблема**, передать 1С-отделу.

**Дата:** 2026-09-21

---

## Вложенные ` ``` ` в markdown ломают копирование через LLM

**Симптом:** при копировании markdown-файла из чата LLM в терминал
сообщение «разваливается» на месте вложенных ` ``` `. Внешний блок
закрывается раньше времени, остальное содержимое «вываливается» как текст.

**Причина:** ` ``` ` (три бэктика) — зарезервированный разделитель
markdown. Внутри ` ```markdown ... ``` ` они не могут быть вложены
без экранирования. При копировании через чат markdown-рендер съедает
границы.

**Как не наступить:**
1. Для вложенных блоков кода — **отступ в 4 пробела** вместо ` ``` `
   (валидный markdown, работает на GitHub и в `/project-docs`).
2. Альтернатива — `~~~` (tilde-fencing), тоже валидный markdown.
3. Для вставки через LLM — **вставлять в редактор** (`nano`, `vim`),
   а не в терминал.
4. При передаче контекста — **не вкладывать** ` ``` ` в ` ``` `.

**Дата:** 2026-09-21

---

## `requestId` должен быть целым числом

**Симптом:** SOAP-ответ от 1С содержит `"requestId "` (без данных),
callback возвращает `status: success`, но 1С НЕ обработала сообщение.
В логах `[SOAP Notify] Ответ 1С: <base> requestId ` (пусто после).

**Причина:** 1С в `ProcessPayload` делает `Число(Стр.requestId)`:

    Попытка
        ЗапросИД = Число(Стр.requestId);
    Исключение
        Ответ = ""+ИмяБазы()+"Недопустимый (должен быть числом) requestId: "+Стр.requestId;
        Возврат "requestId "
    КонецПопытки;

Если `requestId` — не число (например, `"fallback-debug-123"`), 1С
возвращает `"requestId "` (ошибка) и НЕ записывает QR в свой регистр.

**Как не наступить:**
- `requestId` должен быть **целым числом** (например, `12345`, `754316`)
- В тестах — использовать числовые ID (например, `77001001`)
- Реальные `requestId` из 1С — всегда числа
- Не использовать UUID, `date +%s`, префиксы со словами

**Дата:** 2026-09-22

---

## Лок не снимается при abort / ошибке Job

**Симптом:** после abort'а (или обычной ошибки Job) в Redis остаётся ключ
`lock:*` на файл, которого уже нет в `/sbp/jobs/`. Повторная публикация
того же Job → `JOB_ALREADY_PROCESSING`.

**Причина:** лок ставится в `routes/create_payload_mq.py`
(ключ `lock:job:{bank}:{base}:{job_id}`). `job_manager.move_to_error` →
`_move_job_file` исторически делал только `shutil.move(src, dst)` —
**не трогал** `mq_client.locker`. При `_handle_abort` (SIGTERM) лок
вообще не снимался.

**История (2026-09-21):** рассматривали 3 варианта:

- **A)** забить — лок умрёт по TTL (или будет висеть)
- **B)** снимать лок явно в `_handle_abort`
- **C)** добавить снятие внутрь `move_to_error` (архитектурно правильнее)

**Решение (2026-09-22, коммит `896cc29`):** выбран **Вариант C**.
`move_to_error` и `move_to_success` теперь сами снимают лок через
`_unlock_job` (sync-клиент Redis, потому что `move_to_*` — синхронные).

**Как не наступить:**

- `move_to_error` / `move_to_success` **снимают лок** (сделано)
- При отладке — чистить вручную:

    redis-cli -n 1 --scan --pattern "lock:*" | xargs -r redis-cli -n 1 del

- `sh_dev/test_smoke.sh` чистит локи в подготовке
- Проверка после теста:

    redis-cli -n 1 keys "lock:*"
    # ожидаемо: (empty array)

**Проверка:** `redis-cli -n 1 KEYS "lock:*"`

**Дата:** 2026-09-21 / обновлено 2026-09-22

---

## `BASE_DIR = Path(...)` до `from pathlib import Path`

**Симптом:** сервис не поднимается после правки. В `journalctl -u sbp_mq-dev`:

    File "/var/www/html/sbp_mq_dev/sbp.py", line 13, in <module>
        BASE_DIR = Path(__file__).resolve().parent
    NameError: name 'Path' is not defined

**Причина:** при добавлении `BASE_DIR = Path(__file__).resolve().parent` скрипт
вставил его **сразу после** `sys.path.insert(...)`, **до** `from pathlib import Path`.
Python выполняет **сверху вниз** — `Path` ещё не импортирован.

**Как не наступить:**

- **`BASE_DIR`** — **после** всех импортов, **перед** `app = FastAPI(...)`
- Все `from ... import ...` — **в начале файла**, до любого исполняемого кода
- Порядок в `sbp.py`:

      import os
      import sys
      import asyncio
      from contextlib import asynccontextmanager
      from pathlib import Path                    # ← импорт здесь

      # sys.path.insert(...)

      from fastapi import FastAPI
      from fastapi.staticfiles import StaticFiles
      # ... другие импорты

      BASE_DIR = Path(__file__).resolve().parent  # ← после импортов
      app = FastAPI(lifespan=lifespan)

- Если правишь `sbp.py` скриптом — **проверяй `head -25 sbp.py`** после правки

**Дата:** 2026-09-22

---

## Шаблон для новой записи

    ## Краткое название грабли

    **Симптом:** что видно (лог, ошибка, поведение).

    **Причина:** почему так происходит (механизм).

    **Как не наступить:** что делать (команды, паттерны, ссылки).

    **Дата:** YYYY-MM-DD
