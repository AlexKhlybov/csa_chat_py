import sys
import json
# import app.logs.config_server_log
# import app.logs.config_client_log
import logging


# метод определения модуля, источника запуска.
if sys.argv[0].find('client') == -1:
    #если не клиент то сервер!
    logger = logging.getLogger('server')
else:
    # ну, раз не сервер, то клиент
    logger = logging.getLogger('client')


def log(func_to_log):
    def log_saver(*args , **kwargs):
        logger.debug(f'Была вызвана функция {func_to_log.__name__} c параметрами {args} , {kwargs}. Вызов из модуля {func_to_log.__module__}')
        ret = func_to_log(*args , **kwargs)
        return ret
    return log_saver


def try_except_wrapper(func):
    """ Для методов классов с логгером """
    def wrapper(*args, **kwargs):
        logger = args[0].logger
        try:
            return func(*args, **kwargs)
        except (json.JSONDecodeError, ValueError) as e:
            logger.critical('Некорректный запрос / json')
            logger.critical(e)
        except ConnectionRefusedError:
            logger.error('Сервер недоступен')
        except ConnectionError as e:
            logger.error('Ошибка сервера')
        except Exception as ex:
            logger.error(ex)
        return None
    return wrapper
    