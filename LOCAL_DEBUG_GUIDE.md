# Инструкция по локальной отладке Yandex Cloud Functions

Это руководство поможет вам тестировать и отлаживать функции Yandex Cloud Functions локально на вашем компьютере перед деплоем.

## 🚀 Быстрый старт

1. **Создайте файл `.env`** в корне проекта:
   ```bash
   KAITEN_API_URL=https://your-space.kaiten.ru/api/latest
   KAITEN_API_TOKEN=your-api-token
   LOG_LEVEL=DEBUG
   ```

2. **Запустите тестовый скрипт**:
   ```bash
   # Тест HTTP-триггера (использует parsed_webhook.json)
   python3 test_local.py --type http
   
   # Тест Timer-триггера
   python3 test_local.py --type timer
   
   # Тест обоих
   python3 test_local.py --type both
   ```

3. **Проверьте вывод** - вы увидите детальные логи и результат выполнения функции.

## Содержание

1. [Базовый подход: эмуляция event объекта](#базовый-подход-эмуляция-event-объекта)
2. [Создание тестового скрипта](#создание-тестового-скрипта)
3. [Эмуляция HTTP-триггера](#эмуляция-http-триггера)
4. [Эмуляция Timer-триггера](#эмуляция-timer-триггера)
5. [Тестирование с реальными данными](#тестирование-с-реальными-данными)
6. [Использование Yandex Cloud Functions Emulator](#использование-yandex-cloud-functions-emulator)
7. [Отладка с помощью VS Code](#отладка-с-помощью-vs-code)
8. [Полезные советы](#полезные-советы)

## Базовый подход: эмуляция event объекта

Yandex Cloud Functions передают в функцию объект `event`, который содержит данные о запросе. Вы можете создать тестовый скрипт, который эмулирует этот объект.

### Структура event для HTTP-триггера

```python
http_event = {
    "httpMethod": "POST",
    "path": "/webhook",
    "headers": {
        "Content-Type": "application/json",
        "User-Agent": "Kaiten/1.0"
    },
    "body": '{"id": 12345, "title": "Test card"}',
    "isBase64Encoded": False,
    "queryStringParameters": None,
    "pathParameters": None,
    "requestContext": {
        "requestId": "test-request-id",
        "functionName": "kaiten-automation"
    }
}
```

### Структура event для Timer-триггера

```python
timer_event = {
    "source": "system",
    "messages": [
        {
            "event_metadata": {
                "event_id": "test-event-id",
                "event_type": "yandex.cloud.events.serverless.triggers.TimerMessage",
                "created_at": "2026-01-24T12:00:00Z"
            },
            "details": {
                "trigger_id": "test-trigger-id"
            }
        }
    ]
}
```

## Создание тестового скрипта

Создайте файл `test_local.py` в корне проекта:

```python
#!/usr/bin/env python3
"""
Локальный тестовый скрипт для отладки Yandex Cloud Functions
"""

import json
import os
import sys
from typing import Dict, Any

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

# Импортируем handler из index.py
from index import handler

# Загружаем переменные окружения из .env файла (если используется)
def load_env_file():
    """Загружает переменные окружения из .env файла"""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().replace('"', '').replace("'", "")

# Загружаем переменные окружения
load_env_file()

# Устанавливаем переменные окружения для тестирования (если не заданы)
if 'KAITEN_API_URL' not in os.environ:
    os.environ['KAITEN_API_URL'] = 'https://your-space.kaiten.ru/api/latest'
if 'KAITEN_API_TOKEN' not in os.environ:
    os.environ['KAITEN_API_TOKEN'] = 'your-test-token'

def test_http_trigger():
    """Тестирование HTTP-триггера"""
    print("=" * 80)
    print("ТЕСТ HTTP-ТРИГГЕРА")
    print("=" * 80)
    
    # Загружаем тестовый JSON из файла
    test_json_path = os.path.join(os.path.dirname(__file__), 'parsed_webhook.json')
    if os.path.exists(test_json_path):
        with open(test_json_path, 'r', encoding='utf-8') as f:
            body_data = json.load(f)
        body_str = json.dumps(body_data, ensure_ascii=False)
    else:
        # Используем простой тестовый JSON
        body_str = json.dumps({
            "id": 59682997,
            "title": "Тестовая задача",
            "board_id": 1613875
        }, ensure_ascii=False)
    
    event = {
        "httpMethod": "POST",
        "path": "/webhook",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Kaiten/1.0"
        },
        "body": body_str,
        "isBase64Encoded": False,
        "queryStringParameters": None,
        "pathParameters": None,
        "requestContext": {
            "requestId": "test-request-id",
            "functionName": "kaiten-automation"
        }
    }
    
    # Создаем mock context
    class MockContext:
        def __init__(self):
            self.request_id = "test-request-id"
            self.function_name = "kaiten-automation"
            self.function_version = "test-version"
            self.memory_limit_in_mb = 128
            self.timeout = 60
    
    context = MockContext()
    
    # Вызываем handler
    try:
        result = handler(event, context)
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТ:")
        print("=" * 80)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_timer_trigger():
    """Тестирование Timer-триггера"""
    print("=" * 80)
    print("ТЕСТ TIMER-ТРИГГЕРА")
    print("=" * 80)
    
    event = {
        "source": "system",
        "messages": [
            {
                "event_metadata": {
                    "event_id": "test-event-id",
                    "event_type": "yandex.cloud.events.serverless.triggers.TimerMessage",
                    "created_at": "2026-01-24T12:00:00Z"
                },
                "details": {
                    "trigger_id": "test-trigger-id"
                }
            }
        ]
    }
    
    class MockContext:
        def __init__(self):
            self.request_id = "test-request-id"
            self.function_name = "kaiten-automation"
            self.function_version = "test-version"
            self.memory_limit_in_mb = 128
            self.timeout = 60
    
    context = MockContext()
    
    try:
        result = handler(event, context)
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТ:")
        print("=" * 80)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Тестирование Yandex Cloud Functions локально')
    parser.add_argument('--type', choices=['http', 'timer', 'both'], default='http',
                       help='Тип триггера для тестирования')
    
    args = parser.parse_args()
    
    if args.type == 'http' or args.type == 'both':
        test_http_trigger()
    
    if args.type == 'timer' or args.type == 'both':
        test_timer_trigger()
```

## Эмуляция HTTP-триггера

### Использование тестового скрипта

```bash
# Тест HTTP-триггера
python3 test_local.py --type http

# Тест Timer-триггера
python3 test_local.py --type timer

# Тест обоих
python3 test_local.py --type both
```

### Тестирование с разными форматами данных

Создайте файл `test_http_variants.py`:

```python
#!/usr/bin/env python3
"""Тестирование различных форматов HTTP-запросов"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from index import handler

def test_json_body():
    """Тест с JSON в body"""
    event = {
        "httpMethod": "POST",
        "body": json.dumps({"id": 12345}),
        "isBase64Encoded": False,
        "headers": {"Content-Type": "application/json"}
    }
    return handler(event, None)

def test_form_urlencoded():
    """Тест с form-urlencoded"""
    event = {
        "httpMethod": "POST",
        "body": "id=12345&title=Test",
        "isBase64Encoded": False,
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    }
    return handler(event, None)

def test_base64_body():
    """Тест с base64-encoded body"""
    import base64
    data = json.dumps({"id": 12345})
    encoded = base64.b64encode(data.encode()).decode()
    
    event = {
        "httpMethod": "POST",
        "body": encoded,
        "isBase64Encoded": True,
        "headers": {"Content-Type": "application/json"}
    }
    return handler(event, None)

def test_empty_body():
    """Тест с пустым body"""
    event = {
        "httpMethod": "POST",
        "body": "",
        "isBase64Encoded": False,
        "headers": {"Content-Type": "application/json"}
    }
    return handler(event, None)

if __name__ == "__main__":
    tests = [
        ("JSON body", test_json_body),
        ("Form URL encoded", test_form_urlencoded),
        ("Base64 encoded", test_base64_body),
        ("Empty body", test_empty_body)
    ]
    
    for name, test_func in tests:
        print(f"\n{'='*80}")
        print(f"ТЕСТ: {name}")
        print('='*80)
        try:
            result = test_func()
            print(f"Успешно: {json.dumps(result, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
```

## Эмуляция Timer-триггера

Создайте файл `test_timer.py`:

```python
#!/usr/bin/env python3
"""Тестирование Timer-триггера"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from index import handler

event = {
    "source": "system",
    "messages": [
        {
            "event_metadata": {
                "event_id": "test-event-id",
                "event_type": "yandex.cloud.events.serverless.triggers.TimerMessage",
                "created_at": "2026-01-24T12:00:00Z"
            },
            "details": {
                "trigger_id": "test-trigger-id"
            }
        }
    ]
}

if __name__ == "__main__":
    result = handler(event, None)
    print(result)
```

## Тестирование с реальными данными

### Использование реального webhook JSON

```python
#!/usr/bin/env python3
"""Тест с реальными данными из parsed_webhook.json"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from index import handler

# Загружаем реальный webhook
with open('parsed_webhook.json', 'r', encoding='utf-8') as f:
    webhook_data = json.load(f)

event = {
    "httpMethod": "POST",
    "path": "/webhook",
    "headers": {
        "Content-Type": "application/json"
    },
    "body": json.dumps(webhook_data, ensure_ascii=False),
    "isBase64Encoded": False
}

if __name__ == "__main__":
    result = handler(event, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

## Использование Yandex Cloud Functions Emulator

Yandex Cloud предоставляет эмулятор для локальной разработки.

### Установка

```bash
# Установка через pip
pip install yandex-cloud-functions-emulator

# Или через npm (если используете Node.js)
npm install -g @yandex-cloud/functions-emulator
```

### Использование

```bash
# Запуск эмулятора
yandex-cloud-functions-emulator start

# В другом терминале - отправка тестового запроса
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d @parsed_webhook.json
```

## Отладка с помощью VS Code

### Настройка launch.json

Создайте файл `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Debug HTTP Trigger",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/test_local.py",
            "args": ["--type", "http"],
            "console": "integratedTerminal",
            "justMyCode": false,
            "env": {
                "KAITEN_API_URL": "https://your-space.kaiten.ru/api/latest",
                "KAITEN_API_TOKEN": "your-token"
            }
        },
        {
            "name": "Python: Debug Timer Trigger",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/test_local.py",
            "args": ["--type", "timer"],
            "console": "integratedTerminal",
            "justMyCode": false
        }
    ]
}
```

### Использование отладчика

1. Установите точки останова (breakpoints) в коде
2. Нажмите F5 или выберите конфигурацию из меню "Run and Debug"
3. Выполнение остановится на точках останова
4. Используйте Debug Console для проверки переменных

## Полезные советы

### 1. Использование .env файла

Создайте файл `.env` в корне проекта:

```bash
KAITEN_API_URL=https://your-space.kaiten.ru/api/latest
KAITEN_API_TOKEN=your-token
LOG_LEVEL=DEBUG
```

И загружайте его в тестовом скрипте (см. пример выше).

### 2. Мокирование внешних API

Для тестирования без реальных запросов к Kaiten API:

```python
from unittest.mock import patch, MagicMock

# Мокируем KaitenClient
with patch('index.KaitenClient') as mock_client:
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    # Настраиваем возвращаемые значения
    mock_instance.get_card.return_value = {"id": 12345, "title": "Test"}
    
    # Запускаем тест
    result = handler(event, None)
```

### 3. Логирование

Включите детальное логирование:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 4. Тестирование обработки ошибок

```python
# Тест с невалидным JSON
event = {
    "httpMethod": "POST",
    "body": "{invalid json}",
    "isBase64Encoded": False
}

# Тест с отсутствующим card_id
event = {
    "httpMethod": "POST",
    "body": json.dumps({"title": "Test"}),
    "isBase64Encoded": False
}
```

### 5. Использование pytest

Создайте файл `test_index.py`:

```python
import pytest
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from index import handler, handle_http_trigger

def test_http_trigger_with_id():
    event = {
        "httpMethod": "POST",
        "body": json.dumps({"id": 12345}),
        "isBase64Encoded": False
    }
    # Мокируем evaluator
    # result = handler(event, None)
    # assert result['statusCode'] == 200

def test_http_trigger_without_id():
    event = {
        "httpMethod": "POST",
        "body": json.dumps({"title": "Test"}),
        "isBase64Encoded": False
    }
    # result = handler(event, None)
    # assert result['statusCode'] == 400
```

Запуск:

```bash
pytest test_index.py -v
```

### 6. Сравнение с реальными запросами

Сохраняйте реальные запросы от Kaiten в файлы для тестирования:

```python
# Сохраните реальный event в файл
with open('real_event.json', 'w') as f:
    json.dump(event, f, indent=2)

# Используйте для тестирования
with open('real_event.json', 'r') as f:
    real_event = json.load(f)
result = handler(real_event, None)
```

## Быстрый старт

1. Создайте файл `test_local.py` (код выше)
2. Создайте файл `.env` с переменными окружения
3. Запустите: `python3 test_local.py --type http`
4. Проверьте вывод и логи

## Дополнительные ресурсы

- [Документация Yandex Cloud Functions](https://cloud.yandex.ru/docs/functions/)
- [Примеры функций](https://github.com/yandex-cloud/serverless-functions-examples)
- [Python SDK для Yandex Cloud](https://github.com/yandex-cloud/python-sdk)
