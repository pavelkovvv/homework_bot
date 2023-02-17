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
    if not all(tokens):
        logging.critical('Отсутсвуют переменные окружения!')
        return False
    return True


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
        response_json = response.json()
        if response.status_code == HTTPStatus.OK:
            logging.debug('Запрос от API успешно получен.')
            logging.debug(f'Ответ API: {response_json}')
            return response_json
        else:
            logging.error(f'Неверный ответ API: {response.status_code}.')
            raise ex.InvalidStatusCodeAPI(f'Неверный ответ API:'
                                          f' {response.status_code}')
    except Exception:
        pass

    if response.status_code != HTTPStatus.OK:
        raise ex.InvalidStatusCodeAPI('Endpoint API недоступен.')
    else:
        raise ex.InvalidStatusCodeAPI('Сбой при запросе к Endpoint API')


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
        if "homework_name" in homework:
            return ('Изменился статус проверки работы'
                    f' "{homework["homework_name"]}".'
                    f' {HOMEWORK_VERDICTS[homework["status"]]}')
        else:
            logging.error('Переменная <homework_name> отсутствует в ответе'
                          ' API')
            raise ex.MissArgument('Переменная <homework_name> отсутствует'
                                  ' в ответе API')
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
        raise ex.MissingEnvironmentVariable(
            'Отсутствуют переменные окружения!')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    timestamp = int(time.mktime((dt.datetime.now()
                                 - dt.timedelta(days=7)).timetuple()))
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

            # Отправляем сообщение пользователю
            if STATUS_HOMEWORK != parse_status_answer:
                send_message(bot, parse_status_answer)
                STATUS_HOMEWORK = parse_status_answer

        except Exception as error:
            logging.critical(f'Сбой в работе программы: {error}')
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

# Доброго времени суток! Пишу тут, потому что так будет продуктивнее и мы
# сэкономим время. В предыдущем ревью Вы писали, что при пробрасывании ошибок
# лучше создавать ошибку из существующей, не совсем понял что Вы имели в виду,
# может быть то, что когда я пишу собственную ошибку мне лучше пользоваться
# конструкция from или Вы имели ввиду, что нужно использовать ошибку, которая
# уже по дефолту есть в питоне (т.е. не создана мной как отдельный класс нас-
# ледованный от Exceptions). И по поводу переноса строк с помощью знака "\",
# это по дефолту делает PyCharm, так что извиняюсь
# P.S. После ревью я всё это обязательно удалю, спасибо за внимание:) Ответьте
# на первый вопрос, пожалуйста.
