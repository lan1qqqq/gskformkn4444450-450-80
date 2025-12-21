#!/bin/sh
set -e
# Инициализация прав на /app/data (важно для volume)
mkdir -p /app/data
chmod 777 /app/data
chown -R $(id -u):$(id -g) /app/data 2>/dev/null || true
# Запускаем основное приложение
exec "$@"
