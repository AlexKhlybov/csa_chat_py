import logging
import logs.config_client_log
import argparse
import sys
import os
from PyQt5.QtWidgets import QApplication

from common.variables import *
from common.errors import ServerError
from common.decos import log
from client.database import ClientDatabase
from client.transport import ClientTransport
from client.main_window import ClientMainWindow
from client.start_dialog import UserNameDialog

# Инициализация клиентского логера
logger = logging.getLogger('client')


# Парсер аргументов коммандной строки
@log
def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADDRESS, nargs='?')
    parser.add_argument('port', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-n', '--name', default=None, nargs='?')
    ns = parser.parse_args(sys.argv[1:])

    # проверим подходящий номер порта
    if not 1023 < ns.port < 65536:
        logger.critical(
            f'Попытка запуска клиента с неподходящим номером порта: {ns.port}. Допустимы адреса с 1024 до 65535. Клиент завершается.')
        exit(1)

    return ns.addr, ns.port, ns.name


def main(addr, port, name):
    # Создаём клиентокое приложение
    app = QApplication(sys.argv)

    # Если имя пользователя не было указано в командной строке то запросим его
    if not name:
        start_dialog = UserNameDialog()
        app.exec_()
        # Если пользователь ввёл имя и нажал ОК, то сохраняем ведённое и удаляем объект, инааче выходим
        if start_dialog.ok_pressed:
            name = start_dialog.name.text()
            del start_dialog
        else:
            exit(0)

    # Записываем логи
    logger.info(f'Запущен клиент с парамертами: адрес сервера: {addr} , порт: {port}, имя пользователя: {name}')

    # Создаём объект базы данных
    database = ClientDatabase(
        create_sqlite_uri(f'client_db_{name}.db3', 'client'))

    # Создаём объект - транспорт и запускаем транспортный поток
    try:
        transport = ClientTransport(port, addr, database, name)
    except ServerError as error:
        print(error.text)
        exit(1)
    transport.setDaemon(True)
    transport.start()

    # Создаём GUI
    main_window = ClientMainWindow(database, transport)
    main_window.make_connection(transport)
    main_window.setWindowTitle(f'Чат Программа alpha release - {name}')
    app.exec_()

    # Раз графическая оболочка закрылась, закрываем транспорт
    transport.transport_shutdown()
    transport.join()


# Основная функция клиента
if __name__ == '__main__':
    # Загружаем параметы коммандной строки
    addr, port, name = arg_parser()

    main(addr, port, name)

    
