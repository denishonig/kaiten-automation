#!/usr/bin/env python3
"""
Вебхук-обработчик для автоматизации Kaiten.
Запускается как Flask сервер и обрабатывает события от Kaiten.
"""

import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from kaiten_automation import KaitenClient, CardStatusAutomation, load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для клиента и автоматизации
client = None
automation = None


def init_automation():
    """Инициализировать клиент и автоматизацию"""
    global client, automation
    try:
        config = load_config()
        client = KaitenClient(config['api_url'], config['api_token'])
        automation = CardStatusAutomation(client, config)
        logger.info("Автоматизация инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        raise


@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервиса"""
    return jsonify({'status': 'ok'}), 200


@app.route('/webhook/kaiten', methods=['POST'])
def kaiten_webhook():
    """
    Обработчик вебхука от Kaiten.
    Ожидает событие обновления карточки.
    """
    if not automation:
        return jsonify({'error': 'Automation not initialized'}), 500
    
    try:
        data = request.get_json()
        logger.info(f"Получен вебхук: {data}")
        
        # Структура события зависит от Kaiten API
        # Возможные варианты:
        # 1. { "event": "card.updated", "card": {...}, "card_id": 123 }
        # 2. { "card_id": 123, ... }
        
        card_id = None
        
        if 'card_id' in data:
            card_id = data['card_id']
        elif 'card' in data and isinstance(data['card'], dict):
            card_id = data['card'].get('id')
        elif 'card' in data and isinstance(data['card'], int):
            card_id = data['card']
        
        if not card_id:
            logger.warning("Вебхук не содержит card_id")
            return jsonify({'error': 'card_id not found'}), 400
        
        # Проверяем, что событие связано с обновлением карточки
        event_type = data.get('event', data.get('type', ''))
        if event_type and 'card' not in event_type.lower() and 'update' not in event_type.lower():
            logger.debug(f"Событие {event_type} не требует обработки")
            return jsonify({'status': 'ignored'}), 200
        
        # Обрабатываем карточку
        logger.info(f"Обработка карточки {card_id} из вебхука")
        success = automation.update_card_status(card_id)
        
        if success:
            return jsonify({'status': 'success', 'card_id': card_id}), 200
        else:
            return jsonify({'status': 'error', 'card_id': card_id}), 500
            
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/process/card/<int:card_id>', methods=['POST'])
def process_card_endpoint(card_id):
    """Ручной запуск обработки карточки через API"""
    if not automation:
        return jsonify({'error': 'Automation not initialized'}), 500
    
    try:
        success = automation.update_card_status(card_id)
        if success:
            return jsonify({'status': 'success', 'card_id': card_id}), 200
        else:
            return jsonify({'status': 'error', 'card_id': card_id}), 500
    except Exception as e:
        logger.error(f"Ошибка обработки карточки {card_id}: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    load_dotenv()
    init_automation()
    
    port = int(os.getenv('WEBHOOK_PORT', '5000'))
    host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    
    logger.info(f"Запуск вебхук-сервера на {host}:{port}")
    app.run(host=host, port=port, debug=False)
