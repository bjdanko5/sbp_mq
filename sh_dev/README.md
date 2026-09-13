# sh_dev — скрипты для DEV

Работают только с dev-окружением:
- Сервисы: sbp_mq-dev.service, sbp_mq-dev-worker*
- Порт: 8512
- Redis: DB 1
- Папки: /sbp/mq_dev/, /var/www/html/sbp_mq_dev/

## Скрипты

| Скрипт | Что делает |
|--------|-----------|
| restart_dev.sh | Перезапуск dev-сервиса |
| restart_dev_workers.sh | Перезапуск dev-воркеров |
| status_dev.sh | Статус dev-сервисов |
| logs_dev.sh | Логи dev |
| logs_dev_all.sh | Агрегированный лог dev |
| health_dev.sh | Healthcheck dev |
| reset_dev.sh | Очистка dev-данных |
| quick_test.sh | Быстрый тест dev |
| test_create_payload_mq.sh | Тест create_payload_mq dev |
| test_monitor_v2.sh | Полный тест мониторинга dev |
