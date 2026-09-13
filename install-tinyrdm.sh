#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ✅ ДАННЫЕ ХРАНЯТСЯ В ДОМАШНЕЙ ПАПКЕ
DATA_DIR="/home/user/tinyrdm_data"

echo -e "${YELLOW}🚀 Установка Tiny RDM через Docker...${NC}"
echo -e "${YELLOW}📂 Данные: ${DATA_DIR}${NC}"
echo ""

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен.${NC}"
    exit 1
fi

# Создаём папку данных
mkdir -p "$DATA_DIR"
echo -e "${GREEN}✅ Папка данных: ${DATA_DIR}${NC}"

# Удаление старого контейнера
if docker ps -a --format '{{.Names}}' | grep -q "^tinyrdm$"; then
    echo -e "${YELLOW}⚠️ Удаляем старый контейнер 'tinyrdm'...${NC}"
    docker stop tinyrdm 2>/dev/null
    docker rm tinyrdm 2>/dev/null
    echo -e "${GREEN}✅ Старый контейнер удалён.${NC}"
fi

# Запуск контейнера
echo -e "${YELLOW}📦 Запускаем контейнер Tiny RDM...${NC}"

docker run -d \
    --name tinyrdm \
    --restart unless-stopped \
    -p 0.0.0.0:8086:8086 \
    -e ADMIN_USERNAME=admin \
    -e ADMIN_PASSWORD=tinyrdm \
    -v "$DATA_DIR":/app/tinyrdm \
    ghcr.io/tiny-craft/tiny-rdm:latest

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Tiny RDM успешно установлен!${NC}"
    echo ""
    echo -e "${GREEN}📋 Данные для входа:${NC}"
    echo -e "   Логин:  ${YELLOW}admin${NC}"
    echo -e "   Пароль: ${YELLOW}tinyrdm${NC}"
    echo ""
    echo -e "${GREEN}🌐 Открыть в браузере:${NC}"
    echo -e "   http://localhost:8086"
    echo -e "   http://192.168.10.130:8086"
    echo ""
    echo -e "${GREEN}📂 Данные: ${YELLOW}${DATA_DIR}${NC}"
    echo ""
    echo -e "${YELLOW}🔧 Управление:${NC}"
    echo "   docker stop tinyrdm"
    echo "   docker start tinyrdm"
    echo "   docker restart tinyrdm"
    echo "   docker rm -f tinyrdm"
    echo "   docker logs tinyrdm"
else
    echo -e "${RED}❌ Ошибка запуска${NC}"
    echo -e "${YELLOW}Логи: docker logs tinyrdm${NC}"
    exit 1
fi
