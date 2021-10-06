import json
import sys

import logs.config_client_log as srv_log
import logs.config_server_log as cli_log

from .errors import ReqFieldMissingError, ServerError

# метод определения модуля, источника запуска.
if sys.argv[0].find("client") == -1:
    # если не клиент то сервер!
    logger = srv_log.logger
else:
    # ну, раз не сервер, то клиент
    logger = cli_log.logger


def log(func_to_log):
    def log_saver(*args, **kwargs):
        logger.debug(
            f"Была вызвана функция {func_to_log.__name__} c параметрами {args} , {kwargs}. Вызов из модуля {func_to_log.__module__}"
        )
        ret = func_to_log(*args, **kwargs)
        return ret

    return log_saver


def try_except_wrapper(func):
    """Для методов классов с логгером"""

    def wrapper(*args, **kwargs):
        logger = args[0].logger
        try:
            return func(*args, **kwargs)
        except (json.JSONDecodeError, ValueError) as e:
            logger.critical("Не удалось декодировать полученную Json строку.")
            logger.critical(e)
            exit(1)
        except ServerError as error:
            logger.error(f"При установке соединения сервер вернул ошибку: {error.text}")
            exit(1)
        except ReqFieldMissingError as missing_error:
            logger.error(f"В ответе сервера отсутствует необходимое поле {missing_error.missing_field}")
            exit(1)
        except (ConnectionRefusedError, ConnectionError):
            logger.critical(f"Не удалось подключиться к серверу, конечный компьютер отверг запрос на подключение.")
            exit(1)
        except Exception as ex:
            logger.error(ex)
        return None

    return wrapper
