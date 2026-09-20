# Git workflow SBP MQ

## 🎯 Модель веток

| Ветка | Назначение | Worktree |
|-------|-----------|----------|
| `dev` | Разработка, эксперименты, новые фичи | `/var/www/html/sbp_mq_dev` |
| `main` | Прод, стабильное состояние | `/var/www/html/sbp_mq` |

**Правило:** код едет **только через `dev`**. Прямые коммиты в `main` — нет.

```
dev ──commit──▶ dev ──push──▶ origin/dev
                              │
                              │ deploy.sh
                              ▼
              main ◀──merge── dev
                │
                └──push──▶ origin/main
```

---

## 🌳 Worktree

Проект использует **`git worktree`** — один `.git`, две рабочие директории.

### Схема

```
/var/www/html/sbp_mq_dev/        /var/www/html/sbp_mq/
├── .git  ───┐                   ├── .git  ───┐
├── sbp.py   │                   ├── sbp.py   │
├── routes/  │                   ├── routes/  │
├── docs/    │                   ├── docs/    │
└── .venv/   │                   └── .venv/   │
             └──────────┬────────────────────┘
                        ▼
              /var/www/html/sbp_mq_dev/.git   ← ЕДИНЫЙ репозиторий
              (объекты, refs, конфиг — одни для обоих worktree)
```

- **`.git`** — только в `sbp_mq_dev` (главный worktree)
- **В `sbp_mq`** — файл `.git` (ссылка на главный `.git/worktrees/sbp_mq`)
- **Ветки** `dev` и `main` — **общие**, но **одновременно checked out только в одном worktree**

### Проверить

```bash
git worktree list
```

```
/var/www/html/sbp_mq      2b2f5aa [main]
/var/www/html/sbp_mq_dev  51c4569 [dev]
```

### Основные команды

```bash
# Посмотреть все worktree
git worktree list

# Добавить worktree (пример — не делаем, уже есть)
git worktree add /path/to/dir branch-name

# Удалить worktree (сначала отвязать от ветки)
git -C /path/to/dir checkout --detach
git worktree remove /path/to/dir

# Почистить «мертвые» записи
git worktree prune
```

### Ограничение

⚠️ **Ветку нельзя checked out в двух worktree одновременно.**

Попытка:
```bash
cd /var/www/html/sbp_mq
git checkout dev
# fatal: 'dev' is already checked out at '/var/www/html/sbp_mq_dev'
```

