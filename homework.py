import requests
import os
import telegram
import time
import logging
import exceptions as exc


from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
STATUS_HOMEWORK = None

HOMEWORK_VERDICTS: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('homework_log.log', maxBytes=50000000,
                              backupCount=5)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения"""

    if TELEGRAM_TOKEN is None or PRACTICUM_TOKEN is None or\
            TELEGRAM_CHAT_ID is None:
        logger.critical('Отсутсвуют переменные окружения!')
        raise exc.MissingEnvironmentVariable(
            'Отсутствуют переменные окружения!')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат"""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug(f'Сообщение <<<{message}>>> успешно отправлено.')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делаем запрос к эндпоинту API-сервиса"""

    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
        response_json = response.json()
        if response.status_code == HTTPStatus.OK:
            logger.debug('Запрос от API успешно получен.')
            logger.debug(f'Ответ API: {response_json}')
            return response_json
        else:
            logger.error(f'Неверный ответ API: {response.status_code}.')
            raise exc.InvalidStatusCodeAPI(f'Неверный ответ API:'
                                           f' {response.status_code}')
    except Exception:
        if response.status_code != HTTPStatus.OK:
            raise exc.InvalidStatusCodeAPI('Endpoint API недоступен.')
        else:
            raise exc.InvalidStatusCodeAPI('Сбой при запросе к Endpoint API')


def check_response(response):
    """Проверка API на соответствие документации"""

    try:
        homework = response['homeworks']
        current_date = response['current_date']
        if type(homework) != list:
            logger.error(f'Ответ API под ключом "homeworks" приходит не в'
                         f' ожидаемом виде. Получен {type(homework)},'
                         f' а ожидался list.')
            raise TypeError(f'Ответ API под ключом "homeworks" приходит не в'
                            f' ожидаемом виде. Получен {type(homework)},'
                            f' а ожидался list.')
    except KeyError as error:
        logger.error(f'Значение переменной {error} в ответе API не найдено.')
        raise exc.MissingValueAPI(f'Значение переменной {error}'
                                  f' в ответе API не найдено.')


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы"""

    if homework['status'] in HOMEWORK_VERDICTS:
        if "homework_name" in homework:
            return f'Изменился статус проверки работы ' \
                   f'"{homework["homework_name"]}".' \
                   f' {HOMEWORK_VERDICTS[homework["status"]]}'
        else:
            logger.error('Переменная <homework_name> отсутствует в ответе API')
            raise exc.MissArgument('Переменная <homework_name> отсутствует'
                                   ' в ответе API')
    else:
        logger.error(f'API возвращает незадокументированный аргумент'
                     f' {homework["status"]}.')
        raise exc.APIReturningUnknownArgument(f'API возвращает'
                                              f' незадокументированный'
                                              f' аргумент'
                                              f' {homework["status"]}')


def main():
    """Основная логика работы бота."""

    logger.debug('--------------')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # Проверяем переменные окружения
    check_tokens()
    # Устанавливаем время равное 0, чтобы получить все домашки
    timestamp = 0

    while True:
        try:
            logger.debug('Начало новой итерации')

            # Получаем ответ API приведённый к типу данных Python
            api_answer = get_api_answer(timestamp)

            # Проверка API на соответствие документации
            check_response(api_answer)

            # Извлекаем нужную информацию о последней домашке
            parse_status_answer = parse_status(api_answer['homeworks'][0])

            # Отправляем сообщение пользователю
            global STATUS_HOMEWORK
            if STATUS_HOMEWORK != parse_status_answer:
                send_message(bot, parse_status_answer)
                STATUS_HOMEWORK = parse_status_answer

            time.sleep(RETRY_PERIOD)

        except Exception as error:
            logger.critical(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.debug('--------------')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
