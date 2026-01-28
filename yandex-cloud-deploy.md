# Развертывание в Yandex Cloud Functions

Инструкция по развертыванию автоматизации Kaiten в Yandex Cloud Functions.

## Преимущества использования Yandex Cloud Functions

- ✅ Не требует собственного сервера
- ✅ Автоматическое масштабирование
- ✅ Оплата только за использование
- ✅ Встроенная поддержка HTTP и Timer триггеров
- ✅ Простое управление через консоль или CLI

## Подготовка

### 1. Установите Yandex Cloud CLI (опционально)

```bash
# Для Linux
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash

# Инициализация
yc init
```

### 2. Подготовьте код для загрузки

Создайте ZIP-архив с кодом:

```bash
# Создайте директорию для упаковки
mkdir kaiten-function
cd kaiten-function

# Скопируйте необходимые файлы
cp ../kaiten_automation.py .
cp ../index.py .
cp ../requirements.txt .

# Создайте ZIP-архив
zip -r kaiten-automation.zip .
```

**Важно:** В ZIP должны быть:
- `index.py` - точка входа (handler) - **обязательно**
- `requirements.txt` - зависимости - **обязательно**
- `kaiten_automation.py` - опционально (index.py самодостаточен, но если файл есть, он будет использован)

## Развертывание через консоль Yandex Cloud

### Шаг 1: Создание функции

