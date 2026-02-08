#!/usr/bin/env python3
"""
Автоматизация Kaiten: автоматическое обновление статуса карточки
на основе суммы числовых полей.

Логика:
- Сумма >= 13 → Gold
- Сумма >= 9 и < 13 → Silver
- Сумма < 9 → Bronze
"""

import os
import sys
import json
import logging
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


VALUES_SCORE = {
    # Актуальность
    '1 - Низкая': 1.0,
    '2 - Слабая': 2.0,
    '3 - Средняя': 3.0,
    '4 - Высокая': 4.0,
    '5 - Максимальная': 5.0,
    # Новизна
    '1 - Копипаста': 1.0,
    '2 - Баян': 2.0,
    '3 - Находка есть, прорыва нет': 3.0,
    '3 - Находки есть, прорыва нет': 3.0,  # вариант из API
    '4 - Уникальный опыт': 4.0,
    '5 - 100 % свежести': 5.0,
    '5 - 100% свежести': 5.0,  # вариант без пробела перед %
    # Применимость
    '1 - Вдохновиться': 1.0,
    '2 - Без рецепта': 2.0,
    '3 - Фрагментарно': 3.0,
    '4 - Toolkit': 4.0,
    '5 - Под ключ': 5.0,
    '5 -Под ключ': 5.0,  # вариант без пробела после дефиса (обратная совместимость)
    # Массовость (IT/ІТ — латиница и кириллица могут смешиваться в API)
    '1 - Для Профи': 1.0,
    '2 - Для своих': 2.0,
    '3 - Связующее звено': 3.0,
    '4 - Для всей команды': 4.0,
    '5 - Для всей IT кухни': 5.0,
    '5 - Для всей ІТ кухни': 5.0,   # кириллические І, Т (U+0406, U+0422)
    '5 - Для всей IТ кухни': 5.0,   # Latin I + Cyrillic Т
    '5 - Для всей ІT кухни': 5.0,   # Cyrillic І + Latin T
    # Опыт спикера
    '1 - Низкий': 1.0,  # Норм, что дублится, повтор для читаемости
    '2 - Ниже среднего': 2.0,
    '3 - Средний': 3.0,
    '4 - Высокий': 4.0,
    '5 - Экспертный': 5.0,
    # Харизма (шкала может отличаться от опыта спикера)
    '1 - Низкое качество': 1.0,
    '2 - Ниже среднего качества': 2.0,
    '3 - Среднее качество': 3.0,
    '4 - Выше среднего': 4.0,
    '5 - Высокое качество': 5.0,
    '1 - Нет записей или опыта': 1.0,  # вариант шкалы Харизмы в API
    '2 - Очень ограниченный опыт': 2.0,
    '4 - Хороший уровень': 4.0,
    '5 - Отлично': 5.0,  # вариант шкалы Харизмы в API
    # Инфлюенсер (Да/Нет)
    'Да': 1.0,
    'Нет': 0.0,
    'Yes': 1.0,
    'No': 0.0,

}