**Обход:** работать с веткой `dev` **только в DEV-директории**.
В PROD-директории — только `main` (никогда не checkout'ить `dev`).

---

## 🔀 Поток изменений

### Разработка в DEV

```bash
cd /var/www/html/sbp_mq_dev        # ← всегда здесь

# 1. Изменить код
vim sbp.py

# 2. Посмотреть статус
git status
git diff

# 3. Закоммитить
git add sbp.py
git commit -m "fix: описание"

# 4. (Опционально) запушить сразу
git push origin dev
```

### Деплой в PROD

```bash
cd /var/www/html/sbp_mq_dev
./deploy.sh
```

Что делает `deploy.sh` (см. [deployment.md](deployment.md)):

1. `git push origin dev` — отправить всё в GitHub
2. `cd $PROD_DIR && git pull origin main && git merge dev && git push origin main`
3. `pip install -r requirements.txt` (если менялся)
4. `sudo systemctl restart sbp_mq-debug.service`
5. Healthcheck 30×1с

**Push в `main` руками НЕ нужен** — всё делает `deploy.sh`.

---

## 🚀 Как пушить

### Только `dev` (без деплоя)

```bash
cd /var/www/html/sbp_mq_dev
git push origin dev
```

### Обновить локальный `main` (без деплоя)

```bash
cd /var/www/html/sbp_mq       # PROD worktree
git pull origin main
```

### Полный деплой (push dev + merge main + push main + restart)

```bash
cd /var/www/html/sbp_mq_dev
./deploy.sh
```

### Синхронизировать `dev` из `main` (если что-то появилось в main)

Обычно **не нужно**, но если что-то правилось напрямую в `main`:

```bash
cd /var/www/html/sbp_mq       # PROD
git checkout main             # на всякий случай
git pull origin main

cd /var/www/html/sbp_mq_dev   # DEV
git merge main                # влить изменения из main в dev
# разрешить конфликты, если есть
git push origin dev
```

---

## 🔑 SSH к GitHub

### Конфиг `~/.ssh/config`

```
Host github.com
    Hostname ssh.github.com
    Port 443
    User git
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

### Почему через `ssh.github.com:443`

- **Порт 22** на сервере нестабилен (провайдер/фаервол режет)
- GitHub поддерживает SSH через **порт 443** на `ssh.github.com`
- Трафик похож на HTTPS — реже блокируется

### Проверка

```bash
ssh -T git@github.com
# Hi bjdanko5! You've successfully authenticated, but GitHub does not provide shell access.
```

Если не работает — проверить:

```bash
# какой хост подставляется
ssh -vT git@github.com 2>&1 | grep -E "Connecting|Authenticated"
# должно быть: Connecting to ssh.github.com port 443
```

### Remote

```bash
git remote -v
# origin  git@github.com:bjdanko5/sbp_mq.git (fetch)
# origin  git@github.com:bjdanko5/sbp_mq.git (push)
```

**SSH, не HTTPS.** Credentials — ключ `~/.ssh/id_*`, без ввода пароля.

---

## 📝 Правила коммитов

### Стиль сообщений

**Формат:** `<type>(<scope>): <описание>`

| Type | Когда |
|------|-------|
| `feat` | новая фича |
| `fix` | баг-фикс |
| `docs` | только документация |
| `refactor` | рефакторинг без изменения поведения |
| `perf` | оптимизация |
| `chore` | рутина (deps, конфиги, скрипты) |
| `test` | тесты |

**Примеры из истории проекта:**

```
feat(monitor): показывать текст ошибки в карточке упавшего Job
fix(deploy): timeout 120s для pip install + пропуск, если requirements.txt не менялся
docs: architecture.md — архитектура, слои, потоки, диаграммы
docs: роут /project-docs для Markdown-документации + healthcheck в restart_dev.sh
```

### Что **нельзя** коммитить

Проверь `.gitignore`:

| Не в git | Причина |
|----------|---------|
| `.env` | секреты (пароли, порты) |
| `.venv/` | локальное окружение |
| `logs/` | рантайм |
| `data/` | рантайм |
| `__pycache__/`, `*.pyc` | байткод |
| `requests.db` | локальная SQLite |
| `*.log` | логи |
| `*.tar.gz` | бэкапы |
| `.idea/`, `.vscode/` | IDE (кроме shared-конфигов) |

**Перед `git add`** — глазами посмотреть `git status`, убедиться, что нет лишнего.

### Проверка `.gitignore`

```bash
cat .gitignore
```

Если что-то чувствительное случайно попало в индекс:

```bash
git rm --cached <file>       # убрать из индекса, оставить в рабочей копии
echo "<file>" >> .gitignore
git commit -m "chore: игнорировать <file>"
```

---

## 🆘 Типовые проблемы

### ❌ `fatal: 'dev' is already checked out at ...`

```
fatal: 'dev' is already checked out at '/var/www/html/sbp_mq_dev'
```

**Причина:** ветка `dev` уже checked out в DEV-worktree, а ты пытаешься
checkout'ить её в PROD.

**Решение:** работать с `dev` только в DEV.

### ❌ `failed to push some refs`

```
! [rejected]        dev -> dev (non-fast-forward)
```

**Причина:** на `origin/dev` есть коммиты, которых нет у тебя (кто-то ещё пушил).

**Решение:**

```bash
cd /var/www/html/sbp_mq_dev

# 1. Посмотреть, что там
git fetch origin
git log --oneline --graph origin/dev..dev       # что у тебя
git log --oneline --graph dev..origin/dev       # что у них

# 2. Влить
git pull --rebase origin dev
# разрешить конфликты, если есть
git push origin dev
```

### ❌ `Permission denied (publickey)`

```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
```

**Причины:**
1. Нет ключа в `~/.ssh/`
2. Ключ не добавлен в GitHub
3. SSH-конфиг сломан

**Проверка:**

```bash
# 1. Какой хост используется
ssh -vT git@github.com 2>&1 | grep Connecting

# 2. Что говорит ssh-agent
ssh-add -l

# 3. Если ключа нет — сгенерировать
ssh-keygen -t ed25519 -C "user@p-ivc"
cat ~/.ssh/id_ed25519.pub        # → вставить в GitHub → Settings → SSH keys
```

### ❌ `non-fast-forward` при `git pull`

```bash
# Если локальные коммиты и чужие разошлись
git pull --rebase origin dev
# или merge
git pull --no-rebase origin dev
```

`--rebase` — «поставить мои коммиты поверх их», чище история.
`--no-rebase` — merge-коммит.

### ❌ Случайно закоммичен `.env` или пароль

**Немедленно:**

1. **Ротация секрета** — пароль сменить (1С, база, банк — что утекло)
2. **Убрать из истории:**

```bash
# Если коммит — последний
git rm --cached .env
echo ".env" >> .gitignore
git commit --amend -m "chore: убрать .env из индекса"

# Если коммит — несколько назад
git filter-repo --path .env --invert-paths    # переписывает всю историю
git push --force origin dev

# ВСЕМ разработчикам — git pull --rebase / clone заново
```

⚠️ **`filter-repo` переписывает SHA всех коммитов** — координация обязательна.
В крайнем случае — **считать секрет скомпрометированным** и сменить.

### ❌ `error: pathspec 'X' did not match any file(s)`

Обычно опечатка в имени файла. Проверь:

```bash
git status
ls X
```

### ❌ `Your branch is ahead of 'origin/dev' by N commits`

Это **норма** — значит есть локальные коммиты, не запушенные. Пуш:

```bash
git push origin dev
```

---

## 🧭 Полезные команды

### Посмотреть состояние

```bash
# Все ветки + отставание/опережение
git branch -vv

# Все worktree
git worktree list

# Граф всех веток
git log --oneline --graph --all -20

# Что уже запушено, что нет
git log --oneline origin/dev..dev
```

### Откатить

```bash
# Последний коммит — вернуть в индекс
git reset --soft HEAD~1

# Последний коммит — отменить полностью
git reset --hard HEAD~1

# Файл — вернуть из HEAD
git checkout HEAD -- path/to/file

# Файл — отменить staged
git restore --staged path/to/file
```

### Посмотреть чужие изменения

```bash
git fetch origin
git diff dev origin/dev
git log --oneline dev..origin/dev
```

---

## 🔗 Связанные документы

- [deployment.md](deployment.md) — `deploy.sh`, systemd, окружения
- [architecture.md](architecture.md) — общая архитектура
- [scripts/sh_prod.md](scripts/sh_prod.md) — `deploy_to_prod.sh`, backup/restore (TODO)