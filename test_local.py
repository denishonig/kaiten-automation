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
        print(f"Загрузка переменных окружения из {env_file}")
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
    print("⚠️  KAITEN_API_URL не задан, используйте .env файл или установите переменную окружения")
if 'KAITEN_API_TOKEN' not in os.environ:
    print("⚠️  KAITEN_API_TOKEN не задан, используйте .env файл или установите переменную окружения")

def test_http_trigger():
    """Тестирование HTTP-триггера"""
    print("=" * 80)
    print("ТЕСТ HTTP-ТРИГГЕРА")
    print("=" * 80)
    
    # Загружаем тестовый JSON из файла
    test_json_path = os.path.join(os.path.dirname(__file__), 'parsed_webhook.json')
    if os.path.exists(test_json_path):
        print(f"Использование тестовых данных из {test_json_path}")
        with open(test_json_path, 'r', encoding='utf-8') as f:
            body_data = json.load(f)
        body_str = json.dumps(body_data, ensure_ascii=False)
    else:
        # Используем простой тестовый JSON
        print("Использование простого тестового JSON")
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
        print("\nВызов handler...")
        result = handler(event, context)
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТ:")
        print("=" * 80)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
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
        print("\nВызов handler...")
        result = handler(event, context)
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТ:")
        print("=" * 80)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Тестирование Yandex Cloud Functions локально')
    parser.add_argument('--type', choices=['http', 'timer', 'both'], default='http',
                       help='Тип триггера для тестирования (по умолчанию: http)')
    
    args = parser.parse_args()
    
    if args.type == 'http' or args.type == 'both':
        test_http_trigger()
        if args.type == 'both':
            print("\n\n")
    
    if args.type == 'timer' or args.type == 'both':
        test_timer_trigger()
