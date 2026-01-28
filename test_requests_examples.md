# Примеры HTTP-запросов для тестирования

## Вариант 1: JSON в body (рекомендуется)

### Запрос с card_id в body:

```json
{
    "httpMethod": "POST",
    "headers": {
        "Content-Type": "application/json"
    },
    "body": "{\"card_id\": 12345}",
    "isBase64Encoded": false
}
```

### Запрос с card объектом:

```json
{
    "httpMethod": "POST",
    "headers": {
        "Content-Type": "application/json"
    },
    "body": "{\"card\": {\"id\": 12345}}",
    "isBase64Encoded": false
}
```

### Запрос с card как числом:

```json
{
    "httpMethod": "POST",
    "headers": {
        "Content-Type": "application/json"
    },
    "body": "{\"card\": 12345}",
    "isBase64Encoded": false
}
```

## Вариант 2: card_id в query параметрах

```json
{
    "httpMethod": "POST",
    "queryStringParameters": {
        "card_id": "12345"
    }
}
```

## Вариант 3: Base64-encoded body

```json
{
    "httpMethod": "POST",
    "headers": {
        "Content-Type": "application/json"
    },
    "body": "eyJjYXJkX2lkIjogMTIzNDV9",
    "isBase64Encoded": true
}
```

Где `eyJjYXJkX2lkIjogMTIzNDV9` - это base64-кодированный JSON `{"card_id": 12345}`

## Примеры curl команд

### Простой запрос с card_id в body:

```bash
curl -X POST https://your-function-url \
  -H "Content-Type: application/json" \
  -d '{"card_id": 12345}'
```

### Запрос с card_id в query параметрах:

```bash
curl -X POST "https://your-function-url?card_id=12345" \
  -H "Content-Type: application/json"
```

### Запрос с полным объектом card:

```bash
curl -X POST https://your-function-url \
  -H "Content-Type: application/json" \
  -d '{"card": {"id": 12345}}'
```

## Формат ответа

### Успешный ответ:

```json
{
    "statusCode": 200,
    "body": "{\"status\": \"success\", \"card_id\": 12345}"
}
```

### Ошибка (card_id не найден):

```json
{
    "statusCode": 400,
    "body": "{\"error\": \"card_id not found in request\"}"
}
```

### Ошибка обработки:

```json
{
    "statusCode": 500,
    "body": "{\"status\": \"error\", \"card_id\": 12345, \"message\": \"Failed to update card status\"}"
}
```

## Примечания

1. **card_id** должен быть числом (ID карточки в Kaiten)
2. Поддерживаются следующие форматы в body:
   - `{"card_id": 12345}`
   - `{"card": {"id": 12345}}`
   - `{"card": 12345}`
   - `{"id": 12345}`
3. Также можно передать `card_id` через query параметр: `?card_id=12345`
4. Body может быть закодирован в base64 (установите `isBase64Encoded: true`)
