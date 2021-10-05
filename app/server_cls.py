import argparse
import configparser
import os
import select
import sys
from socket import AF_INET, SOCK_STREAM, socket
from threading import Lock, Thread

from icecream import ic
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QApplication, QMessageBox

from app.common.decos import try_except_wrapper
from app.common.descriptor import Port
from app.common.meta import ServerVerifier
from app.common.utils import *
from app.common.variables import *
from app.db.server_db import ServerStorage
from app.gui.server_gui import (ConfigWindow, HistoryWindow, MainWindow,
                                create_stat_model, gui_create_model)
from app.logs.config_server_log import logger

# Флаг что был подключён новый пользователь, нужен чтобы не мучать BD
# постоянными запросами на обновление
new_connection = False
conflag_lock = Lock()


class ServerThread(Thread):
    __slots__ = ("func", "logger")

    def __init__(self, func, logger, storage):
        super().__init__()
        self.func = func
        self.logger = logger
        self.daemon = True
        self.storage = storage

    # @try_except_wrapper
    def run(self):
        self.func()


class Server(metaclass=ServerVerifier):
    __slots__ = ("bind_addr", "_port", "logger", "socket", "clients", "listener", "messages", "names", "storage")

    TCP = (AF_INET, SOCK_STREAM)
    TIMEOUT = 5
    port = Port("_port")

    def __init__(self, bind_addr, port, storage):
        self.logger = logger
        self.bind_addr = bind_addr
        self.port = port
        # список клиентов , очередь сообщений
        self.clients = []
        self.messages = []
        # Словарь, содержащий имена пользователей и соответствующие им сокеты.
        self.names = dict()
        self.storage = storage

    def start(self, request_count=5):
        self.socket = socket(*self.TCP)
        self.socket.settimeout(0.5)
        self.socket.bind((self.bind_addr, self.port))
        self.logger.info(f"Порт сервера - {self.port}| адресс - {self.bind_addr}")
        self.socket.listen(request_count)
        self.listener = ServerThread(self.listen, self.logger, self.storage)
        self.listener.start()
        # self.__console()

    def print_help(self):
        txt = (
            "Поддерживаемые комманды:\n"
            "users - список известных пользователей\n"
            "connected - список подключенных пользователей\n"
            "loghist - история входов пользователя\n"
            "exit - завершение работы сервера\n"
            "help - вывод справки по поддерживаемым командамn\n"
        )
        print(txt)

    def __console(self):
        # Основной цикл сервера:
        self.print_help()
        while True:
            command = input("Введите комманду: ")
            if command == "help":
                self.print_help()
            elif command == "exit":
                break
            elif command == "users":
                for user in sorted(self.storage.user_list()):
                    print(f"Пользователь {user[0]}, последний вход: {user[1]}")
            elif command == "connected":
                for user in sorted(self.storage.active_user_list()):
                    print(
                        f"Пользователь {user[0]}, подключен: {user[1]}:{user[2]}, время установки соединения: {user[3]}"
                    )
            elif command == "loghist":
                name = input(
                    "Введите имя пользователя для просмотра истории. Для вывода всей истории, просто нажмите Enter: "
                )
                for user in sorted(self.storage.login_history(name)):
                    print(f"Пользователь: {user[0]} время входа: {user[1]}. Вход с: {user[2]}:{user[3]}")
            else:
                print("Команда не распознана.")

    def listen(self):
        self.logger.info("Запусп прослушки")
        while True:
            # Ждём подключения, если таймаут вышел, ловим исключение.
            try:
                client, addr = self.socket.accept()
            except OSError:
                pass
            except Exception as ex:
                self.logger.error(ex)
            else:
                self.logger.info(f"Установлено соединение с ПК {addr}")
                self.clients.append(client)

            recv_data_lst, send_data_lst, err_lst = [], [], []
            # Проверяем на наличие ждущих клиентов
            try:
                if self.clients:
                    recv_data_lst, send_data_lst, err_lst = select.select(self.clients, self.clients, [], self.TIMEOUT)
            except OSError:
                pass
            except Exception as ex:
                self.logger.error(ex)

            # принимаем сообщения и если ошибка, исключаем клиента.
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(get_message(client_with_message), client_with_message)
                    except:
                        ic(client_with_message.getpeername())
                        self.logger.info(f"Клиент {client_with_message.getpeername()} отключился от сервера.")
                        self.clients.remove(client_with_message)

            # Если есть сообщения, обрабатываем каждое.
            for i in self.messages:
                try:
                    self.process_message(i, send_data_lst)
                except:
                    self.logger.info(f"Связь с клиентом с именем {i[DESTINATION]} была потеряна")
                    self.clients.remove(self.names[i[DESTINATION]])
                    del self.names[i[DESTINATION]]
            self.messages.clear()

    # Обработчик сообщений от клиентов, принимает словарь - сообщение от клиента, проверяет корректность, отправляет
    # словарь-ответ в случае необходимости.
    # @try_except_wrapper
    def process_client_message(self, message, client):
        self.logger.debug(f"Разбор сообщения от клиента : {message}")
        # Если это сообщение о присутствии, принимаем и отвечаем
        if ACTION in message and message[ACTION] == PRESENCE and TIME in message and USER in message:
            # Если такой пользователь ещё не зарегистрирован, регистрируем, иначе отправляем ответ и завершаем соединение.
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                client_ip, client_port = client.getpeername()
                self.storage.user_login(message[USER][ACCOUNT_NAME], client_ip, client_port)
                send_message(client, RESPONSE_200)
            else:
                response = RESPONSE_400
                response[ERROR] = "Имя пользователя уже занято."
                send_message(client, response)
                self.clients.remove(client)
                client.close()
            return
        # Если это сообщение, то добавляем его в очередь сообщений. Ответ не требуется.
        elif (
            ACTION in message
            and message[ACTION] == MESSAGE
            and DESTINATION in message
            and TIME in message
            and SENDER in message
            and MESSAGE_TEXT in message
        ):
            self.messages.append(message)
            self.storage.process_message(message[SENDER], message[DESTINATION])
            return
        # Если клиент выходит
        elif ACTION in message and message[ACTION] == EXIT and ACCOUNT_NAME in message:
            self.storage.user_logout(message[ACCOUNT_NAME])

            self.clients.remove(self.names[ACCOUNT_NAME])
            self.names[ACCOUNT_NAME].close()
            del self.names[ACCOUNT_NAME]
            return
        # Иначе отдаём Bad request
        else:
            response = RESPONSE_400
            response[ERROR] = "Запрос некорректен."
            send_message(client, response)
            return

    # Функция адресной отправки сообщения определённому клиенту. Принимает словарь сообщение, список зарегистрированых
    # пользователей и слушающие сокеты. Ничего не возвращает.
    @try_except_wrapper
    def process_message(self, message, listen_socks):
        if message[DESTINATION] in self.names and self.names[message[DESTINATION]] in listen_socks:
            send_message(self.names[message[DESTINATION]], message)
            self.logger.info(
                f"Отправлено сообщение пользователю {message[DESTINATION]} от пользователя {message[SENDER]}."
            )
        elif message[DESTINATION] in self.names and self.names[message[DESTINATION]] not in listen_socks:
            raise ConnectionError
        else:
            self.logger.error(
                f"Пользователь {message[DESTINATION]} не зарегистрирован на сервере, отправка сообщения невозможна."
            )


