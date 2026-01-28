#!/usr/bin/env python3
"""
CLI-утилита для запуска автоматизации вычисления параметров комиссии.
Можно использовать локально для обработки карточек.
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv
from kaiten_automation import KaitenClient

# Импортируем классы из index.py для новой версии автоматизации
try:
    # Пытаемся импортировать из index.py
    sys.path.insert(0, os.path.dirname(__file__))
    from index import ConferenceProposalEvaluator, get_config_from_env
    USE_NEW_VERSION = True
except ImportError as e:
    # Если не получилось, выводим ошибку
    print(f"❌ Ошибка импорта: {e}")
    print("Убедитесь, что файл index.py находится в той же директории.")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_single_card(card_id: int, client: KaitenClient, config: dict):
    """Обработать одну карточку"""
    evaluator = ConferenceProposalEvaluator(client, config)
    success = evaluator.update_card_parameters(card_id)
    
    if success:
        print(f"✅ Карточка {card_id} успешно обработана")
        return 0
    else:
        print(f"❌ Ошибка при обработке карточки {card_id}")
        return 1


def process_all_cards(client: KaitenClient, config: dict):
    """Обработать все карточки"""
    board_id = config.get('board_id')
    space_id = config.get('space_id')
    
    print(f"Получение списка карточек...")
    if board_id:
        print(f"  Фильтр: доска ID {board_id}")
    if space_id:
        print(f"  Фильтр: пространство ID {space_id}")
    
    cards = client.get_cards(board_id=board_id, space_id=space_id)
    
    if not cards:
        print("⚠️  Карточки не найдены")
        return 0
    
    print(f"\nНайдено {len(cards)} карточек. Начинаю обработку...\n")
    
    evaluator = ConferenceProposalEvaluator(client, config)
    
    success_count = 0
    error_count = 0
    
    for i, card in enumerate(cards, 1):
        card_id = card.get('id')
        card_title = card.get('title', 'N/A')
        print(f"[{i}/{len(cards)}] Обработка карточки {card_id}: {card_title[:50]}...")
        
        try:
            if evaluator.process_card(card):
                success_count += 1
                print(f"  ✅ Успешно")
            else:
                error_count += 1
                print(f"  ❌ Ошибка")
        except Exception as e:
            error_count += 1
            print(f"  ❌ Ошибка: {e}")
    
    print(f"\n{'='*60}")
    print(f"Обработка завершена:")
    print(f"  ✅ Успешно: {success_count}")
    print(f"  ❌ Ошибок: {error_count}")
    print(f"{'='*60}")
    
    return 0 if error_count == 0 else 1


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(
        description='Запуск автоматизации вычисления параметров для комиссии Kaiten',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Обработать одну карточку
  python run_automation.py --card-id 12345
  
  # Обработать все карточки на доске
  python run_automation.py --board-id 123
  
  # Обработать все карточки в пространстве
  python run_automation.py --space-id 456
  
  # Обработать все карточки (используя настройки из .env)
  python run_automation.py --all
        """
    )
    
    parser.add_argument('--card-id', type=int,
                       help='ID карточки для обработки')
    parser.add_argument('--board-id', type=int,
                       help='ID доски для обработки всех карточек')
    parser.add_argument('--space-id', type=int,
                       help='ID пространства для обработки всех карточек')
    parser.add_argument('--all', action='store_true',
                       help='Обработать все карточки (используя BOARD_ID/SPACE_ID из .env)')
    parser.add_argument('--config', type=str, default='.env',
                       help='Путь к файлу конфигурации (по умолчанию: .env)')
    
    args = parser.parse_args()
    
    # Загружаем конфигурацию
    if os.path.exists(args.config):
        load_dotenv(args.config)
    else:
        load_dotenv()
    
    try:
        config = get_config_from_env()
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nУбедитесь, что файл .env настроен правильно.")
        print("См. config.example.env для примера конфигурации.")
        sys.exit(1)
    
    client = KaitenClient(config['api_url'], config['api_token'])
    
    # Обработка одной карточки
    if args.card_id:
        return process_single_card(args.card_id, client, config)
    
    # Обработка всех карточек с фильтрацией
    if args.board_id:
        config['board_id'] = args.board_id
        config['space_id'] = None
        return process_all_cards(client, config)
    
    if args.space_id:
        config['space_id'] = args.space_id
        config['board_id'] = None
        return process_all_cards(client, config)
    
    # Обработка всех карточек (из конфигурации)
    if args.all:
        return process_all_cards(client, config)
    
    # Если ничего не указано, показываем справку
    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
