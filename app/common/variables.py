import logging
from os.path import abspath, dirname, join

# Порт поумолчанию для сетевого ваимодействия
DEFAULT_PORT = 7777
# IP адрес по умолчанию для подключения клиента
DEFAULT_IP_ADDRESS = "127.0.0.1"
# "Сервер по умолчанию"
DEFAULT_SERVER = "server"
# Максимальная очередь подключений
MAX_CONNECTIONS = 5
# Максимальная длинна сообщения в байтах
MAX_PACKAGE_LENGTH = 1024
# Кодировка проекта
ENCODING = "utf-8"
# Текущий уровень логирования
LOGGING_LEVEL = logging.DEBUG

BASEDIR = abspath(dirname(__file__))


def create_sqlite_uri(db_name):
    return "sqlite:///" + join(BASEDIR, db_name)


# База данных для хранения данных сервера:
SERVER_DATABASE = create_sqlite_uri("../db/server_data.db3")


# Прококол JIM основные ключи:
ACTION = "action"
TIME = "time"
USER = "user"
ACCOUNT_NAME = "account_name"
SENDER = "from"
DESTINATION = "to"

# Прочие ключи, используемые в протоколе
PRESENCE = "presence"
RESPONSE = "response"
ERROR = "error"
MESSAGE = "message"
MESSAGE_TEXT = "mess_text"
EXIT = "exit"

# Словари - ответы:
# 200
RESPONSE_200 = {RESPONSE: 200}
# 400
RESPONSE_400 = {RESPONSE: 400, ERROR: None}
