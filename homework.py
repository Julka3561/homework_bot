from asyncio.log import logger
import os
import time
from http import HTTPStatus

import logging
import requests
import telegram
from dotenv import load_dotenv

from exceptions import DictIsEmptyError

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения об изменении статуса работы в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as telegram_error:
        message = (f'Сбой в работе программы: Отправка сообщения в чат не'
                   f'удалась. {telegram_error}')
        logging.error(telegram_error)
    else:
        logging.info(f'Сообщение успешно отправлено: "{message}"')


def get_api_answer(current_timestamp):
    """Получение ответа от API Практикум."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f'Эндпоинт {response.url} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка правильности формата ответа от API Практикума."""
    if type(response) is not dict:
        raise TypeError(f'Неверный тип данных ответа API Практикума. Ожидался '
                        f'dict, получен {type(response)}')
    elif len(response) < 1:
        raise DictIsEmptyError('Словарь ответа API пуст')
    elif 'homeworks' not in response:
        raise KeyError('Ключа homeworks нет в ответе API')
    elif type(response['homeworks']) is not list:
        raise TypeError('homeworks не явлеятся списком')
    else:
        return response['homeworks']


def parse_status(homework):
    """Получение статуса домашней работы из списка работ."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError(f'Неверный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия всех необходимых для работы бота переменных среды."""
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        logger.critical('Отсутствуют переменные среды. '
                        'Запуск бота не возможен!')
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    cache_message = ''
    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Новые статусы отсутствуют')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(error)
            if cache_message != message:
                send_message(bot, message)
                cache_message = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
