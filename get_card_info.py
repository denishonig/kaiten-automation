#!/usr/bin/env python3
"""
Утилита для получения информации о карточке, пространствах и досках Kaiten.
Помогает найти ID полей, пространств и досок для настройки автоматизации.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from kaiten_automation import KaitenClient

# Импортируем новую функцию конфигурации из index.py
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from index import get_config_from_env
    USE_NEW_CONFIG = True
except ImportError:
    # Fallback на старую версию для обратной совместимости
    from kaiten_automation import load_config as get_config_from_env
    USE_NEW_CONFIG = False

def print_card_info(card):
    """Вывести информацию о карточке в читаемом формате"""
    print("=" * 60)
    print(f"Карточка ID: {card.get('id')}")
    print(f"Название: {card.get('title', 'N/A')}")
    print("=" * 60)
    
    # Выводим custom_properties
    if 'custom_properties' in card and card['custom_properties']:
        print("\n📋 Custom Properties:")
        print("-" * 60)
        for prop in card['custom_properties']:
            prop_id = prop.get('id') or prop.get('property_id', 'N/A')
            prop_name = prop.get('name', prop.get('title', 'N/A'))
            prop_type = prop.get('type', 'N/A')
            prop_value = prop.get('value', 'N/A')
            
            print(f"  ID: {prop_id}")
            print(f"  Название: {prop_name}")
            print(f"  Тип: {prop_type}")
            print(f"  Значение: {prop_value}")
            print()
    else:
        print("\n⚠️  Custom Properties не найдены")
    
    # Выводим properties (если есть)
    if 'properties' in card and card['properties']:
        print("\n📋 Properties:")
        print("-" * 60)
        for key, value in card['properties'].items():
            print(f"  {key}: {value}")
        print()
    
    # Выводим полный JSON для отладки
    print("\n📄 Полный JSON карточки:")
    print("-" * 60)
    print(json.dumps(card, indent=2, ensure_ascii=False))


def print_spaces(spaces):
    """Вывести список пространств"""
    print("=" * 60)
    print("📁 ПРОСТРАНСТВА")
    print("=" * 60)
    
    if not spaces:
        print("\n⚠️  Пространства не найдены")
        return
    
    print(f"\nНайдено пространств: {len(spaces)}\n")
    
    for space in spaces:
        space_id = space.get('id', 'N/A')
        space_name = space.get('name', space.get('title', 'N/A'))
        space_type = space.get('type', 'N/A')
        
        print(f"  ID: {space_id}")
        print(f"  Название: {space_name}")
        print(f"  Тип: {space_type}")
        print()
    
    print("=" * 60)
    print("💡 Для использования в конфигурации:")
    print("=" * 60)
    print("Добавьте в .env или переменные окружения:")
    print("  SPACE_ID=<id_пространства>")
    print("\nПример:")
    if spaces:
        first_space = spaces[0]
        print(f"  SPACE_ID={first_space.get('id')}")


def print_boards(boards, space_id=None):
    """Вывести список досок"""
    print("=" * 60)
    if space_id:
        print(f"📋 ДОСКИ (пространство ID: {space_id})")
    else:
        print("📋 ДОСКИ (все пространства)")
    print("=" * 60)
    
    if not boards:
        print("\n⚠️  Доски не найдены")
        return
    
    print(f"\nНайдено досок: {len(boards)}\n")
    
    for board in boards:
        board_id = board.get('id', 'N/A')
        board_name = board.get('name', board.get('title', 'N/A'))
        board_space_id = board.get('space_id', 'N/A')
        board_type = board.get('type', 'N/A')
        
        print(f"  ID: {board_id}")
        print(f"  Название: {board_name}")
        print(f"  Пространство ID: {board_space_id}")
        print(f"  Тип: {board_type}")
        print()
    
    print("=" * 60)
    print("💡 Для использования в конфигурации:")
    print("=" * 60)
    print("Добавьте в .env или переменные окружения:")
    print("  BOARD_ID=<id_доски>")
    print("\nПример:")
    if boards:
        first_board = boards[0]
        print(f"  BOARD_ID={first_board.get('id')}")


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(
        description='Утилита для получения информации из Kaiten',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python get_card_info.py 12345                    # Получить информацию о карточке
  python get_card_info.py --spaces                 # Получить список пространств
  python get_card_info.py --boards                 # Получить список всех досок
  python get_card_info.py --boards --space-id 10   # Получить доски конкретного пространства
        """
    )
    
    parser.add_argument('card_id', nargs='?', type=int, 
                       help='ID карточки для получения информации')
    parser.add_argument('--spaces', action='store_true',
                       help='Получить список пространств')
    parser.add_argument('--boards', action='store_true',
                       help='Получить список досок')
    parser.add_argument('--space-id', type=int,
                       help='ID пространства для фильтрации досок')
    
    args = parser.parse_args()
    
    # Если не указаны никакие параметры
    if not args.card_id and not args.spaces and not args.boards:
        parser.print_help()
        sys.exit(1)
    
    # Загружаем переменные окружения из .env файла
    load_dotenv()
    
    try:
        config = get_config_from_env()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}")
        print("\nУбедитесь, что файл .env настроен правильно.")
        print("Необходимые переменные:")
        print("  - KAITEN_API_URL")
        print("  - KAITEN_API_TOKEN")
        if USE_NEW_CONFIG:
            print("\nОпциональные переменные для автоматизации:")
            print("  - FIELD_AKTUALNOST, FIELD_NOVIZNA, FIELD_OPYT_SPIKERA")
            print("  - FIELD_HARIZMA, FIELD_PRIMENIMOST, FIELD_MASSOVOST")
            print("  - FIELD_INFLUENCER")
            print("  - FIELD_RATING_KACHESTVA, FIELD_TIP_KONTENTA")
            print("  - FIELD_UROVEN_SPIKERA, FIELD_OHVAT")
            print("  - BOARD_ID, SPACE_ID")
        sys.exit(1)
    
    client = KaitenClient(config['api_url'], config['api_token'])
    
    print(f"API URL: {config['api_url']}\n")
    
    # Обработка запроса списка пространств
    if args.spaces:
        print("Получение списка пространств...\n")
        spaces = client.get_spaces()
        if spaces is None:
            print("❌ Не удалось получить список пространств")
            sys.exit(1)
        print_spaces(spaces)
        return
    
    # Обработка запроса списка досок
    if args.boards:
        print("Получение списка досок...\n")
        boards = client.get_boards(space_id=args.space_id)
        if boards is None:
            print("❌ Не удалось получить список досок")
            sys.exit(1)
        print_boards(boards, space_id=args.space_id)
        return
    
    # Обработка запроса информации о карточке
    if args.card_id:
        print(f"Получение информации о карточке {args.card_id}...\n")
        card = client.get_card(args.card_id)
        
        if not card:
            print(f"❌ Не удалось получить карточку {args.card_id}")
            print("Проверьте:")
            print("  1. Правильность ID карточки")
            print("  2. Валидность API токена")
            print("  3. Права доступа к карточке")
            sys.exit(1)
        
        print_card_info(card)
        
        # Подсказка для настройки
        print("\n" + "=" * 60)
        print("💡 Подсказка для настройки автоматизации:")
        print("=" * 60)
        print("Скопируйте ID нужных полей из раздела 'Custom Properties'")
        print("и укажите их в файле .env или переменных окружения:")
        print("\nПоля критериев (входные данные):")
        print("  FIELD_AKTUALNOST=id_530178  # или просто 530178")
        print("  FIELD_NOVIZNA=id_530179")
        print("  FIELD_OPYT_SPIKERA=id_530180")
        print("  FIELD_HARIZMA=id_530181")
        print("  FIELD_PRIMENIMOST=id_530182")
        print("  FIELD_MASSOVOST=id_530183")
        print("  FIELD_INFLUENCER=id_530184")
        print("\nПоля результатов (выходные данные):")
        print("  FIELD_RATING_KACHESTVA=id_530178")
        print("  FIELD_TIP_KONTENTA=id_532084")
        print("  FIELD_UROVEN_SPIKERA=id_532086")
        print("  FIELD_OHVAT=id_532087")
        print("\n💡 Примечание: можно использовать формат 'id_530178' или просто '530178'")


if __name__ == '__main__':
    main()
