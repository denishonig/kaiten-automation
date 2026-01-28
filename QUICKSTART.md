# Быстрый старт

## Шаг 1: Установка зависимостей

```bash
pip install -r requirements.txt
```

## Шаг 2: Настройка конфигурации

```bash
cp config.example.env .env
```

Отредактируйте `.env` и укажите:
- `KAITEN_API_URL` - URL вашего Kaiten пространства
- `KAITEN_API_TOKEN` - API токен (получите в настройках Kaiten)
- `NUMERIC_FIELD_IDS` - ID числовых полей через запятую
- `STATUS_FIELD_ID` - ID поля статуса

## Шаг 3: Как найти ID полей

### Способ 1: Через API

1. Откройте карточку в Kaiten
2. Откройте консоль браузера (F12)
3. Перейдите на вкладку Network
4. Обновите карточку
5. Найдите запрос к `/api/latest/cards/{id}`
6. В ответе найдите структуру `custom_properties` или `properties`
7. Скопируйте ID нужных полей

### Способ 2: Через API напрямую

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-space.kaiten.ru/api/latest/cards/CARD_ID
```

В ответе найдите поля и их ID.

## Шаг 4: Тестирование

Проверьте логику без реальных запросов:

```bash
python test_automation.py
```

## Шаг 5: Запуск

### Вариант A: Обработка одной карточки

```bash
python kaiten_automation.py 12345
```

### Вариант B: Обработка всех карточек

```bash
python kaiten_automation.py
```

### Вариант C: Вебхук-сервер (рекомендуется)

```bash
python webhook_handler.py
```

Затем настройте вебхук в Kaiten на URL: `http://your-server:5000/webhook/kaiten`

## Пример конфигурации

```env
KAITEN_API_URL=https://mycompany.kaiten.ru/api/latest
KAITEN_API_TOKEN=abc123xyz789
NUMERIC_FIELD_IDS=12345,12346,12347
STATUS_FIELD_ID=12348
STATUS_GOLD=Gold
STATUS_SILVER=Silver
STATUS_BRONZE=Bronze
THRESHOLD_GOLD=13
THRESHOLD_SILVER=9
```

## Проверка работы

После запуска проверьте логи. Вы должны увидеть сообщения вида:

```
INFO - Карточка 12345: сумма = 15.0, новый статус = Gold
INFO - Статус карточки 12345 успешно обновлен на Gold
```

## Где запускать в продакшене

### Вариант 1: Yandex Cloud Functions (рекомендуется)

**Быстрый старт:**

1. Упакуйте код:
```bash
./pack_for_yandex_cloud.sh
```

2. Загрузите `kaiten-automation.zip` в Yandex Cloud Functions через консоль

3. Настройте переменные окружения в консоли

4. Создайте HTTP или Timer триггер

**Подробная инструкция:** см. [yandex-cloud-deploy.md](yandex-cloud-deploy.md)

**Преимущества:**
- Не требует собственного сервера
- Автоматическое масштабирование
- Оплата только за использование

### Вариант 2: Вебхук-сервер на вашем сервере

1. Установите на сервер
2. Настройте systemd сервис (см. `systemd/kaiten-automation.service.example`)
3. Настройте вебхук в Kaiten
4. Готово!

### Вариант 3: Cron задача

Добавьте в crontab:

```bash
*/5 * * * * cd /path/to/kaiten-automation && python3 kaiten_automation.py
```

Запуск каждые 5 минут для обработки всех карточек.