class KaitenClient:
    """Клиент для работы с Kaiten API"""
    
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        })
        self._select_values_cache: Dict[int, List[Dict[str, Any]]] = {}
    
    def get_card(self, card_id: int) -> Optional[Dict[str, Any]]:
        """Получить карточку по ID"""
        try:
            response = self.session.get(f'{self.api_url}/cards/{card_id}')
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Ответ API GET /cards/{card_id}: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении карточки {card_id}: {e}")
            return None
    
    def update_card(self, card_id: int, data: Dict[str, Any]) -> bool:
        """Обновить карточку"""
        try:
            logger.debug(f"Отправка запроса PATCH на {self.api_url}/cards/{card_id}")
            logger.debug(f"Данные: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            response = self.session.patch(
                f'{self.api_url}/cards/{card_id}',
                json=data
            )
            response.raise_for_status()
            
            # Логируем ответ для отладки
            try:
                response_data = response.json()
                logger.debug(f"Ответ сервера: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
            except:
                logger.debug(f"Ответ сервера (не JSON): {response.text[:500]}")
            
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при обновлении карточки {card_id}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Ответ сервера: {e.response.text}")
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                logger.error(f"Код статуса: {e.response.status_code}")
            return False
    
    def get_cards(self, board_id: Optional[int] = None, 
                  space_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получить список карточек"""
        try:
            params = {}
            if board_id:
                params['board_id'] = board_id
            if space_id:
                params['space_id'] = space_id
            
            response = self.session.get(f'{self.api_url}/cards', params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении списка карточек: {e}")
            return []
    
    def get_spaces(self) -> List[Dict[str, Any]]:
        """Получить список пространств"""
        try:
            response = self.session.get(f'{self.api_url}/spaces')
            response.raise_for_status()
            result = response.json()
            # API может возвращать объект с полем 'spaces' или массив напрямую
            if isinstance(result, dict) and 'spaces' in result:
                return result['spaces']
            elif isinstance(result, list):
                return result
            else:
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении списка пространств: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Ответ сервера: {e.response.text}")
            return []
    
    def get_boards(self, space_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получить список досок"""
        try:
            # Если указан space_id, используем вложенный эндпоинт
            if space_id:
                url = f'{self.api_url}/spaces/{space_id}/boards'
            else:
                # Пробуем получить все доски через общий эндпоинт
                url = f'{self.api_url}/boards'
            
            response = self.session.get(url)
            response.raise_for_status()
            result = response.json()
            # API может возвращать объект с полем 'boards' или массив напрямую
            if isinstance(result, dict) and 'boards' in result:
                return result['boards']
            elif isinstance(result, list):
                return result
            else:
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении списка досок: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Ответ сервера: {e.response.text}")
                logger.error(f"URL: {url}")
            return []
    
    def get_property(self, property_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о свойстве по ID"""
        try:
            response = self.session.get(f'{self.api_url}/properties/{property_id}')
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.debug(f"Не удалось получить информацию о свойстве {property_id}: {e}")
            return None
    
    def get_select_values(self, property_id: int) -> Optional[List[Dict[str, Any]]]:
        """Получить список значений для Select-поля по ID свойства (с кэшем на сессию)."""
        if property_id in self._select_values_cache:
            return self._select_values_cache[property_id]
        try:
            url = f'{self.api_url}/company/custom-properties/{property_id}/select-values'
            response = self.session.get(url)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Ответ API GET {url}: {json.dumps(result, ensure_ascii=False, indent=2)}")
            values = self._parse_select_values_response(result)
            # Кэшируем только непустые ответы, чтобы при временной ошибке API повторить запрос
            if values is not None and len(values) > 0:
                self._select_values_cache[property_id] = values
            return values
        except requests.exceptions.RequestException as e:
            logger.debug(f"Не удалось получить значения Select-поля {property_id}: {e}")
            return None

    def _parse_select_values_response(self, result: Any) -> Optional[List[Dict[str, Any]]]:
        """Извлечь список вариантов из ответа API (массив или объект с разными ключами)."""
        if isinstance(result, list):
            return result if result else []
        if isinstance(result, dict):
            for key in ('values', 'data', 'select_values', 'items', 'results', 'options', 'choices'):
                if key in result and isinstance(result[key], list):
                    return result[key]
            for v in result.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    first = v[0]
                    if any(k in first for k in ('id', 'option_id', 'value_id', 'select_value_id')):
                        return v
        return []


class CardStatusAutomation:
    """Автоматизация обновления статуса карточки"""
    
    def __init__(self, client: KaitenClient, config: Dict[str, Any]):
        self.client = client
        self.numeric_field_ids = config['numeric_field_ids']
        self.status_field_id = config['status_field_id']
        self.status_gold = config.get('status_gold', 'Gold')
        self.status_silver = config.get('status_silver', 'Silver')
        self.status_bronze = config.get('status_bronze', 'Bronze')
        self.threshold_gold = config.get('threshold_gold', 13)
        self.threshold_silver = config.get('threshold_silver', 9)
    
    def _resolve_select_value(self, field_id: str, raw_list: List[Any]) -> Optional[str]:
        """
        Для поля типа select в карточке хранится список id значений.
        По property_id запрашиваем select-values и возвращаем value по первому id из списка.
        """
        if not raw_list:
            return None
        try:
            property_id = int(str(field_id).replace('id_', '').strip())
        except (ValueError, TypeError):
            logger.debug(f"Не удалось извлечь property_id из field_id={field_id}")
            return None
        values = self.client.get_select_values(property_id)
        if not values:
            logger.debug(f"get_select_values({property_id}) вернул пустой результат")
            return None
        selected_id = raw_list[0]
        for item in values:
            item_id = item.get('id') or item.get('option_id') or item.get('value_id') or item.get('select_value_id')
            if item_id is None:
                continue
            item_value = item.get('value') or item.get('name') or item.get('label') or item.get('text') or item.get('title')
            # Сравниваем с учётом int/str (API может вернуть id как число или строку)
            try:
                if int(item_id) == int(selected_id):
                    return item_value
            except (TypeError, ValueError):
                if item_id == selected_id:
                    return item_value
        logger.debug(f"В select-values для property_id={property_id} не найден id={selected_id!r}")
        return None
    
    def _normalize_field_value_for_score(self, value: Any, field_id: str) -> Optional[str]:
        """Привести значение поля к строке для _value_to_float (поддержка select и старых типов)."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list) and value:
            return self._resolve_select_value(field_id, value)
        return None
    
    def extract_numeric_value(self, card: Dict[str, Any], field_id: str) -> float:
        """Извлечь числовое значение поля из карточки"""
        # Kaiten API может хранить поля в разных местах
        # Проверяем несколько возможных структур
        
        # Вариант 1: поля в custom_properties
        if 'custom_properties' in card:
            for prop in card['custom_properties']:
                if str(prop.get('id')) == str(field_id) or str(prop.get('property_id')) == str(field_id):
                    value = prop.get('value')
                    normalized = self._normalize_field_value_for_score(value, field_id)
                    if normalized is not None:
                        return self._value_to_float(normalized)
                    logger.debug(f"Не удалось нормализовать значение поля (select?): {value}")
                    return 0.0
        
        # Вариант 2: поля в properties
        if 'properties' in card:
            prop = card['properties'].get(field_id)
            if prop is not None:
                normalized = self._normalize_field_value_for_score(prop, field_id)
                if normalized is not None:
                    return self._value_to_float(normalized)
                logger.debug(f"Не удалось нормализовать значение из properties: {prop}")
                return 0.0
        
        # Вариант 3: ключ вида id_542109 в корне карточки (иногда properties лежит там)
        key = field_id if field_id in card else f"id_{field_id}" if f"id_{field_id}" in card else None
        if key is not None:
            field_value = card.get(key)
            if field_value is not None:
                normalized = self._normalize_field_value_for_score(field_value, field_id)
                if normalized is not None:
                    return self._value_to_float(normalized)
        
        logger.warning(f"Поле {field_id} не найдено в карточке {card.get('id')}")
        return 0.0

    def _value_to_float(self, value: str) -> float:
        if value in VALUES_SCORE:
            return float(VALUES_SCORE[value])
        # Нормализация смешанного IT/ІТ (кириллица → латиница) для поиска
        normalized = value.replace('\u0406', 'I').replace('\u0422', 'T')
        if normalized in VALUES_SCORE:
            return float(VALUES_SCORE[normalized])
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.error(f'Неизвестное значение поля {value}')
            return 0.0
    
    def calculate_sum(self, card: Dict[str, Any]) -> float:
        """Вычислить сумму числовых полей"""
        total = 0.0
        for field_id in self.numeric_field_ids:
            value = self.extract_numeric_value(card, field_id)
            total += value
            logger.debug(f"Поле {field_id}: {value}, сумма: {total}")
        return total
    
    def determine_status(self, total: float) -> str:
        """Определить статус на основе суммы"""
        if total >= self.threshold_gold:
            return self.status_gold
        elif total >= self.threshold_silver:
            return self.status_silver
        else:
            return self.status_bronze
    
    def get_current_status(self, card: Dict[str, Any]) -> Optional[str]:
        """Получить текущий статус карточки"""
        return self.extract_numeric_value(card, self.status_field_id)
    
    def update_card_status(self, card_id: int) -> bool:
        """Обновить статус карточки"""
        card = self.client.get_card(card_id)
        if not card:
            logger.error(f"Не удалось получить карточку {card_id}")
            return False
        
        total = self.calculate_sum(card)
        new_status = self.determine_status(total)
        
        logger.info(
            f"Карточка {card_id}: сумма = {total}, новый статус = {new_status}"
        )
        
        # Формируем данные для обновления
        # Структура зависит от API Kaiten, может потребоваться корректировка
        #update_data = {
        #    'custom_properties': [
        #        {
        #            'id': self.status_field_id,
        #            'value': new_status
        #        }
        #    ]
        #}
        
        # Альтернативный вариант структуры
        update_data = {
             'properties': {
                 self.status_field_id: new_status
             }
        }
        
        success = self.client.update_card(card_id, update_data)
        if success:
            logger.info(f"Статус карточки {card_id} успешно обновлен на {new_status}")
        else:
            logger.error(f"Не удалось обновить статус карточки {card_id}")
        
        return success
    
    def process_card(self, card: Dict[str, Any]) -> bool:
        """Обработать карточку (проверить и обновить статус при необходимости)"""
        card_id = card.get('id')
        if not card_id:
            logger.warning("Карточка без ID пропущена")
            return False
        
        total = self.calculate_sum(card)
        new_status = self.determine_status(total)
        
        # Получаем текущий статус
        current_status = None
        if 'custom_properties' in card:
            for prop in card['custom_properties']:
                if (prop.get('id') == self.status_field_id or 
                    prop.get('property_id') == self.status_field_id):
                    current_status = prop.get('value')
                    break
        
        # Проверяем, нужно ли обновлять
        if current_status == new_status:
            logger.debug(f"Карточка {card_id}: статус уже {new_status}, обновление не требуется")
            return True
        
        logger.info(
            f"Карточка {card_id}: сумма = {total}, "
            f"текущий статус = {current_status}, новый статус = {new_status}"
        )
        
        return self.update_card_status(card_id)


def load_config() -> Dict[str, Any]:
    """Загрузить конфигурацию из переменных окружения"""
    load_dotenv()
    
    api_url = os.getenv('KAITEN_API_URL')
    api_token = os.getenv('KAITEN_API_TOKEN')
    
    if not api_url or not api_token:
        raise ValueError(
            "Необходимо указать KAITEN_API_URL и KAITEN_API_TOKEN в .env файле"
        )
    
    numeric_field_ids_str = os.getenv('NUMERIC_FIELD_IDS', '')
    if not numeric_field_ids_str:
        raise ValueError("Необходимо указать NUMERIC_FIELD_IDS в .env файле")
    
    numeric_field_ids = [fid.strip() for fid in numeric_field_ids_str.split(',')]
    
    status_field_id = os.getenv('STATUS_FIELD_ID')
    if not status_field_id:
        raise ValueError("Необходимо указать STATUS_FIELD_ID в .env файле")
    
    board_id = os.getenv('BOARD_ID')
    space_id = os.getenv('SPACE_ID')
    
    return {
        'api_url': api_url,
        'api_token': api_token,
        'numeric_field_ids': numeric_field_ids,
        'status_field_id': status_field_id,
        'status_gold': os.getenv('STATUS_GOLD', 'Gold'),
        'status_silver': os.getenv('STATUS_SILVER', 'Silver'),
        'status_bronze': os.getenv('STATUS_BRONZE', 'Bronze'),
        'threshold_gold': int(os.getenv('THRESHOLD_GOLD', '13')),
        'threshold_silver': int(os.getenv('THRESHOLD_SILVER', '9')),
        'board_id': int(board_id) if board_id else None,
        'space_id': int(space_id) if space_id else None,
    }


def main():
    """Основная функция для запуска автоматизации"""
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        sys.exit(1)
    
    client = KaitenClient(config['api_url'], config['api_token'])
    automation = CardStatusAutomation(client, config)
    
    # Если передан ID карточки как аргумент командной строки
    if len(sys.argv) > 1:
        try:
            card_id = int(sys.argv[1])
            logger.info(f"Обработка карточки {card_id}")
            success = automation.update_card_status(card_id)
            sys.exit(0 if success else 1)
        except ValueError:
            logger.error(f"Неверный ID карточки: {sys.argv[1]}")
            sys.exit(1)
    
    # Иначе обрабатываем все карточки на доске/в пространстве
    logger.info("Получение списка карточек...")
    cards = client.get_cards(
        board_id=config.get('board_id'),
        space_id=config.get('space_id')
    )
    
    if not cards:
        logger.warning("Карточки не найдены")
        return
    
    logger.info(f"Найдено {len(cards)} карточек. Начинаю обработку...")
    
    success_count = 0
    error_count = 0
    
    for card in cards:
        try:
            if automation.process_card(card):
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Ошибка при обработке карточки {card.get('id')}: {e}")
            error_count += 1
    
    logger.info(
        f"Обработка завершена: успешно {success_count}, ошибок {error_count}"
    )


if __name__ == '__main__':
    main()