1. Откройте [Yandex Cloud Console](https://console.cloud.yandex.ru/)
2. Перейдите в раздел **Cloud Functions**
3. Нажмите **Создать функцию**
4. Заполните:
   - **Имя:** `kaiten-automation`
   - **Описание:** `Автоматизация обновления статуса карточек Kaiten`
   - **Среда выполнения:** `python311` или `python312`

### Шаг 2: Загрузка кода

1. В разделе **Код функции** выберите **ZIP-архив**
2. Загрузите созданный `kaiten-automation.zip`
3. Укажите:
   - **Точка входа:** `index.handler`
   - **Таймаут:** 60 секунд (или больше, если карточек много)
   - **Память:** 128 МБ (обычно достаточно)

### Шаг 3: Настройка переменных окружения

В разделе **Переменные окружения** добавьте:

```
KAITEN_API_URL=https://your-space.kaiten.ru/api/latest
KAITEN_API_TOKEN=your_api_token_here
NUMERIC_FIELD_IDS=field_id_1,field_id_2,field_id_3
STATUS_FIELD_ID=status_field_id
STATUS_GOLD=Gold
STATUS_SILVER=Silver
STATUS_BRONZE=Bronze
THRESHOLD_GOLD=13
THRESHOLD_SILVER=9
```

Опционально:
```
BOARD_ID=board_id_here
SPACE_ID=space_id_here
```

### Шаг 4: Создание триггера

#### Вариант A: HTTP-триггер (для вебхуков)

1. Перейдите в раздел **Триггеры**
2. Нажмите **Создать триггер**
3. Выберите **HTTP-триггер**
4. Настройте:
   - **Имя:** `kaiten-webhook`
   - **HTTP-метод:** `POST`
   - **Путь:** `/webhook` (или любой другой)
5. Скопируйте **URL триггера** - он понадобится для настройки вебхука в Kaiten

#### Вариант B: Timer-триггер (периодический запуск)

1. Перейдите в раздел **Триггеры**
2. Нажмите **Создать триггер**
3. Выберите **Timer**
4. Настройте:
   - **Имя:** `kaiten-schedule`
   - **Cron-выражение:** `*/5 * * * *` (каждые 5 минут)
   - Или используйте интервал: `rate(5 minutes)`

Примеры cron-выражений:
- `*/5 * * * *` - каждые 5 минут
- `0 * * * *` - каждый час
- `0 */6 * * *` - каждые 6 часов
- `0 9 * * *` - каждый день в 9:00

## Развертывание через CLI

### Создание функции

```bash
yc serverless function create \
  --name kaiten-automation \
  --description "Автоматизация Kaiten"
```

### Загрузка кода

```bash
yc serverless function version create \
  --function-name kaiten-automation \
  --runtime python311 \
  --entrypoint index.handler \
  --memory 128m \
  --execution-timeout 60s \
  --source-path kaiten-automation.zip \
  --environment KAITEN_API_URL=https://your-space.kaiten.ru/api/latest \
  --environment KAITEN_API_TOKEN=your_token \
  --environment NUMERIC_FIELD_IDS=field1,field2,field3 \
  --environment STATUS_FIELD_ID=status_field
```

### Создание HTTP-триггера

```bash
yc serverless trigger create http \
  --name kaiten-webhook \
  --function-name kaiten-automation \
  --path /webhook \
  --method POST
```

### Создание Timer-триггера

```bash
yc serverless trigger create timer \
  --name kaiten-schedule \
  --function-name kaiten-automation \
  --cron-expression "*/5 * * * *"
```

## Настройка вебхука в Kaiten

Если используете HTTP-триггер:

1. Откройте настройки вашего пространства в Kaiten
2. Найдите раздел **Webhooks** или **Интеграции**
3. Добавьте новый вебхук:
   - **URL:** `https://functions.yandexcloud.net/your-function-id/webhook`
   - **События:** Выберите "Card Updated" или аналогичное
   - **Метод:** POST

## Тестирование

### Тест HTTP-триггера

```bash
curl -X POST https://functions.yandexcloud.net/your-function-id/webhook \
  -H "Content-Type: application/json" \
  -d '{"card_id": 12345}'
```

### Тест через консоль

1. Откройте функцию в консоли Yandex Cloud
2. Перейдите в раздел **Тестирование**
3. Выберите **HTTP-триггер**
4. Введите тестовые данные:
```json
{
  "httpMethod": "POST",
  "body": "{\"card_id\": 12345}"
}
```

### Просмотр логов

```bash
# Через CLI
yc serverless function logs kaiten-automation

# Или в консоли: раздел "Логи"
```

## Обновление функции

### Через консоль

1. Загрузите новый ZIP-архив
2. Обновите переменные окружения при необходимости
3. Функция обновится автоматически

### Через CLI

```bash
yc serverless function version create \
  --function-name kaiten-automation \
  --source-path kaiten-automation.zip \
  --runtime python311 \
  --entrypoint index.handler
```

## Мониторинг и отладка

### Просмотр метрик

В консоли Yandex Cloud доступны метрики:
- Количество вызовов
- Время выполнения
- Ошибки
- Использование памяти

### Логирование

Все логи доступны в разделе **Логи** функции. Используйте `logger.info()`, `logger.error()` для отладки.

## Ограничения и рекомендации

### Ограничения Yandex Cloud Functions

- **Таймаут:** Максимум 300 секунд (5 минут) для HTTP-триггера
- **Память:** От 128 МБ до 4 ГБ
- **Размер кода:** До 50 МБ (ZIP-архив)

### Рекомендации

1. **Для большого количества карточек:**
   - Используйте фильтрацию по `BOARD_ID` или `SPACE_ID`
   - Увеличьте таймаут до максимума
   - Рассмотрите обработку батчами

2. **Для вебхуков:**
   - Настройте обработку ошибок и retry
   - Логируйте все события для отладки

3. **Безопасность:**
   - Храните API токены в переменных окружения (не в коде)
   - Используйте HTTPS для вебхуков
   - Ограничьте доступ к HTTP-триггеру (если возможно)

## Стоимость

Yandex Cloud Functions тарифицируется по:
- Количеству вызовов
- Времени выполнения
- Использованию памяти

Для типичного использования (несколько вызовов в час) стоимость минимальна.

## Troubleshooting

### Ошибка "Unable to import module index"

Если вы получили ошибку `Unable to import module index: No module named 'index'`:

1. **Проверьте точку входа:** Убедитесь, что в настройках функции указано `index.handler` (не `index.py.handler`)
2. **Проверьте структуру ZIP:** Файл `index.py` должен быть в корне ZIP-архива, а не в подпапке
3. **Пересоздайте архив:** Используйте скрипт `pack_for_yandex_cloud.sh` для правильной упаковки

**Важно:** Файл `index.py` самодостаточен и не требует `kaiten_automation.py` для работы. Если модуль не найден, используются встроенные классы.

### Функция не запускается

1. Проверьте логи в консоли
2. Убедитесь, что все переменные окружения установлены
3. Проверьте формат ZIP-архива

### Ошибки API Kaiten

1. Проверьте валидность API токена
2. Убедитесь, что токен имеет права на обновление карточек
3. Проверьте правильность ID полей

### Таймаут функции

1. Увеличьте таймаут в настройках функции
2. Ограничьте количество обрабатываемых карточек
3. Используйте фильтрацию по доске/пространству

## Дополнительные ресурсы

- [Документация Yandex Cloud Functions](https://cloud.yandex.ru/docs/functions/)
- [Документация Kaiten API](https://developers.kaiten.ru/)
