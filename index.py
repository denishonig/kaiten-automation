#!/usr/bin/env python3
"""
Yandex Cloud Functions handler для автоматизации Kaiten.
Расширенная версия: вычисление параметров для комиссии на основе критериев оценки докладов.
"""

import json
import logging
import os
import sys
import base64
import time
from typing import Dict, Any, List, Optional
import requests

# Настройка логирования для Cloud Functions (должно быть до использования logger)
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Флаг для отладочного вывода полного event объекта (можно включить через DEBUG_FULL_EVENT=true)
DEBUG_FULL_EVENT = os.environ.get('DEBUG_FULL_EVENT', 'false').lower() in ('true', '1', 'yes')

# Настройки retry для обработки 429 ошибок
MAX_RETRIES_429 = int(os.environ.get('MAX_RETRIES_429', '3'))  # Максимальное количество повторов при 429
INITIAL_RETRY_DELAY = float(os.environ.get('INITIAL_RETRY_DELAY', '1.0'))  # Начальная задержка в секундах
# Добавляем текущую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(__file__))

# Пытаемся импортировать из модуля, если не получается - используем встроенные классы
try:
    from kaiten_automation import KaitenClient
except ImportError:
    # Если модуль не найден, используем встроенные классы
    logger.info("Модуль kaiten_automation не найден, используются встроенные классы")
    
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
        
        def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
            """
            Выполняет HTTP запрос с retry при получении 429 ошибки.
            
            Args:
                method: HTTP метод ('get', 'post', 'patch', etc.)
                url: URL для запроса
                **kwargs: Дополнительные аргументы для requests
            
            Returns:
                Response объект
            
            Raises:
                requests.exceptions.HTTPError: Если после всех повторов все еще ошибка
            """
            last_exception = None
            
            for attempt in range(MAX_RETRIES_429 + 1):
                try:
                    response = self.session.request(method, url, **kwargs)
                    
                    # Проверяем статус-код перед raise_for_status
                    if response.status_code == 429:
                        if attempt < MAX_RETRIES_429:
                            # Вычисляем задержку с exponential backoff
                            delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                            
                            # Проверяем, есть ли в заголовках Retry-After
                            retry_after = response.headers.get('Retry-After')
                            if retry_after:
                                try:
                                    delay = float(retry_after)
                                    logger.info(f"Получен Retry-After: {delay} секунд")
                                except (ValueError, TypeError):
                                    pass
                            
                            logger.warning(
                                f"Получен 429 (Too Many Requests) при {method.upper()} {url}, "
                                f"попытка {attempt + 1}/{MAX_RETRIES_429 + 1}. "
                                f"Повтор через {delay:.2f} секунд..."
                            )
                            time.sleep(delay)
                            last_exception = requests.exceptions.HTTPError(
                                f"429 Too Many Requests (attempt {attempt + 1})",
                                response=response
                            )
                            continue
                        else:
                            logger.error(
                                f"Превышено максимальное количество повторов ({MAX_RETRIES_429 + 1}) "
                                f"для 429 ошибки при {method.upper()} {url}"
                            )
                            response.raise_for_status()
                    
                    # Для других статус-кодов вызываем raise_for_status как обычно
                    response.raise_for_status()
                    return response
                    
                except requests.exceptions.HTTPError as e:
                    # Если это не 429 или это последняя попытка, пробрасываем ошибку
                    if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                        if attempt < MAX_RETRIES_429:
                            # Это уже обработано выше, но на всякий случай
                            delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                            retry_after = e.response.headers.get('Retry-After')
                            if retry_after:
                                try:
                                    delay = float(retry_after)
                                except (ValueError, TypeError):
                                    pass
                            logger.warning(
                                f"Получен 429 (Too Many Requests), попытка {attempt + 1}/{MAX_RETRIES_429 + 1}. "
                                f"Повтор через {delay:.2f} секунд..."
                            )
                            time.sleep(delay)
                            last_exception = e
                            continue
                    raise
                except requests.exceptions.RequestException as e:
                    # Другие ошибки запросов пробрасываем без retry
                    raise
            
            # Если дошли сюда, значит все попытки исчерпаны
            if last_exception:
                raise last_exception
            raise requests.exceptions.RequestException("Не удалось выполнить запрос после всех повторов")
        
        def get_card(self, card_id: int) -> Optional[Dict[str, Any]]:
            """Получить карточку по ID"""
            try:
                response = self._make_request_with_retry('get', f'{self.api_url}/cards/{card_id}')
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при получении карточки {card_id}: {e}")
                return None
        
        def update_card(self, card_id: int, data: Dict[str, Any]) -> bool:
            """Обновить карточку"""
            try:
                logger.debug(f"Отправка PATCH запроса на {self.api_url}/cards/{card_id}")
                logger.debug(f"Данные запроса: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                response = self._make_request_with_retry(
                    'patch',
                    f'{self.api_url}/cards/{card_id}',
                    json=data
                )
                
                logger.info(f"Статус ответа API: {response.status_code}")
                
                # Логируем ответ для отладки
                try:
                    response_data = response.json()
                    logger.info(f"Ответ сервера: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                    # Также логируем custom_properties из ответа, если они есть
                    if 'custom_properties' in response_data:
                        logger.info("Custom properties в ответе:")
                        for prop in response_data['custom_properties']:
                            logger.info(f"  - id={prop.get('id')}, property_id={prop.get('property_id')}, value={prop.get('value')}")
                except:
                    logger.info(f"Ответ сервера (не JSON): {response.text[:500]}")
                
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
                
                response = self._make_request_with_retry('get', f'{self.api_url}/cards', params=params)
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при получении списка карточек: {e}")
                return []
        
        def get_property(self, property_id: int) -> Optional[Dict[str, Any]]:
            """Получить информацию о свойстве по ID"""
            try:
                response = self._make_request_with_retry('get', f'{self.api_url}/properties/{property_id}')
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.debug(f"Не удалось получить информацию о свойстве {property_id}: {e}")
                return None
        
        def get_select_values(self, property_id: int) -> Optional[List[Dict[str, Any]]]:
            """Получить список значений для Select-поля по ID свойства"""
            try:
                response = self._make_request_with_retry('get', f'{self.api_url}/company/custom-properties/{property_id}/select-values')
                result = response.json()
                # API может возвращать массив напрямую или объект с полем
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict) and 'values' in result:
                    return result['values']
                else:
                    return []
            except requests.exceptions.RequestException as e:
                logger.debug(f"Не удалось получить значения Select-поля {property_id}: {e}")
                return None


