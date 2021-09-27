import argparse
import select
import sys
from socket import AF_INET, SOCK_STREAM, socket
from threading import Thread

from app.common.decos import try_except_wrapper
from app.common.descriptor import Port
from app.common.meta import ServerVerifier
from app.common.utils import *
from app.common.variables import *
from app.db.server_db import ServerStorage
from app.logs.config_server_log import logger


class ServerThread(Thread):
    __slots__ = ("func", "logger")

    def __init__(self, func, logger, storage):
        super().__init__()
        self.func = func
        self.logger = logger
        self.daemon = True
        self.storage = storage

    @try_except_wrapper
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
        self.__console()

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
    @try_except_wrapper
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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, nargs="?", help="Port [default=7777]")
    parser.add_argument("-a", "--addr", type=str, default=DEFAULT_IP_ADDRESS, nargs="?", help="Bind address")
    return parser.parse_args(sys.argv[1:])


def run():
    param = parse_args()

    database = ServerStorage()

    server = Server(param.addr, param.port, database)
    server.start()


if __name__ == "__main__":
    run()
