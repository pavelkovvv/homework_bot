import json
import requests
import os
import telegram
import time
import logging
import datetime as dt
import exceptions as ex

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens: tuple = (TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug(f'Сообщение <<<{message}>>> успешно отправлено.')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делаем запрос к эндпоинту API-сервиса."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except Exception as exc:
        logging.error('Ошибка при подключении к эндпоинту.')
        raise ConnectionError from exc

    if response.status_code == HTTPStatus.OK:
        try:
            response_json = response.json()
            return response_json
        except Exception as exc:
            logging.error('Ошибка при десириализации json.')
            raise json.decoder.JSONDecodeError from exc
    else:
        logging.error(f'Неверный ответ API: {response.status_code}.')
        raise ex.InvalidStatusCodeAPI(f'Неверный ответ API:'
                                      f' {response.status_code}')


def check_response(response):
    """Проверка API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error(f'Ответ API  приходит не в ожидаемом виде. Получен'
                      f' {type(response)}, а ожидался dict.')
        raise TypeError(f'Ответ API  приходит не в ожидаемом виде. Получен'
                        f' {type(response)},а ожидался dict.')

    if 'homeworks' not in response or 'current_date' not in response:
        logging.error('Значение одной из переменной в ответе API не найдено.')
        raise KeyError('Значение одной из переменной в ответе API не найдено.')

    homework = response['homeworks']
    if not isinstance(homework, list):
        logging.error(f'Ответ API под ключом "homeworks" приходит не в'
                      f' ожидаемом виде. Получен {type(homework)},'
                      f' а ожидался list.')
        raise TypeError(f'Ответ API под ключом "homeworks" приходит не в'
                        f' ожидаемом виде. Получен {type(homework)},'
                        f' а ожидался list.')


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'status' not in homework or 'homework_name' not in homework:
        logging.error('Значение одной из переменной в ответе API не найдено.')
        raise KeyError('Значение одной из переменной в ответе API не найдено.')

    if homework['status'] in HOMEWORK_VERDICTS:
        return ('Изменился статус проверки работы'
                f' "{homework["homework_name"]}".'
                f' {HOMEWORK_VERDICTS[homework["status"]]}')
    else:
        logging.error('API возвращает незадокументированный аргумент'
                      f' {homework["status"]}.')
        raise ex.APIReturningUnknownArgument(f'API возвращает'
                                             ' незадокументированный'
                                             ' аргумент'
                                             f' {homework["status"]}')


def main():
    """Основная логика работы бота."""
    STATUS_HOMEWORK = None

    logging.debug('--------------')

    # Проверяем переменные окружения
    if not check_tokens():
        logging.critical('Отсутсвуют переменные окружения!')
        raise ex.MissingEnvironmentVariable(
            'Отсутствуют переменные окружения!')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    timestamp = int(time.mktime((dt.datetime.now()
                                 - dt.timedelta(days=50)).timetuple()))

    while True:
        try:
            logging.debug('Начало новой итерации')

            # Получаем ответ API приведённый к типу данных Python
            api_answer = get_api_answer(timestamp)

            # Проверка API на соответствие документации
            check_response(api_answer)

            # Извлекаем нужную информацию о последней домашке
            if len(api_answer['homeworks']) > 0:
                parse_status_answer = parse_status(api_answer['homeworks'][0])
            else:
                parse_status_answer = 'Обновлений в ДЗ пока нет'

            # Отправляем сообщение пользователю
            if STATUS_HOMEWORK != parse_status_answer:
                send_message(bot, parse_status_answer)
                STATUS_HOMEWORK = parse_status_answer

        except Exception as error:
            logging.critical(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            if message != STATUS_HOMEWORK:
                send_message(bot, message)
                STATUS_HOMEWORK = message
            logging.debug('--------------')

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[logging.FileHandler('homework_log.log'),
                  logging.StreamHandler()]
    )
    main()
