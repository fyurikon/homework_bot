import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(
            filename='homework.log', mode='w', encoding='UTF-8'),
        logging.StreamHandler(stream=sys.stdout)
    ],
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

REQUIRED_TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def check_tokens():
    """Check that all tokens are available."""
    for token in REQUIRED_TOKENS:
        if globals()[token] is None:
            logging.critical(f'No token -{token}- found')
            raise ValueError(f'{token} is missing.')


def send_message(bot, message):
    """Send message."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('The message was successfully sent.')
    except telegram.error.TelegramError as error:
        logging.exception(
            f'The following error appears while sending the message: {error}'
        )


def get_api_answer(timestamp):
    """Get an answer form API."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Connection failed: {error}'
        )

    if response.status_code != 200:
        raise exceptions.ApiResponseFailed(
            f'Failed get answer from API. Status code = {response.status_code}'
        )

    response_json = response.json()

    return response_json


def check_response(response):
    """Check the response."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Response is {type(response)}, but dict expected.'
        )

    if 'homeworks' not in response:
        raise KeyError(
            'homeworks not in the response'
        )

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError(
            f'Response is {type(homeworks)}, but list expected.'
        )

    return homeworks


def parse_status(homework):
    """Get status of homework."""
    if 'homework_name' not in homework:
        raise KeyError(
            "homework_name not found while parsing homework."
        )

    if 'status' not in homework:
        raise KeyError(
            "status not found while parsing homework."
        )

    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'unknown status = {status}.'
        )

    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Main bot logic."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                continue

            message = parse_status(homeworks[0])
            if last_message != message:
                send_message(bot, message)
                last_message = message
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Program failed: {error}'
            logging.exception(message)

            if last_message != message:
                try:
                    send_message(bot, message)
                    last_message = message
                except Exception as error:
                    logging.exception(f'Failed to send error message: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
