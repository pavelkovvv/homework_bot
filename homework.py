import requests
import os
import telegram
import time

from telegram.ext import Updater, CommandHandler
from telegram import ReplyKeyboardMarkup
from dotenv import load_dotenv
from exceptions import MissingEnvironmentVariable, MissingValueAPI
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: int = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
STATUS_HOMEWORK = None

HOMEWORK_VERDICTS: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения"""

    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    for token in tokens:
        if token in os.environ:
            continue
        else:
            raise MissingEnvironmentVariable(f'Переменная окружения {token}'
                                             f' не найдена.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат"""

    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message
    )


def get_api_answer(timestamp):
    """Делаем запрос к эндпоинту API-сервиса"""

    response = requests.get(ENDPOINT, headers=HEADERS,
                            params={'from_date': timestamp})
    if response.status_code == HTTPStatus.OK:
        return response.json()


def check_response(response):
    """Проверка API на соответствие документации"""

    keys_in_answer = ('current_date', 'homeworks')
    keys_in_homeworks = ('date_updated', 'homework_name', 'id', 'lesson_name',
                         'reviewer_comment', 'status')

    for key in keys_in_answer:
        if key in response:
            if key == 'homeworks':
                for key_homeworks in keys_in_homeworks:
                    if key_homeworks in response['homeworks'][0]:
                        continue
                    else:
                        raise MissingValueAPI(f'Значение переменной'
                                              f' {key_homeworks} в ответе API'
                                              f' не найдено.')
        else:
            raise MissingValueAPI(f'Значение переменной {key} в ответе API'
                                  f'не найдено.')


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы"""

    if homework['status'] in HOMEWORK_VERDICTS:
        return f'Изменился статус проверки работы ' \
               f'"{homework["homework_name"]}".' \
               f' {HOMEWORK_VERDICTS[homework["status"]]}'


def main():
    """Основная логика работы бота."""

    # Проверяем переменные окружения
    check_tokens()
    # Устанавливаем время равное 0, чтобы получить все домашки
    timestamp = 0
    time.sleep(0)
    while True:
        try:
            updater = Updater(token=TELEGRAM_TOKEN)
            # Получаем ответ API приведённый к типу данных Python
            api_answer = get_api_answer(timestamp)

            bot = telegram.Bot(token=TELEGRAM_TOKEN)

            # Проверка API на соответствие документации
            check_response(api_answer)

            # Извлекаем нужную информацию о последней домашке
            parse_status_answer = parse_status(api_answer['homeworks'][0])

            # Отправляем сообщение пользователю
            global STATUS_HOMEWORK
            if STATUS_HOMEWORK != parse_status_answer:
                send_message(bot, parse_status_answer)
                STATUS_HOMEWORK = parse_status_answer

            updater.start_polling(poll_interval=RETRY_PERIOD)
            updater.idle()

        except MissingValueAPI as error:
            message = f'Значение переменной в ответе API не найдено: {error}'
            send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)


if __name__ == '__main__':
    main()
