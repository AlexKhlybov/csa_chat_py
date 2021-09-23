import argparse
import json
import time
from socket import AF_INET, SOCK_STREAM, socket
from threading import Thread

from app.common.decos import log, try_except_wrapper
from app.common.errors import (IncorrectDataRecivedError, ReqFieldMissingError,
                               ServerError)
from app.common.utils import *
from app.common.variables import *
from app.logs.config_client_log import logger


class ClientThread(Thread):
    __slots__ = ("func", "logger", "sock", "name")

    def __init__(self, func, logger, sock, name):
        super().__init__()
        self.func = func
        self.logger = logger
        self.daemon = True
        self.sock = sock
        self.name = name

    @try_except_wrapper
    def run(self):
        self.func(self.sock, self.name)


# Функция выводящяя справку по использованию.
def print_help():
    txt = (
        "=================HELPER===================\n"
        "Поддерживаемые команды:\n"
        "message - отправить сообщение. Кому и текст будет запрошены отдельно.\n"
        "help - вывести подсказки по командам\n"
        "exit - выход из программы\n"
    )
    print(txt)


class Client:
    __slots__ = ("addr", "port", "name", "logger", "socket", "connected", "listener", "sender", "user_interface")

    TCP = (AF_INET, SOCK_STREAM)
    # addr = Addr('_addr')
    # port = Port('_port')

    def __init__(self, addr, port, name):
        # Сообщаем о запуске
        print("Консольный месседжер. Клиентский модуль.")
        self.logger = logger
        self.addr = addr
        self.port = port
        self.name = name
        if not self.name:
            self.name = input("Введите имя пользователя: ")
        self.logger.info(
            f"Запущен клиент с парамертами: адрес сервера: {self.addr} , порт: {self.port}, имя пользователя: {self.name}"
        )
        self.connected = False

    def start(self):
        self.socket = socket(*self.TCP)
        self.connect()

    @try_except_wrapper
    def connect(self):
        self.socket.connect((self.addr, self.port))
        self.connected = True
        send_message(self.socket, self.create_presence())
        answer = self.process_response_ans(get_message(self.socket))
        self.logger.info(f"Установлено соединение с сервером. Ответ сервера: {answer}")
        print(f"Установлено соединение с сервером.")

        # Запускаем клиенский процесс приёма сообщний
        self.listener = ClientThread(self.message_from_server, self.logger, self.socket, self.name)
        self.listener.start()

        # Затем запускаем отправку сообщений и взаимодействие с пользователем.
        self.user_interface = ClientThread(self.user_interactive, self.logger, self.socket, self.name)
        self.user_interface.start()
        self.logger.debug("Запущены процессы")

        # Watchdog основной цикл, если один из потоков завершён, то значит или потеряно соединение или пользователь
        # ввёл exit. Поскольку все события обработываются в потоках, достаточно просто завершить цикл.
        while True:
            time.sleep(1)
            if self.listener.is_alive() and self.user_interface.is_alive():
                continue
            break

    @log
    # Функция создаёт словарь с сообщением о выходе.
    def create_exit_message(self, account_name):
        return {ACTION: EXIT, TIME: time.time(), ACCOUNT_NAME: account_name}

    @log
    # Функция запрашивает кому отправить сообщение и само сообщение, и отправляет полученные данные на сервер.
    def create_message(self, sock, account_name="Guest"):
        to = input("Введите получателя сообщения: ")
        message = input("Введите сообщение для отправки: ")
        message_dict = {
            ACTION: MESSAGE,
            SENDER: account_name,
            DESTINATION: to,
            TIME: time.time(),
            MESSAGE_TEXT: message,
        }
        self.logger.debug(f"Сформирован словарь сообщения: {message_dict}")
        try:
            send_message(sock, message_dict)
            self.logger.info(f"Отправлено сообщение для пользователя {to}")
        except:
            self.logger.critical("Потеряно соединение с сервером.")
            exit(1)

    @log
    # Функция взаимодействия с пользователем, запрашивает команды, отправляет сообщения
    def user_interactive(self, sock, username):
        print_help()
        while True:
            command = input("Введите команду: ")
            if command == "message":
                self.create_message(sock, username)
            elif command == "help":
                print_help()
            elif command == "exit":
                send_message(sock, self.create_exit_message(username))
                print("Завершение соединения.")
                self.logger.info("Завершение работы по команде пользователя.")
                # Задержка неоходима, чтобы успело уйти сообщение о выходе
                time.sleep(0.5)
                break
            else:
                print("Команда не распознана, попробуйте снова. help - вывести поддерживаемые команды.")

    @log
    # Функция генерирует запрос о присутствии клиента
    def create_presence(self):
        out = {
            ACTION: PRESENCE,
            TIME: time.time(),
            USER: {
                ACCOUNT_NAME: self.name,
            },
        }
        self.logger.debug(f"Сформировано {PRESENCE} сообщение для пользователя {self.name}")
        return out

    @log
    # Функция разбирает ответ сервера на сообщение о присутствии, возращает 200 если все ОК
    # или генерирует исключение при ошибке.
    def process_response_ans(self, message):
        self.logger.debug(f"Разбор приветственного сообщения от сервера: {message}")
        if RESPONSE in message:
            if message[RESPONSE] == 200:
                return "200 : OK"
            elif message[RESPONSE] == 400:
                raise ServerError(f"400 : {message[ERROR]}")
        raise ReqFieldMissingError(RESPONSE)

    @log
    # Функция - обработчик сообщений других пользователей, поступающих с сервера.
    def message_from_server(self, sock, my_username):
        while True:
            try:
                message = get_message(sock)
                if (
                    ACTION in message
                    and message[ACTION] == MESSAGE
                    and SENDER in message
                    and DESTINATION in message
                    and MESSAGE_TEXT in message
                    and message[DESTINATION] == my_username
                ):
                    print(f"\nПолучено сообщение от пользователя {message[SENDER]}:\n{message[MESSAGE_TEXT]}")
                    self.logger.info(f"Получено сообщение от пользователя {message[SENDER]}:\n{message[MESSAGE_TEXT]}")
                else:
                    self.logger.error(f"Получено некорректное сообщение с сервера: {message}")
            except IncorrectDataRecivedError:
                self.logger.error(f"Не удалось декодировать полученное сообщение.")
            except (OSError, ConnectionError, ConnectionAbortedError, ConnectionResetError, json.JSONDecodeError):
                self.logger.critical(f"Потеряно соединение с сервером.")
                break


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "addr", nargs="?", type=str, default=DEFAULT_IP_ADDRESS, help="Server address [default=localhost]"
    )
    parser.add_argument("port", nargs="?", type=int, default=DEFAULT_PORT, help="Server port [default=7777]")
    return parser


def run():
    args = parse_args()
    client = Client(args.addr, args.port)
    client.start()


if __name__ == "__main__":
    run()
