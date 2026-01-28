#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы автоматизации Kaiten.
Позволяет протестировать логику без реальных запросов к API.
"""

import sys
from kaiten_automation import CardStatusAutomation, KaitenClient


class MockKaitenClient:
    """Мок-клиент для тестирования"""
    
    def __init__(self):
        self.cards = {}
    
    def get_card(self, card_id: int):
        return self.cards.get(card_id)
    
    def update_card(self, card_id: int, data: dict):
        if card_id in self.cards:
            # Обновляем карточку
            if 'custom_properties' in data:
                for prop in data['custom_properties']:
                    prop_id = prop.get('id')
                    prop_value = prop.get('value')
                    # Обновляем свойство в карточке
                    for existing_prop in self.cards[card_id].get('custom_properties', []):
                        if existing_prop.get('id') == prop_id:
                            existing_prop['value'] = prop_value
                            break
            print(f"✓ Карточка {card_id} обновлена: {data}")
            return True
        return False


def create_test_card(card_id: int, field1: float, field2: float, field3: float, 
                     field1_id: str, field2_id: str, field3_id: str,
                     status_field_id: str, current_status: str = None):
    """Создать тестовую карточку"""
    return {
        'id': card_id,
        'custom_properties': [
            {'id': field1_id, 'value': str(field1)},
            {'id': field2_id, 'value': str(field2)},
            {'id': field3_id, 'value': str(field3)},
            {'id': status_field_id, 'value': current_status or 'Unknown'}
        ]
    }


def test_status_logic():
    """Тестирование логики определения статуса"""
    print("=" * 60)
    print("Тестирование логики определения статуса")
    print("=" * 60)
    
    # Настройки теста
    field1_id = 'field_1'
    field2_id = 'field_2'
    field3_id = 'field_3'
    status_field_id = 'status_field'
    
    config = {
        'numeric_field_ids': [field1_id, field2_id, field3_id],
        'status_field_id': status_field_id,
        'status_gold': 'Gold',
        'status_silver': 'Silver',
        'status_bronze': 'Bronze',
        'threshold_gold': 13,
        'threshold_silver': 9,
    }
    
    client = MockKaitenClient()
    automation = CardStatusAutomation(client, config)
    
    # Тестовые случаи
    test_cases = [
        # (card_id, field1, field2, field3, expected_status, description)
        (1, 5, 5, 5, 'Gold', 'Сумма = 15 (>= 13) → Gold'),
        (2, 4, 4, 4, 'Silver', 'Сумма = 12 (>= 9 и < 13) → Silver'),
        (3, 3, 3, 2, 'Bronze', 'Сумма = 8 (< 9) → Bronze'),
        (4, 4.5, 4.5, 4.5, 'Silver', 'Сумма = 13.5 (>= 13) → Gold'),
        (5, 3, 3, 3, 'Bronze', 'Сумма = 9 (>= 9 и < 13) → Silver'),
        (6, 0, 0, 0, 'Bronze', 'Сумма = 0 (< 9) → Bronze'),
        (7, 13, 0, 0, 'Gold', 'Сумма = 13 (>= 13) → Gold'),
        (8, 9, 0, 0, 'Silver', 'Сумма = 9 (>= 9 и < 13) → Silver'),
    ]
    
    passed = 0
    failed = 0
    
    for card_id, f1, f2, f3, expected, desc in test_cases:
        card = create_test_card(
            card_id, f1, f2, f3,
            field1_id, field2_id, field3_id,
            status_field_id
        )
        client.cards[card_id] = card
        
        total = automation.calculate_sum(card)
        actual_status = automation.determine_status(total)
        
        status_icon = "✓" if actual_status == expected else "✗"
        print(f"{status_icon} Тест {card_id}: {desc}")
        print(f"   Поля: [{f1}, {f2}, {f3}], Сумма: {total}, "
              f"Ожидается: {expected}, Получено: {actual_status}")
        
        if actual_status == expected:
            passed += 1
        else:
            failed += 1
            print(f"   ❌ ОШИБКА: ожидалось {expected}, получено {actual_status}")
        print()
    
    print("=" * 60)
    print(f"Результаты: ✓ {passed} пройдено, ✗ {failed} провалено")
    print("=" * 60)
    
    return failed == 0


def test_card_processing():
    """Тестирование обработки карточек"""
    print("\n" + "=" * 60)
    print("Тестирование обработки карточек")
    print("=" * 60)
    
    field1_id = 'field_1'
    field2_id = 'field_2'
    field3_id = 'field_3'
    status_field_id = 'status_field'
    
    config = {
        'numeric_field_ids': [field1_id, field2_id, field3_id],
        'status_field_id': status_field_id,
        'status_gold': 'Gold',
        'status_silver': 'Silver',
        'status_bronze': 'Bronze',
        'threshold_gold': 13,
        'threshold_silver': 9,
    }
    
    client = MockKaitenClient()
    automation = CardStatusAutomation(client, config)
    
    # Создаем тестовые карточки
    card1 = create_test_card(1, 5, 5, 5, field1_id, field2_id, field3_id, 
                             status_field_id, 'Unknown')
    card2 = create_test_card(2, 3, 3, 2, field1_id, field2_id, field3_id,
                             status_field_id, 'Gold')  # Неправильный статус
    
    client.cards[1] = card1
    client.cards[2] = card2
    
    print("\nОбработка карточки 1 (сумма = 15, текущий статус = Unknown):")
    result1 = automation.process_card(card1)
    print(f"Результат: {'✓ Успешно' if result1 else '✗ Ошибка'}")
    
    print("\nОбработка карточки 2 (сумма = 8, текущий статус = Gold):")
    result2 = automation.process_card(card2)
    print(f"Результат: {'✓ Успешно' if result2 else '✗ Ошибка'}")
    
    # Проверяем, что статусы обновились
    print(f"\nСтатус карточки 1 после обработки: {card1['custom_properties'][3]['value']}")
    print(f"Статус карточки 2 после обработки: {card2['custom_properties'][3]['value']}")
    
    return result1 and result2


if __name__ == '__main__':
    print("Запуск тестов автоматизации Kaiten\n")
    
    test1_passed = test_status_logic()
    test2_passed = test_card_processing()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("✓ Все тесты пройдены успешно!")
        sys.exit(0)
    else:
        print("✗ Некоторые тесты провалены")
        sys.exit(1)
