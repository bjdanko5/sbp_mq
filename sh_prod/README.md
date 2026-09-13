# sh_prod — скрипты для PROD

Работают только с prod-окружением:
- Сервисы: sbp_mq-debug.service, sbp_mq-worker*
- Порт: 8511
- Redis: DB 0
- Папки: /sbp/mq/, /var/www/html/sbp_mq/

## Скрипты

| Скрипт | Что делает |
|--------|-----------|
| deploy_to_prod.sh | Merge dev -> main + рестарт prod |
| restart_prod.sh | Перезапуск prod-сервиса |
| restart_prod_workers.sh | Перезапуск prod-воркеров |
| status_prod.sh | Статус prod-сервисов |
| logs_prod.sh | Логи prod |
| health_prod.sh | Healthcheck prod |
| backup_sbp_mq.sh | Бэкап prod |
| restore_sbp_mq.sh | Восстановление prod |
| restore_sbp_mq_with_venv.sh | Восстановление prod с venv |

WARNING: скрипты работают с продакшеном!