def parse_args(port_default, addr_default):
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=port_default, nargs="?", help="Port [default=7777]")
    parser.add_argument("-a", "--addr", type=str, default=addr_default, nargs="?", help="Bind address")
    return parser.parse_args(sys.argv[1:])


def run(port=None, addr=None):
    # Загрузка файла конфигурации сервера
    config = configparser.ConfigParser()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    config.read(f"{dir_path}/gui/{'server.ini'}")

    # Загрузка параметров командной строки, если нет параметров, то задаём
    # значения по умоланию.
    if not port and not addr:
        param = parse_args(config["SETTINGS"]["default_port"], config["SETTINGS"]["listen_address"])

    ic(os.path.join(config["SETTINGS"]["database_path"], config["SETTINGS"]["database_file"]))
    # Инициализация базы данных
    database = ServerStorage(
        create_sqlite_uri(os.path.join(config["SETTINGS"]["database_path"], config["SETTINGS"]["database_file"]))
    )

    server = Server(addr, port, database)
    server.start()

    server_app = QApplication(sys.argv)
    main_window = MainWindow()

    main_window.statusBar().showMessage("Server Working")
    main_window.active_clients_table.setModel(gui_create_model(database))
    main_window.active_clients_table.resizeColumnsToContents()
    main_window.active_clients_table.resizeRowsToContents()

    # Функция обновляющяя список подключённых, проверяет флаг подключения, и
    # если надо обновляет список
    def list_update():
        global new_connection
        if new_connection:
            main_window.active_clients_table.setModel(gui_create_model(database))
            main_window.active_clients_table.resizeColumnsToContents()
            main_window.active_clients_table.resizeRowsToContents()
            with conflag_lock:
                new_connection = False

    # Функция создающяя окно со статистикой клиентов
    def show_statistics():
        global stat_window
        stat_window = HistoryWindow()
        stat_window.history_table.setModel(create_stat_model(database))
        stat_window.history_table.resizeColumnsToContents()
        stat_window.history_table.resizeRowsToContents()
        stat_window.show()

    # Функция создающяя окно с настройками сервера.
    def server_config():
        global config_window
        # Создаём окно и заносим в него текущие параметры
        config_window = ConfigWindow()
        config_window.db_path.insert(config["SETTINGS"]["Database_path"])
        config_window.db_file.insert(config["SETTINGS"]["Database_file"])
        config_window.port.insert(config["SETTINGS"]["Default_port"])
        config_window.ip.insert(config["SETTINGS"]["Listen_Address"])
        config_window.save_btn.clicked.connect(save_server_config)

    # Функция сохранения настроек
    def save_server_config():
        global config_window
        message = QMessageBox()
        config["SETTINGS"]["Database_path"] = config_window.db_path.text()
        config["SETTINGS"]["Database_file"] = config_window.db_file.text()
        try:
            port = int(config_window.port.text())
        except ValueError:
            message.warning(config_window, "Ошибка", "Порт должен быть числом")
        else:
            config["SETTINGS"]["Listen_Address"] = config_window.ip.text()
            if 1023 < port < 65536:
                config["SETTINGS"]["Default_port"] = str(port)
                print(port)
                with open("server.ini", "w") as conf:
                    config.write(conf)
                    message.information(config_window, "OK", "Настройки успешно сохранены!")
            else:
                message.warning(config_window, "Ошибка", "Порт должен быть от 1024 до 65536")

    # Таймер, обновляющий список клиентов 1 раз в секунду
    timer = QTimer()
    timer.timeout.connect(list_update)
    timer.start(1000)

    # Связываем кнопки с процедурами
    main_window.refresh_button.triggered.connect(list_update)
    main_window.show_history_button.triggered.connect(show_statistics)
    main_window.config_btn.triggered.connect(server_config)

    # Запускаем GUI
    server_app.exec_()


if __name__ == "__main__":
    run()
