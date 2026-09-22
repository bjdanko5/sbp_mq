# sh_dev — скрипты для DEV

Работают только с dev-окружением:
- Сервисы: sbp_mq-dev.service, sbp_mq-dev-worker*
- Порт: 8512
- Redis: DB 1
- Папки: /sbp/mq_dev/, /var/www/html/sbp_mq_dev/

## Скрипты

| Скрипт | Что делает |
|--------|-----------|
| restart_dev.sh | Перезапуск dev-сервиса (с ожиданием старта) |
| restart_dev_workers.sh | Перезапуск dev-воркеров |
| status_dev.sh | Статус dev-сервисов |
| logs_dev.sh | Логи dev (journalctl) |
| logs_dev_all.sh | Агрегированный лог dev (tail -f all.log) |
| health_dev.sh | Healthcheck dev (/health + /health/detailed) |
| reset_dev.sh | Очистка dev-данных (Redis DB 1, jobs, logs) |
| quick_test.sh | Быстрый smoke-тест dev |
| test_create_payload_mq.sh | Тест create_payload_mq dev |
| test_monitor_v2.sh | Полный тест мониторинга (9 Job, callback, SOAP) |
| test_stop_payload.sh | Тест stop_payload (legacy + new эндпоинт) |
| test_soap_on_error.sh | Проверка SOAP при ошибке Job |
| collect_context.sh | Сборка контекста для новой сессии |