class ConferenceProposalEvaluator:
    """
    Класс для вычисления параметров комиссии на основе критериев оценки докладов.
    
    Вычисляет:
    1. Рейтинг Качества (Золото/Серебро/Бронза) - на основе: Актуальность + Новизна + Опыт спикера
    2. Тип Контента - на основе: Применимость
    3. Уровень спикера - на основе: Харизма + IT-инфлюенсер
    4. Охват - на основе: Массовость
    """
    
    def __init__(self, client: KaitenClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        
        # ID полей критериев (входные данные)
        self.field_aktualnost = config.get('field_aktualnost')  # Актуальность
        self.field_novizna = config.get('field_novizna')  # Новизна
        self.field_opyt_spikera = config.get('field_opyt_spikera')  # Опыт спикера
        self.field_primenimost = config.get('field_primenimost')  # Применимость
        self.field_harizma = config.get('field_harizma')  # Харизма
        self.field_influencer = config.get('field_influencer')  # IT-инфлюенсер
        self.field_massovost = config.get('field_massovost')  # Массовость
        
        # ID полей результатов (выходные данные)
        self.field_rating_kachestva = config.get('field_rating_kachestva')  # Рейтинг Качества
        self.field_tip_kontenta = config.get('field_tip_kontenta')  # Тип Контента
        self.field_uroven_spikera = config.get('field_uroven_spikera')  # Уровень спикера
        self.field_ohvat = config.get('field_ohvat')  # Охват
    
    def extract_field_value(self, card: Dict[str, Any], field_id: str) -> Optional[Any]:
        """Извлечь значение поля из карточки (поддерживает разные типы)"""
        if not field_id:
            return None
        
        logger.debug(f"Извлечение значения поля {field_id}")
        
        # Вариант 1: поля в custom_properties
        if 'custom_properties' in card:
            for prop in card['custom_properties']:
                prop_id = prop.get('id')
                property_id = prop.get('property_id')
                prop_name = prop.get('name')
                
                # Проверяем разные варианты совпадения
                if (str(prop_id) == str(field_id) or 
                    str(property_id) == str(field_id) or
                    prop_name == field_id):
                    value = prop.get('value')
                    logger.debug(f"  ✓ Найдено в custom_properties: value={value}")
                    return value
        
        # Вариант 2: поля в properties
        if 'properties' in card:
            if field_id in card['properties']:
                value = card['properties'][field_id]
                logger.debug(f"  ✓ Найдено в properties: value={value}")
                return value
        
        # Вариант 3: прямое обращение по ID
        if field_id in card:
            value = card[field_id]
            logger.debug(f"  ✓ Найдено напрямую: value={value}")
            return value
        
        logger.debug(f"  ✗ Поле {field_id} не найдено")
        return None
    
    def extract_numeric_value(self, card: Dict[str, Any], field_id: str) -> float:
        """Извлечь числовое значение поля"""
        value = self.extract_field_value(card, field_id)
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def extract_text_value(self, card: Dict[str, Any], field_id: str) -> Optional[str]:
        """Извлечь текстовое значение поля"""
        value = self.extract_field_value(card, field_id)
        if value is None:
            return None
        return str(value)
    
    def _find_property_info(self, card: Dict[str, Any], field_id: str) -> Optional[Dict[str, Any]]:
        """Найти полную информацию о поле в карточке"""
        logger.debug(f"Поиск информации о поле: '{field_id}' (тип: {type(field_id).__name__})")
        
        # Убираем префикс "id_" если он есть, для сравнения
        field_id_clean = field_id.replace('id_', '') if isinstance(field_id, str) and field_id.startswith('id_') else field_id
        
        if 'custom_properties' in card:
            logger.debug(f"  Всего custom_properties в карточке: {len(card['custom_properties'])}")
            for prop in card['custom_properties']:
                prop_id = prop.get('id')
                prop_property_id = prop.get('property_id')
                prop_name = prop.get('name')
                
                # Преобразуем ID в строки для сравнения
                prop_id_str = str(prop_id) if prop_id is not None else None
                prop_property_id_str = str(prop_property_id) if prop_property_id is not None else None
                
                logger.debug(f"  Проверка: id={prop_id} ({type(prop_id).__name__ if prop_id is not None else 'None'}), "
                           f"property_id={prop_property_id} ({type(prop_property_id).__name__ if prop_property_id is not None else 'None'}), "
                           f"name={prop_name}")
                
                # Проверяем разные варианты сравнения
                matches = (
                    prop_id == field_id or
                    prop_property_id == field_id or
                    prop_id_str == str(field_id) or
                    prop_property_id_str == str(field_id) or
                    prop_id_str == field_id_clean or
                    prop_property_id_str == field_id_clean or
                    prop_name == field_id or
                    (prop_id is not None and str(prop_id) == field_id_clean) or
                    (prop_property_id is not None and str(prop_property_id) == field_id_clean) or
                    (isinstance(prop_id, int) and str(prop_id) == str(field_id_clean)) or
                    (isinstance(prop_property_id, int) and str(prop_property_id) == str(field_id_clean))
                )
                
                if matches:
                    logger.debug(f"  ✓ Найдено совпадение для '{field_id}'!")
                    logger.debug(f"     Полная структура: {json.dumps(prop, ensure_ascii=False, indent=4)}")
                    return prop
        
        # Проверяем также properties (если есть)
        if 'properties' in card and card['properties']:
            logger.debug(f"  Проверяем properties...")
            field_id_clean = field_id.replace('id_', '') if isinstance(field_id, str) and field_id.startswith('id_') else field_id
            
            # Проверяем прямое совпадение ключа
            if field_id in card['properties'] or str(field_id_clean) in card['properties']:
                prop_value = card['properties'].get(field_id) or card['properties'].get(str(field_id_clean))
                logger.debug(f"  ✓ Найдено в properties: {field_id} = {prop_value}")
                # Возвращаем упрощенную структуру для properties
                # Для обновления через custom_properties нужно использовать property_id
                # Если поле в properties, то field_id_clean и есть property_id
                try:
                    property_id_numeric = int(field_id_clean)
                    property_id = property_id_numeric
                except (ValueError, TypeError):
                    property_id = field_id_clean
                
                return {
                    'id': field_id,
                    'property_id': property_id,  # Используем field_id_clean как property_id
                    'value': prop_value,
                    'type': 'unknown'  # Тип неизвестен для properties
                }
        
        logger.debug(f"  ✗ Поле '{field_id}' не найдено ни в custom_properties, ни в properties")
        logger.debug(f"  Доступные поля в карточке:")
        if 'custom_properties' in card:
            logger.debug(f"  Custom Properties:")
            for prop in card['custom_properties']:
                logger.debug(f"    - id: {prop.get('id')} ({type(prop.get('id')).__name__ if prop.get('id') is not None else 'None'}), "
                           f"property_id: {prop.get('property_id')} ({type(prop.get('property_id')).__name__ if prop.get('property_id') is not None else 'None'}), "
                           f"name: {prop.get('name')}")
        if 'properties' in card and card['properties']:
            logger.debug(f"  Properties:")
            for key, value in card['properties'].items():
                logger.debug(f"    - {key}: {value}")
        return None
    
    def _find_property_id(self, card: Dict[str, Any], field_id: str) -> Optional[str]:
        """Найти property_id для поля в карточке (для обратной совместимости)"""
        prop_info = self._find_property_info(card, field_id)
        if prop_info:
            return prop_info.get('property_id') or prop_info.get('id')
        return None
    
    def calculate_rating_kachestva(self, card: Dict[str, Any]) -> str:
        """
        Вычислить Рейтинг Качества на основе: Актуальность + Новизна + Опыт спикера
        
        Золото: Уникальный контент + Сильный спикер. "Must have" программы
        Серебро: Качественный, полезный доклад. Крепкая основа конференции
        Бронза: Нормальный доклад, возможен для резерва или закрытия специфической ниши
        """
        aktualnost = self.extract_numeric_value(card, self.field_aktualnost)
        novizna = self.extract_numeric_value(card, self.field_novizna)
        opyt = self.extract_numeric_value(card, self.field_opyt_spikera)
        
        total = aktualnost + novizna + opyt
        
        logger.debug(
            f"Рейтинг Качества: Актуальность={aktualnost}, Новизна={novizna}, "
            f"Опыт={opyt}, Сумма={total}"
        )
        
        # Логика определения рейтинга
        # Золото: высокие оценки по всем критериям (сумма >= 13 или все >= 4)
        # Серебро: хорошие оценки (сумма >= 9 или средние >= 3)
        # Бронза: остальные
        
        if total >= 13 or (aktualnost >= 4 and novizna >= 4 and opyt >= 4):
            return "Золото"
        elif total >= 9 or (aktualnost >= 3 and novizna >= 3 and opyt >= 3):
            return "Серебро"
        else:
            return "Бронза"
    
    def calculate_tip_kontenta(self, card: Dict[str, Any]) -> str:
        """
        Вычислить Тип Контента на основе: Применимость (числовое поле 1-5)
        
        Применимость:
        1 - Вдохновиться → Вдохновение/Обзор
        2 - Без рецепта → Вдохновение/Обзор
        3 - Фрагментарно → Практический кейс
        4 - Toolkit → Практический кейс
        5 - Под ключ → Хардкор (если Массовость <= 2) или Массовость (если Массовость > 2)
        """
        primenimost = self.extract_numeric_value(card, self.field_primenimost)
        massovost = self.extract_numeric_value(card, self.field_massovost)
        
        logger.debug(f"Тип Контента: Применимость={primenimost}, Массовость={massovost}")
        
        if primenimost == 0:
            return "Не определен"
        
        # Хардкор: Под ключ (5) + Массовость <= 2 (Для профи/Для своих)
        if primenimost == 5 and massovost <= 2:
            return "Хардкор"
        
        # Массовость: Под ключ (5) + Массовость > 2
        if primenimost == 5 and massovost > 2:
            return "Массовость"
        
        # Практический кейс: Toolkit (4) или Фрагментарно (3)
        if primenimost == 4 or primenimost == 3:
            return "Практический кейс"
        
        # Вдохновение/Обзор: Вдохновиться (1) или Без рецепта (2)
        if primenimost == 1 or primenimost == 2:
            return "Вдохновение/Обзор"
        
        return "Не определен"
    
    def calculate_uroven_spikera(self, card: Dict[str, Any]) -> str:
        """
        Вычислить Уровень спикера на основе: Харизма + IT-инфлюенсер
        
        Хедлайнер: Соберет полный зал на имя (Харизма 5 + Инфлюенсер)
        Хороший Спикер: Хорошо держит аудиторию (Харизма 4-5)
        Эксперт: Крутой контент, но подача может быть сухой (Харизма 1-3)
        """
        harizma = self.extract_numeric_value(card, self.field_harizma)
        influencer = self.extract_text_value(card, self.field_influencer)
        
        logger.debug(f"Уровень спикера: Харизма={harizma}, Инфлюенсер={influencer}")
        
        # Хедлайнер: Харизма 5 + Инфлюенсер
        if harizma >= 5 and influencer and influencer.lower() in ("да", "yes", "true", "1"):
            return "Хедлайнер"
        
        # Хороший Спикер: Харизма 4-5
        if harizma >= 4:
            return "Хороший Спикер"
        
        # Эксперт: Харизма 1-3
        if harizma >= 1:
            return "Эксперт"
        
        return "Не определен"
    
    def calculate_ohvat(self, card: Dict[str, Any]) -> str:
        """
        Вычислить Охват на основе: Массовость (числовое поле 1-5)
        
        Массовость:
        1 - Для профи → Ниша
        2 - Для своих → Ниша
        3 - Связующее звено → Кросс
        4 - Для всей команды → Для всех
        5 - Для всей IT-кухни → Для всех
        """
        massovost = self.extract_numeric_value(card, self.field_massovost)
        
        logger.debug(f"Охват: Массовость={massovost}")
        
        if massovost == 0:
            return "Не определен"
        
        # Для всех: Для всей команды (4) или Для всей IT-кухни (5)
        if massovost == 4 or massovost == 5:
            return "Для всех"
        
        # Кросс: Связующее звено (3)
        if massovost == 3:
            return "Кросс"
        
        # Ниша: Для профи (1) или Для своих (2)
        if massovost == 1 or massovost == 2:
            return "Ниша"
        
        return "Не определен"
    
    def calculate_all_parameters(self, card: Dict[str, Any]) -> Dict[str, str]:
        """Вычислить все параметры для комиссии"""
        return {
            'rating_kachestva': self.calculate_rating_kachestva(card),
            'tip_kontenta': self.calculate_tip_kontenta(card),
            'uroven_spikera': self.calculate_uroven_spikera(card),
            'ohvat': self.calculate_ohvat(card)
        }
    
    def update_card_parameters(self, card_id: int) -> bool:
        """Обновить все параметры в карточке"""
        card = self.client.get_card(card_id)
        if not card:
            logger.error(f"Не удалось получить карточку {card_id}")
            return False
        
        # Логируем структуру карточки для отладки
        logger.debug("=" * 60)
        logger.debug("СТРУКТУРА КАРТОЧКИ:")
        logger.debug(f"ID карточки: {card.get('id')}")
        logger.debug(f"Название: {card.get('title', 'N/A')}")
        
        if 'custom_properties' in card:
            logger.debug(f"\nCustom Properties ({len(card['custom_properties'])} полей):")
            for i, prop in enumerate(card['custom_properties'], 1):
                logger.debug(f"  {i}. id={prop.get('id')}, property_id={prop.get('property_id')}, "
                           f"name={prop.get('name')}, type={prop.get('type')}, value={prop.get('value')}")
        else:
            logger.debug("Custom Properties: отсутствуют")
        
        logger.debug("=" * 60)
        
        # Логируем структуру карточки для отладки
        logger.debug("=" * 60)
        logger.debug("СТРУКТУРА КАРТОЧКИ:")
        logger.debug(f"ID карточки: {card.get('id')}")
        logger.debug(f"Название: {card.get('title', 'N/A')}")
        
        if 'custom_properties' in card:
            logger.debug(f"\nCustom Properties ({len(card['custom_properties'])} полей):")
            for i, prop in enumerate(card['custom_properties'], 1):
                logger.debug(f"  {i}. id={prop.get('id')} ({type(prop.get('id')).__name__ if prop.get('id') is not None else 'None'}), "
                           f"property_id={prop.get('property_id')} ({type(prop.get('property_id')).__name__ if prop.get('property_id') is not None else 'None'}), "
                           f"name={prop.get('name')}, type={prop.get('type')}, value={prop.get('value')}")
        else:
            logger.debug("Custom Properties: отсутствуют")
        logger.debug("=" * 60)
        
        # Вычисляем все параметры
        parameters = self.calculate_all_parameters(card)
        
        logger.info(
            f"Карточка {card_id}: "
            f"Рейтинг={parameters['rating_kachestva']}, "
            f"Тип={parameters['tip_kontenta']}, "
            f"Уровень={parameters['uroven_spikera']}, "
            f"Охват={parameters['ohvat']}"
        )
        
        # Формируем данные для обновления
        # Kaiten API требует формат: properties: { "id_{property_id}": value }
        # Формат: 'id_{custom_property_id}: value'
        properties = {}
        
        # Кэш для значений Select-полей, чтобы не делать повторные запросы к API
        select_values_cache = {}
        
        fields_to_update = [
            (self.field_rating_kachestva, parameters['rating_kachestva']),
            (self.field_tip_kontenta, parameters['tip_kontenta']),
            (self.field_uroven_spikera, parameters['uroven_spikera']),
            (self.field_ohvat, parameters['ohvat'])
        ]
        
        for field_id, value in fields_to_update:
            if not field_id:
                continue
            
            # Ищем полную информацию о поле в текущей карточке
            prop_info = self._find_property_info(card, field_id)
            
            # Определяем property_id для использования в ключе "id_{property_id}"
            property_id = None
            
            prop_type = None
            if prop_info:
                # Используем property_id если есть, иначе id
                property_id = prop_info.get('property_id') or prop_info.get('id')
                prop_type = prop_info.get('type', 'unknown')
                
                logger.debug(f"Обновление поля {field_id} (property_id={property_id}, type={prop_type}): {value}")
                
                # Если property_id не определен из prop_info, пробуем получить из field_id
                if not property_id:
                    field_id_clean = field_id.replace('id_', '') if isinstance(field_id, str) and field_id.startswith('id_') else field_id
                    try:
                        property_id = int(field_id_clean)
                        logger.debug(f"  Используем property_id из field_id: {property_id}")
                    except (ValueError, TypeError):
                        property_id = field_id_clean
                        logger.debug(f"  Используем property_id из field_id (строковый): {property_id}")
                
                # Для всех полей с property_id пытаемся получить значения через API
                # (так как все поля результатов - это Select-поля)
                if property_id:
                    logger.debug(f"  Получаем значения через API для property_id={property_id}...")
                    # Проверяем кэш перед запросом к API
                    if property_id in select_values_cache:
                        select_values = select_values_cache[property_id]
                        logger.debug(f"  Используем значения из кэша для property_id={property_id}")
                    else:
                        # Получаем значения Select-поля через API
                        select_values = self.client.get_select_values(property_id)
                        # Сохраняем в кэш
                        if select_values is not None:
                            select_values_cache[property_id] = select_values
                        # Небольшая задержка между запросами, чтобы избежать 429 ошибок
                        import time
                        time.sleep(0.2)
                    if select_values:
                        logger.debug(f"  Получены значения Select-поля: {len(select_values)} вариантов")
                        # Ищем ID варианта по значению (Value)
                        found_option_id = None
                        for option in select_values:
                            if isinstance(option, dict):
                                # Проверяем разные возможные поля для значения
                                option_value = option.get('value') or option.get('Value') or option.get('name') or option.get('label') or option.get('title')
                                option_id = option.get('id') or option.get('Id') or option.get('ID')
                                
                                # Сравниваем значения (без учета регистра и пробелов)
                                if option_value and str(option_value).strip().lower() == str(value).strip().lower():
                                    if option_id:
                                        logger.debug(f"  Найден ID варианта: {option_id} для значения '{value}' (найдено: '{option_value}')")
                                        found_option_id = int(option_id) if isinstance(option_id, (int, str)) and str(option_id).isdigit() else option_id
                                        break
                                # Также проверяем точное совпадение
                                elif option_value == value:
                                    if option_id:
                                        logger.debug(f"  Найден ID варианта (точное совпадение): {option_id} для значения '{value}'")
                                        found_option_id = int(option_id) if isinstance(option_id, (int, str)) and str(option_id).isdigit() else option_id
                                        break
                        
                        # Если нашли ID варианта, используем его
                        if found_option_id is not None:
                            value = found_option_id
                            prop_type = 'select'
                        else:
                            # Если не нашли ID варианта, выводим предупреждение
                            logger.warning(f"  ⚠️  Не найден ID варианта для значения '{value}' в Select-поле {property_id}")
                            # Но все равно предполагаем, что это Select-поле
                            prop_type = 'select'
                    else:
                        logger.warning(f"  ⚠️  Не удалось получить значения Select-поля {property_id} через API")
                        # Предполагаем Select по умолчанию
                        prop_type = 'select'
                else:
                    # Если property_id все еще не определен, предполагаем Select
                    prop_type = 'select'
                    logger.warning(f"  ⚠️  Не удалось определить property_id для поля {field_id}, предполагаем Select")
            else:
                logger.warning(f"⚠️  Поле {field_id} не найдено в карточке! Пробуем получить информацию о свойстве через API.")
                
                # Если поле не найдено в карточке, используем field_id напрямую
                # Убираем префикс "id_" если он есть
                field_id_clean = field_id.replace('id_', '') if isinstance(field_id, str) and field_id.startswith('id_') else field_id
                
                # Преобразуем в число, если возможно (property_id обычно числовой)
                try:
                    property_id = int(field_id_clean)
                    logger.debug(f"  Используем property_id из field_id (числовой): {property_id}")
                    
                    # Проверяем кэш перед запросом к API
                    if property_id in select_values_cache:
                        select_values = select_values_cache[property_id]
                        logger.debug(f"  Используем значения из кэша для property_id={property_id}")
                    else:
                        # Пробуем получить значения Select-поля через API
                        select_values = self.client.get_select_values(property_id)
                        # Сохраняем в кэш
                        if select_values is not None:
                            select_values_cache[property_id] = select_values
                        # Небольшая задержка между запросами, чтобы избежать 429 ошибок
                        import time
                        time.sleep(0.2)
                    
                    if select_values:
                        logger.debug(f"  Получены значения Select-поля: {len(select_values)} вариантов")
                        # Ищем ID варианта по значению (Value)
                        for option in select_values:
                            if isinstance(option, dict):
                                # Проверяем разные возможные поля для значения
                                option_value = option.get('value') or option.get('Value') or option.get('name') or option.get('label') or option.get('title')
                                option_id = option.get('id') or option.get('Id') or option.get('ID')
                                
                                # Сравниваем значения (без учета регистра и пробелов)
                                if option_value and str(option_value).strip().lower() == str(value).strip().lower():
                                    if option_id:
                                        logger.debug(f"  Найден ID варианта: {option_id} для значения '{value}' (найдено: '{option_value}')")
                                        value = int(option_id) if isinstance(option_id, (int, str)) and str(option_id).isdigit() else option_id
                                        prop_type = 'select'
                                        break
                                # Также проверяем точное совпадение
                                elif option_value == value:
                                    if option_id:
                                        logger.debug(f"  Найден ID варианта (точное совпадение): {option_id} для значения '{value}'")
                                        value = int(option_id) if isinstance(option_id, (int, str)) and str(option_id).isdigit() else option_id
                                        prop_type = 'select'
                                        break
                        
                        # Если не нашли ID варианта, предполагаем Select, но значение останется строкой
                        if not isinstance(value, (int, float)):
                            prop_type = 'select'
                            logger.warning(f"  ⚠️  Не найден ID варианта для значения '{value}' в Select-поле {property_id}")
                    else:
                        # Если не удалось получить значения, предполагаем Select
                        prop_type = 'select'
                        logger.debug(f"  Не удалось получить значения Select-поля, предполагаем type=select")
                except (ValueError, TypeError):
                    property_id = field_id_clean
                    logger.debug(f"  Используем property_id из field_id (строковый): {property_id}")
                    prop_type = 'select'  # Предполагаем Select по умолчанию
            
            # Формируем ключ в формате "id_{property_id}"
            if property_id is not None:
                property_key = f"id_{property_id}"
                
                # Для Select-полей API требует массив с ID варианта (integer)
                # Если это Select-поле, передаем массив с ID варианта
                if prop_type in ('select', 'multi_select'):
                    # Для Select-полей API требует массив с integer (ID варианта)
                    if isinstance(value, (int, float)):
                        # Если value уже число (ID варианта), передаем массив с числом
                        final_value = [int(value)]
                        logger.debug(f"  Select-поле: используем ID варианта: {final_value}")
                        properties[property_key] = final_value
                        logger.debug(f"  Добавлено в properties: {property_key} = {final_value}")
                    else:
                        # Если value строка, но мы не нашли ID варианта, пропускаем это поле
                        logger.warning(f"  ⚠️  Для Select-поля не найден ID варианта для значения '{value}'. Поле пропущено.")
                        logger.warning(f"  ⚠️  Убедитесь, что значение '{value}' существует в вариантах выбора свойства {property_id}")
                else:
                    # Для других типов полей передаем значение как есть
                    final_value = value
                    properties[property_key] = final_value
                    logger.debug(f"  Добавлено в properties: {property_key} = {final_value}")
            else:
                logger.warning(f"  ⚠️  Не удалось определить property_id для поля {field_id}")
        
        if not properties:
            logger.warning("Нет полей для обновления!")
            return False
        
        # Формируем данные для обновления в правильном формате
        update_data = {
            'properties': properties
        }
        
        logger.info(f"Данные для обновления: {json.dumps(update_data, ensure_ascii=False, indent=2)}")
        
        # Логируем структуру текущей карточки для отладки
        logger.debug(f"Структура custom_properties в текущей карточке:")
        if 'custom_properties' in card:
            for prop in card['custom_properties']:
                prop_id = prop.get('id')
                property_id = prop.get('property_id')
                # Проверяем, обновляем ли мы это поле
                is_updating = any(
                    str(prop_id) == str(fid) or str(property_id) == str(fid) 
                    for fid, _ in fields_to_update if fid
                )
                if is_updating:
                    logger.debug(f"  >>> ОБНОВЛЯЕМ: {json.dumps(prop, ensure_ascii=False)}")
                else:
                    logger.debug(f"  {json.dumps(prop, ensure_ascii=False)}")
        
        # Обновляем карточку с правильным форматом
        success = self.client.update_card(card_id, update_data)
        
        # Проверяем, что обновление действительно применилось
        if success:
            # Небольшая задержка перед проверкой, чтобы API успел обработать обновление
            import time
            time.sleep(0.5)
            
            # Проверяем, что обновление действительно применилось
            updated_card = self.client.get_card(card_id)
            if updated_card:
                logger.debug("Проверка обновленных значений:")
                logger.debug(f"Полная структура обновленной карточки (custom_properties):")
                if 'custom_properties' in updated_card:
                    for prop in updated_card['custom_properties']:
                        prop_id = prop.get('id')
                        property_id = prop.get('property_id')
                        prop_value = prop.get('value')
                        # Проверяем, относится ли это поле к обновляемым
                        is_target = any(
                            str(prop_id) == str(fid.replace('id_', '')) or 
                            str(property_id) == str(fid.replace('id_', '')) or
                            str(prop_id) == str(fid) or 
                            str(property_id) == str(fid)
                            for fid, _ in fields_to_update if fid
                        )
                        if is_target:
                            logger.debug(f"  >>> ЦЕЛЕВОЕ ПОЛЕ: id={prop_id}, property_id={property_id}, value={prop_value}")
                        else:
                            logger.debug(f"  id={prop_id}, property_id={property_id}, value={prop_value}")
                
                for field_id, expected_value in [
                    (self.field_rating_kachestva, parameters['rating_kachestva']),
                    (self.field_tip_kontenta, parameters['tip_kontenta']),
                    (self.field_uroven_spikera, parameters['uroven_spikera']),
                    (self.field_ohvat, parameters['ohvat'])
                ]:
                    if field_id:
                        actual_value = self.extract_field_value(updated_card, field_id)
                        logger.debug(f"  Поле {field_id}: ожидается '{expected_value}', получено '{actual_value}'")
                        if str(actual_value) != str(expected_value):
                            logger.warning(
                                f"  ⚠️  Поле {field_id} не обновилось! "
                                f"Ожидалось: '{expected_value}', получено: '{actual_value}'"
                            )
        if success:
            logger.info(f"Параметры карточки {card_id} успешно обновлены")
        else:
            logger.error(f"Не удалось обновить параметры карточки {card_id}")
        
        return success
    
    def process_card(self, card: Dict[str, Any]) -> bool:
        """Обработать карточку (вычислить и обновить параметры)"""
        card_id = card.get('id')
        if not card_id:
            logger.warning("Карточка без ID пропущена")
            return False
        
        return self.update_card_parameters(card_id)


def get_config_from_env() -> Dict[str, Any]:
    """Получить конфигурацию из переменных окружения Cloud Functions"""
    api_url = os.environ.get('KAITEN_API_URL')
    api_token = os.environ.get('KAITEN_API_TOKEN')
    
    if not api_url or not api_token:
        raise ValueError(
            "Необходимо указать KAITEN_API_URL и KAITEN_API_TOKEN в переменных окружения"
        )
    
    # ID полей критериев (входные данные)
    field_aktualnost = os.environ.get('FIELD_AKTUALNOST')
    field_novizna = os.environ.get('FIELD_NOVIZNA')
    field_opyt_spikera = os.environ.get('FIELD_OPYT_SPIKERA')
    field_primenimost = os.environ.get('FIELD_PRIMENIMOST')
    field_harizma = os.environ.get('FIELD_HARIZMA')
    field_influencer = os.environ.get('FIELD_INFLUENCER')
    field_massovost = os.environ.get('FIELD_MASSOVOST')
    
    # ID полей результатов (выходные данные)
    field_rating_kachestva = os.environ.get('FIELD_RATING_KACHESTVA')
    field_tip_kontenta = os.environ.get('FIELD_TIP_KONTENTA')
    field_uroven_spikera = os.environ.get('FIELD_UROVEN_SPIKERA')
    field_ohvat = os.environ.get('FIELD_OHVAT')
    
    board_id = os.environ.get('BOARD_ID')
    space_id = os.environ.get('SPACE_ID')
    
    return {
        'api_url': api_url,
        'api_token': api_token,
        'field_aktualnost': field_aktualnost,
        'field_novizna': field_novizna,
        'field_opyt_spikera': field_opyt_spikera,
        'field_primenimost': field_primenimost,
        'field_harizma': field_harizma,
        'field_influencer': field_influencer,
        'field_massovost': field_massovost,
        'field_rating_kachestva': field_rating_kachestva,
        'field_tip_kontenta': field_tip_kontenta,
        'field_uroven_spikera': field_uroven_spikera,
        'field_ohvat': field_ohvat,
        'board_id': int(board_id) if board_id else None,
        'space_id': int(space_id) if space_id else None,
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Обработчик для Yandex Cloud Functions.
    
    Поддерживает два режима работы:
    1. HTTP-триггер (вебхук от Kaiten) - event содержит данные о карточке
    2. Timer-триггер (расписание) - обрабатывает все карточки
    
    Args:
        event: Событие от триггера
        context: Контекст выполнения функции
    
    Returns:
        Результат выполнения в формате для Cloud Functions
    """
    try:
        # Детальное логирование входящего события
        logger.info("=" * 80)
        logger.info("НАЧАЛО ОБРАБОТКИ ФУНКЦИИ")
        logger.info("=" * 80)
        # Отладочный вывод полного event объекта (включить через DEBUG_FULL_EVENT=true)
        if DEBUG_FULL_EVENT:
            logger.error(f"Полный event объект: {json.dumps(event, ensure_ascii=False, indent=2, default=str)}")
        logger.info(f"Ключи в event: {list(event.keys())}")
        logger.info("-" * 80)
        
        # Загружаем конфигурацию
        config = get_config_from_env()
        client = KaitenClient(config['api_url'], config['api_token'])
        evaluator = ConferenceProposalEvaluator(client, config)
        
        # Определяем тип триггера
        is_http_trigger = (
            'httpMethod' in event or 
            'requestContext' in event or
            ('body' in event and event.get('body') not in (None, ''))
        )
        
        is_timer_trigger = (
            event.get('source') == 'system' or
            'messages' in event or
            ('request_id' in event and 'version_id' in event)
        )
        
        logger.info(f"Определение типа триггера: HTTP={is_http_trigger}, Timer={is_timer_trigger}")
        
        if is_http_trigger and not is_timer_trigger:
            # HTTP-триггер (вебхук)
            logger.info("Обработка как HTTP-триггер")
            return handle_http_trigger(event, evaluator)
        else:
            # Timer-триггер или другой тип (по умолчанию обрабатываем как Timer)
            logger.info("Обработка как Timer-триггер")
            return handle_timer_trigger(event, evaluator, config)
            
    except Exception as e:
        logger.error(f"Ошибка выполнения функции: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Internal server error'
            }, ensure_ascii=False)
        }


def handle_http_trigger(event: Dict[str, Any], evaluator: ConferenceProposalEvaluator) -> Dict[str, Any]:
    """Обработка HTTP-триггера (вебхук от Kaiten)"""
    try:
        # Детальное логирование входящего запроса для отладки
        logger.info("=" * 80)
        logger.info("ПОЛУЧЕН HTTP-ЗАПРОС (WEBHOOK)")
        logger.info("=" * 80)
        # Отладочный вывод полного event объекта (включить через DEBUG_FULL_EVENT=true)
        if DEBUG_FULL_EVENT:
            logger.info(f"Полный event объект: {json.dumps(event, ensure_ascii=False, indent=2, default=str)}")
        logger.info("-" * 80)
        
        # Логируем все ключи event для понимания структуры
        logger.info(f"Ключи в event: {list(event.keys())}")
        
        # Логируем заголовки, если есть
        headers = {}
        if 'headers' in event:
            headers = event.get('headers', {})
            logger.info(f"Заголовки запроса: {json.dumps(headers, ensure_ascii=False, indent=2)}")
        
        # Определяем Content-Type
        content_type = headers.get('Content-Type', headers.get('content-type', '')).lower()
        logger.info(f"Content-Type: {content_type}")
        
        # Логируем query параметры, если есть
        if 'queryStringParameters' in event:
            logger.info(f"Query параметры: {json.dumps(event.get('queryStringParameters', {}), ensure_ascii=False, indent=2)}")
        
        # Логируем path параметры, если есть
        if 'pathParameters' in event:
            logger.info(f"Path параметры: {json.dumps(event.get('pathParameters', {}), ensure_ascii=False, indent=2)}")
        
        # Парсим тело запроса
        body = event.get('body', '{}')
        is_base64 = event.get('isBase64Encoded', False)
        
        logger.info(f"Body (raw): {body}")
        logger.info(f"isBase64Encoded: {is_base64}")
        logger.info("-" * 80)
        
        if isinstance(body, str):
            # Декодируем base64, если нужно
            if is_base64:
                try:
                    body = base64.b64decode(body).decode('utf-8')
                    logger.info("Декодирован base64 body")
                except Exception as e:
                    logger.error(f"Ошибка декодирования base64: {e}")
                    body = '{}'
            
            # Проверяем, что body не пустой перед парсингом
            if body.strip():
                # Обработка form-data и urlencoded
                if 'application/x-www-form-urlencoded' in content_type:
                    logger.info("Обнаружен Content-Type: application/x-www-form-urlencoded")
                    try:
                        from urllib.parse import parse_qs, unquote
                        parsed = parse_qs(body, keep_blank_values=True)
                        # Преобразуем в плоский словарь (берем первое значение из списка)
                        body = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
                        logger.info("Body распарсен как urlencoded")
                        # Пробуем найти JSON в значениях
                        for key, value in body.items():
                            if isinstance(value, str) and value.strip().startswith('{'):
                                try:
                                    body[key] = json.loads(value)
                                    logger.info(f"Найден JSON в поле '{key}'")
                                except json.JSONDecodeError:
                                    pass
                    except Exception as e:
                        logger.warning(f"Ошибка парсинга urlencoded: {e}")
                        body = {}
                elif 'multipart/form-data' in content_type:
                    logger.info("Обнаружен Content-Type: multipart/form-data")
                    # Для multipart/form-data нужно парсить границы
                    # Yandex Cloud Functions обычно уже парсит это, но проверим
                    logger.warning("multipart/form-data требует специальной обработки")
                    # Пробуем найти JSON в body
                    if body.strip().startswith('{'):
                        try:
                            body = json.loads(body)
                            logger.info("Найден JSON в multipart body")
                        except json.JSONDecodeError:
                            body = {}
                else:
                    # Пробуем распарсить как JSON (обычный случай)
                    try:
                        body = json.loads(body)
                        logger.info(f"Body успешно распарсен как JSON")
                        # Если получили строку, пробуем распарсить еще раз (на случай двойного экранирования)
                        if isinstance(body, str):
                            logger.info("Body после первого парсинга - строка, пробуем распарсить еще раз")
                            try:
                                body = json.loads(body)
                                logger.info("Body успешно распарсен после второго парсинга")
                            except json.JSONDecodeError:
                                logger.warning("Не удалось распарсить body второй раз")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Не удалось распарсить body как JSON: {e}")
                        logger.warning(f"Содержимое body (первые 500 символов): {body[:500]}")
                        # Пробуем найти JSON внутри строки
                        try:
                            # Ищем первую открывающую скобку
                            start = body.find('{')
                            if start != -1:
                                # Пробуем распарсить с этой позиции
                                body = json.loads(body[start:])
                                logger.info("Найден и распарсен JSON внутри строки body")
                        except (json.JSONDecodeError, ValueError):
                            body = {}
            else:
                logger.warning("Body пустой или содержит только пробелы")
                body = {}
        elif body is None:
            logger.warning("Body равен None")
            body = {}
        else:
            logger.info(f"Body уже является объектом (не строка): {json.dumps(body, ensure_ascii=False, indent=2, default=str)}")
        
        logger.info("-" * 80)
        logger.info(f"Body после обработки:")
        logger.info(f"  Тип body: {type(body).__name__}")
        if isinstance(body, dict):
            logger.info(f"  Ключи в body: {list(body.keys())}")
            # Детальная информация о структуре body
            for key in body.keys():
                value = body[key]
                if isinstance(value, dict):
                    logger.info(f"  body['{key}']: dict с ключами: {list(value.keys())[:10]}")
                elif isinstance(value, list):
                    logger.info(f"  body['{key}']: list длиной {len(value)}")
                else:
                    logger.info(f"  body['{key}']: тип={type(value).__name__}, значение={str(value)[:100]}")
            
            # Выводим полный JSON body для отладки (первые 3000 символов)
            body_json = json.dumps(body, ensure_ascii=False, indent=2, default=str)
            logger.info(f"  Полный JSON body (первые 3000 символов):")
            logger.info(body_json[:3000])
            if len(body_json) > 3000:
                logger.info(f"  ... (еще {len(body_json) - 3000} символов)")
        else:
            logger.warning(f"⚠️ Body не является словарем! Тип: {type(body).__name__}")
            logger.warning(f"   Значение body: {str(body)[:500]}")
        logger.info("-" * 80)
        
        # Убеждаемся, что body - это словарь
        if not isinstance(body, dict):
            logger.error("КРИТИЧЕСКАЯ ОШИБКА: body не является словарем после парсинга!")
            logger.error(f"Тип body: {type(body).__name__}")
            logger.error(f"Значение body: {body}")
            # Пробуем найти JSON в других местах event
            logger.info("Попытка найти JSON в других местах event...")
            for key in ['requestBody', 'payload', 'data', 'json']:
                if key in event:
                    logger.info(f"Найдено поле event['{key}']: {type(event[key]).__name__}")
                    if isinstance(event[key], str):
                        try:
                            parsed = json.loads(event[key])
                            if isinstance(parsed, dict):
                                body = parsed
                                logger.info(f"✓ JSON найден и распарсен из event['{key}']")
                                break
                        except (json.JSONDecodeError, TypeError):
                            pass
                    elif isinstance(event[key], dict):
                        body = event[key]
                        logger.info(f"✓ Используем event['{key}'] как body")
                        break
            if not isinstance(body, dict):
                body = {}
        
        # Проверяем, может быть JSON находится внутри body в поле payload, data или json
        if isinstance(body, dict):
            for key in ['payload', 'data', 'json', 'body', 'webhook']:
                if key in body:
                    value = body[key]
                    logger.info(f"Найдено поле body['{key}'], тип: {type(value).__name__}")
                    if isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                            if isinstance(parsed, dict):
                                logger.info(f"✓ JSON найден в body['{key}'], используем его")
                                body = parsed
                                break
                        except json.JSONDecodeError:
                            pass
                    elif isinstance(value, dict):
                        logger.info(f"✓ Используем body['{key}'] как основной body")
                        body = value
                        break
        
        # Если body пустой, пробуем использовать весь event как body
        if not body or (isinstance(body, dict) and len(body) == 0):
            logger.warning("Body пустой, пробуем использовать весь event как body")
            # Исключаем служебные поля Yandex Cloud Functions
            service_keys = ['httpMethod', 'path', 'headers', 'multiValueHeaders', 
                          'queryStringParameters', 'multiValueQueryStringParameters',
                          'pathParameters', 'requestContext', 'resource', 'isBase64Encoded']
            event_as_body = {k: v for k, v in event.items() if k not in service_keys and k != 'body'}
            if event_as_body:
                logger.info(f"Используем event (без служебных полей) как body. Ключи: {list(event_as_body.keys())}")
                body = event_as_body
        
        # Извлекаем ID карточки из вебхука
        card_id = None
        
        logger.info("Попытки извлечения card_id:")
        logger.info(f"  Тип body: {type(body).__name__}")
        logger.info(f"  Все ключи в body: {list(body.keys())}")
        
        # Функция для безопасного извлечения ID из значения
        def extract_id(value, path="root"):
            """Безопасно извлекает ID из значения"""
            if value is None:
                return None
            if isinstance(value, int):
                # ID карточки обычно большое число (больше 1000)
                if value > 1000:
                    logger.info(f"  ✓ Найден потенциальный ID в {path}: {value}")
                    return value
            elif isinstance(value, str):
                try:
                    int_value = int(value)
                    if int_value > 1000:
                        logger.info(f"  ✓ Найден потенциальный ID в {path}: {int_value}")
                        return int_value
                except ValueError:
                    pass
            return None
        
        # Рекурсивная функция для поиска ID во всей структуре
        def find_id_recursive(obj, path="", max_depth=5, current_depth=0):
            """Рекурсивно ищет поле 'id' во всей структуре"""
            if current_depth >= max_depth:
                return None
            
            if isinstance(obj, dict):
                # Проверяем прямое поле 'id'
                if 'id' in obj:
                    potential_id = extract_id(obj['id'], f"{path}['id']")
                    if potential_id:
                        return potential_id
                
                # Рекурсивно проверяем все значения
                for key, value in obj.items():
                    if key == 'id':
                        continue  # Уже проверили
                    new_path = f"{path}['{key}']" if path else f"['{key}']"
                    result = find_id_recursive(value, new_path, max_depth, current_depth + 1)
                    if result:
                        return result
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]"
                    result = find_id_recursive(item, new_path, max_depth, current_depth + 1)
                    if result:
                        return result
            
            return None
        
        # Список всех возможных путей к ID (в порядке приоритета)
        id_paths = [
            # Стандартная структура вебхука Kaiten: body['data']['old']['id']
            ("body['data']['old']['id']", lambda: body.get('data', {}).get('old', {}).get('id') if isinstance(body, dict) and isinstance(body.get('data'), dict) and isinstance(body.get('data', {}).get('old'), dict) else None),
            # Альтернативные пути
            ("body['id']", lambda: body.get('id') if isinstance(body, dict) else None),
            ("body['card_id']", lambda: body.get('card_id') if isinstance(body, dict) else None),
            ("body['card']['id']", lambda: body.get('card', {}).get('id') if isinstance(body, dict) and isinstance(body.get('card'), dict) else None),
            ("body['card']", lambda: body.get('card') if isinstance(body, dict) and not isinstance(body.get('card'), dict) else None),
            ("body['data']['id']", lambda: body.get('data', {}).get('id') if isinstance(body, dict) and isinstance(body.get('data'), dict) else None),
            ("body['data']['changes']['id']", lambda: body.get('data', {}).get('changes', {}).get('id') if isinstance(body, dict) and isinstance(body.get('data'), dict) and isinstance(body.get('data', {}).get('changes'), dict) else None),
            ("body['payload']['id']", lambda: body.get('payload', {}).get('id') if isinstance(body, dict) and isinstance(body.get('payload'), dict) else None),
            ("body['webhook']['id']", lambda: body.get('webhook', {}).get('id') if isinstance(body, dict) and isinstance(body.get('webhook'), dict) else None),
        ]
        
        # Проверяем все пути по порядку
        for path_name, path_func in id_paths:
            if card_id:
                break
            try:
                potential_id = path_func()
                if potential_id is not None:
                    logger.info(f"  Проверка {path_name}: значение={potential_id}, тип={type(potential_id).__name__}")
                    card_id = extract_id(potential_id, path_name)
                    if card_id:
                        logger.info(f"  ✓ Найден в {path_name}: {card_id}")
            except Exception as e:
                logger.debug(f"  Ошибка при проверке {path_name}: {e}")
        
        # Если все еще не нашли, пробуем рекурсивный поиск
        if not card_id:
            logger.info("  ✗ card_id не найден в стандартных местах, пробуем рекурсивный поиск...")
            logger.info(f"  Доступные ключи в body: {list(body.keys())}")
            
            # Рекурсивный поиск в body
            card_id = find_id_recursive(body, "body")
            if card_id:
                logger.info(f"  ✓ Найден через рекурсивный поиск в body: {card_id}")
            
            # Если не нашли в body, пробуем в event
            if not card_id:
                logger.info("  Рекурсивный поиск в event...")
                card_id = find_id_recursive(event, "event")
                if card_id:
                    logger.info(f"  ✓ Найден через рекурсивный поиск в event: {card_id}")
            
            # Выводим структуру body для отладки
            if not card_id:
                logger.info(f"  Полная структура body (первые 2000 символов):")
                logger.info(json.dumps(body, ensure_ascii=False, indent=2, default=str)[:2000])
        
        # Также можно получить из query параметров
        if not card_id and 'queryStringParameters' in event:
            query_params = event.get('queryStringParameters') or {}
            logger.info(f"  Проверка query параметров: {json.dumps(query_params, ensure_ascii=False)}")
            card_id = query_params.get('card_id')
            if card_id:
                try:
                    card_id = int(card_id)
                    logger.info(f"  ✓ Найден в queryStringParameters['card_id']: {card_id}")
                except ValueError:
                    logger.warning(f"  ✗ card_id в query параметрах не является числом: {card_id}")
                    card_id = None
        
        # Проверяем также в корне event (на случай нестандартного формата)
        if not card_id:
            logger.info("  Проверка альтернативных мест в event:")
            logger.info(f"  Все ключи в event: {list(event.keys())}")
            
            # Проверяем все возможные места в event
            for key in ['id', 'card_id', 'card']:
                if key in event:
                    logger.info(f"  Найдено поле event['{key}']: {event[key]}, тип: {type(event[key]).__name__}")
                    if key == 'id':
                        card_id = extract_id(event[key], f"event['{key}']")
                    elif key == 'card_id':
                        card_id = extract_id(event[key], f"event['{key}']")
                    elif key == 'card':
                        if isinstance(event['card'], dict) and 'id' in event['card']:
                            card_id = extract_id(event['card']['id'], "event['card']['id']")
                        else:
                            card_id = extract_id(event['card'], f"event['{key}']")
                    if card_id:
                        logger.info(f"  ✓ Найден в event['{key}']: {card_id}")
                        break
            
            # Если все еще не нашли, проверяем, может быть весь event и есть body
            if not card_id:
                logger.info("  Проверка: может быть весь event и есть JSON body?")
                if 'id' in event and isinstance(event['id'], (int, str)):
                    try:
                        potential_id = int(event['id'])
                        if potential_id > 1000:  # ID карточки обычно большое число
                            card_id = potential_id
                            logger.info(f"  ✓ Найден в корне event как ID: {card_id}")
                    except (ValueError, TypeError):
                        pass
        
        logger.info("-" * 80)
        
        if not card_id:
            logger.error("=" * 80)
            logger.error("ОШИБКА: Вебхук не содержит card_id")
            logger.error("=" * 80)
            logger.error("ДИАГНОСТИЧЕСКАЯ ИНФОРМАЦИЯ:")
            logger.error(f"  Тип body: {type(body).__name__}")
            logger.error(f"  Ключи в body: {list(body.keys()) if isinstance(body, dict) else 'N/A'}")
            logger.error(f"  Ключи в event: {list(event.keys())}")
            
            # Выводим полную структуру event для отладки (первые 5000 символов)
            try:
                event_json = json.dumps(event, ensure_ascii=False, indent=2, default=str)
                logger.error(f"  Полная структура event (первые 5000 символов):")
                logger.error(event_json[:5000])
                if len(event_json) > 5000:
                    logger.error(f"  ... (еще {len(event_json) - 5000} символов)")
            except Exception as e:
                logger.error(f"  Не удалось сериализовать event: {e}")
            
            logger.error("=" * 80)
            logger.error("Для отладки проверьте логи выше - там должна быть полная структура запроса")
            logger.error("=" * 80)
            
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'card_id not found in request',
                    'debug_info': {
                        'body_keys': list(body.keys()) if isinstance(body, dict) else 'not a dict',
                        'event_keys': list(event.keys()),
                        'body_type': type(body).__name__,
                        'body_preview': str(body)[:500] if body else 'empty',
                        'message': 'Check logs for full request structure. Look for "Полная структура event" in logs.'
                    }
                }, ensure_ascii=False)
            }
        
        logger.info(f"Обработка карточки {card_id} из вебхука")
        success = evaluator.update_card_parameters(card_id)
        
        if success:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'card_id': card_id
                }, ensure_ascii=False)
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'status': 'error',
                    'card_id': card_id,
                    'message': 'Failed to update card parameters'
                }, ensure_ascii=False)
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid JSON in request body'
            }, ensure_ascii=False)
        }
    except Exception as e:
        logger.error(f"Ошибка обработки HTTP-триггера: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            }, ensure_ascii=False)
        }


def handle_timer_trigger(event: Dict[str, Any], evaluator: ConferenceProposalEvaluator, 
                         config: Dict[str, Any]) -> Dict[str, Any]:
    """Обработка Timer-триггера (периодический запуск)"""
    try:
        logger.info("Запуск обработки по расписанию")
        
        client = evaluator.client
        
        # Получаем список карточек
        cards = client.get_cards(
            board_id=config.get('board_id'),
            space_id=config.get('space_id')
        )
        
        if not cards:
            logger.warning("Карточки не найдены")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'message': 'No cards found',
                    'processed': 0
                }, ensure_ascii=False)
            }
        
        logger.info(f"Найдено {len(cards)} карточек. Начинаю обработку...")
        
        success_count = 0
        error_count = 0
        processed_cards = []
        
        for card in cards:
            try:
                card_id = card.get('id')
                if evaluator.process_card(card):
                    success_count += 1
                    processed_cards.append({'id': card_id, 'status': 'success'})
                else:
                    error_count += 1
                    processed_cards.append({'id': card_id, 'status': 'error'})
            except Exception as e:
                logger.error(f"Ошибка при обработке карточки {card.get('id')}: {e}")
                error_count += 1
                processed_cards.append({
                    'id': card.get('id'),
                    'status': 'error',
                    'error': str(e)
                })
        
        logger.info(
            f"Обработка завершена: успешно {success_count}, ошибок {error_count}"
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'processed': success_count + error_count,
                'success': success_count,
                'errors': error_count,
                'cards': processed_cards[:10]  # Ограничиваем вывод
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        logger.error(f"Ошибка обработки Timer-триггера: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            }, ensure_ascii=False)
        }
