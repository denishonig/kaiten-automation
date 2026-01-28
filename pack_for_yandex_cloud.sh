#!/bin/bash
# Скрипт для упаковки кода для Yandex Cloud Functions

set -e

PACKAGE_NAME="kaiten-automation"
TEMP_DIR=$(mktemp -d)

echo "📦 Упаковка кода для Yandex Cloud Functions..."

# Копируем необходимые файлы напрямую в временную директорию (без подпапки)
echo "📋 Копирование файлов..."
cp index.py "$TEMP_DIR/"
cp requirements.txt "$TEMP_DIR/"

# kaiten_automation.py опционален - index.py самодостаточен
# но если он есть, скопируем его для возможного использования
if [ -f kaiten_automation.py ]; then
    cp kaiten_automation.py "$TEMP_DIR/"
    echo "   ✓ kaiten_automation.py (опционально)"
fi

# Проверяем наличие обязательных файлов
if [ ! -f "$TEMP_DIR/index.py" ]; then
    echo "❌ Ошибка: index.py не найден"
    exit 1
fi

if [ ! -f "$TEMP_DIR/requirements.txt" ]; then
    echo "❌ Ошибка: requirements.txt не найден"
    exit 1
fi

echo "   ✓ index.py (обязательно)"
echo "   ✓ requirements.txt (обязательно)"

# Создаем ZIP-архив из корня временной директории (файлы должны быть в корне ZIP)
echo "🗜️  Создание ZIP-архива..."
cd "$TEMP_DIR"
zip -r "$PACKAGE_NAME.zip" . > /dev/null

# Перемещаем архив в текущую директорию
mv "$PACKAGE_NAME.zip" "$OLDPWD/"

# Очистка
rm -rf "$TEMP_DIR"

echo "✅ Готово! Архив создан: $PACKAGE_NAME.zip"
echo ""
echo "📤 Следующие шаги:"
echo "1. Загрузите $PACKAGE_NAME.zip в Yandex Cloud Functions"
echo "2. Укажите точку входа: index.handler"
echo "3. Настройте переменные окружения"
echo ""
echo "📖 Подробная инструкция: yandex-cloud-deploy.md"
