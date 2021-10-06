import datetime

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, MetaData,
                        String, Table, create_engine)
from sqlalchemy.orm import mapper, sessionmaker
from sqlalchemy.sql.functions import user

from common.variables import *
from logs.config_server_log import logger

from icecream import ic


class ServerStorage:
    class AllUsers:
        def __init__(self, username):
            self.name = username
            self.last_login = datetime.datetime.now()
            self.id = None

    class ActiveUsers:
        def __init__(self, user_id, ip_address, port, login_time):
            self.user = user_id
            self.ip_address = ip_address
            self.port = port
            self.login_time = login_time
            self.id = None

    class LoginHistory:
        def __init__(self, name, date, ip, port):
            self.id = None
            self.name = name
            self.date_time = date
            self.ip = ip
            self.port = port

    class UsersContacts:
        def __init__(self, user, contact):
            self.id = None
            self.user = user
            self.contact = contact

    class UsersHistory:
        def __init__(self, user):
            self.id = None
            self.user = user
            self.sent = 0
            self.accepted = 0

    def __init__(self, path):
        from icecream import ic

        self.database_engine = create_engine(path, echo=False, pool_recycle=7200,
                                             connect_args={'check_same_thread': False})
        self.metadata = MetaData()

        user_table = Table(
            "Users",
            self.metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String, unique=True),
            Column("last_login", DateTime),
        )

        acitve_user_table = Table(
            "Active_user",
            self.metadata,
            Column("id", Integer, primary_key=True),
            Column("user", ForeignKey("Users.id")),
            Column("ip_address", String),
            Column("port", Integer),
            Column("login_time", DateTime),
        )

        user_login_history = Table(
            "Login_history",
            self.metadata,
            Column("id", Integer, primary_key=True),
            Column("name", ForeignKey("Users.id")),
            Column("date_time", DateTime),
            Column("ip", String),
            Column("port", Integer),
        )

        contacts = Table(
            "Contacts",
            self.metadata,
            Column("id", Integer, primary_key=True),
            Column("user", ForeignKey("Users.id")),
            Column("contact", ForeignKey("Users.id")),
        )

        users_history_table = Table(
            "History",
            self.metadata,
            Column("id", Integer, primary_key=True),
            Column("user", ForeignKey("Users.id")),
            Column("sent", Integer),
            Column("accepted", Integer),
        )

        self.metadata.create_all(self.database_engine)

        mapper(self.AllUsers, user_table)
        mapper(self.ActiveUsers, acitve_user_table)
        mapper(self.LoginHistory, user_login_history)
        mapper(self.UsersContacts, contacts)
        mapper(self.UsersHistory, users_history_table)

        Session = sessionmaker(bind=self.database_engine)
        self.session = Session()

        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    def user_login(self, username, ip_address, port):
        rez = self.session.query(self.AllUsers).filter_by(name=username)
        if rez.count():
            user = rez.first()
            user.last_login = datetime.datetime.now()
        else:
            user = self.AllUsers(username)
            self.session.add(user)
            self.session.commit()

        new_active_user = self.ActiveUsers(user.id, ip_address, port, datetime.datetime.now())
        self.session.add(new_active_user)

        history = self.LoginHistory(user.id, datetime.datetime.now(), ip_address, port)
        self.session.add(history)

        self.session.commit()

    def user_logout(self, username):
        user = self.session.query(self.AllUsers).filter_by(user=username).first()
        self.session.query(self.ActiveUsers).fiter_by(user=user.id).delete()
        self.session.commit()

    # Функция фиксирует передачу сообщения и делает соответствующие отметки в БД
    def process_message(self, sender, recipient):
        # Получаем ID отправителя и получателя
        sender = self.session.query(self.AllUsers).filter_by(name=sender).first().id
        recipient = self.session.query(self.AllUsers).filter_by(name=recipient).first().id
        # Запрашиваем строки из истории и увеличиваем счётчики
        sender_row = self.session.query(self.UsersHistory).filter_by(user=sender).first()
        if not sender_row:
            sender_row = self.UsersHistory(user=user)
        sender_row.sent += 1
        recipient_row = self.session.query(self.UsersHistory).filter_by(user=recipient).first()
        if not recipient_row:
            recipient_row = self.UsersHistory(user=user)
        recipient_row.accepted += 1

        self.session.commit()

    # Функция добавляет контакт для пользователя.
    def add_contact(self, user, contact):
        # Получаем ID пользователей
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()

        # Проверяем что не дубль и что контакт может существовать (полю пользователь мы доверяем)
        if not contact or self.session.query(self.UsersContacts).filter_by(user=user.id, contact=contact.id).count():
            return

        # Создаём объект и заносим его в базу
        contact_row = self.UsersContacts(user.id, contact.id)
        self.session.add(contact_row)
        self.session.commit()

    # Функция удаляет контакт из базы данных
    def remove_contact(self, user, contact):
        # Получаем ID пользователей
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()

        # Проверяем что контакт может существовать (полю пользователь мы доверяем)
        if not contact:
            return

        # Удаляем требуемое
        print(
            self.session.query(self.UsersContacts)
            .filter(self.UsersContacts.user == user.id, self.UsersContacts.contact == contact.id)
            .delete()
        )
        self.session.commit()

    def user_list(self):
        query = self.session.query(
            self.AllUsers.name,
            self.AllUsers.last_login,
        )
        return query.all()

    def active_user_list(self):
        query = self.session.query(
            self.AllUsers.name, self.ActiveUsers.ip_address, self.ActiveUsers.port, self.ActiveUsers.login_time
        ).join(self.AllUsers)
        print(f"Выводим {query.all()}")
        return query.all()

    def login_history(self, username=None):
        query = self.session.query(
            self.AllUsers.name, self.LoginHistory.date_time, self.LoginHistory.ip, self.LoginHistory.port
        ).join(self.AllUsers)
        if username:
            query = query.filter(self.AllUsers.name == username)
        return query.all()

        # Функция возвращает список контактов пользователя.

    def get_contacts(self, username):
        # Запрашивааем указанного пользователя
        user = self.session.query(self.AllUsers).filter_by(name=username).one()

        # Запрашиваем его список контактов
        query = (
            self.session.query(self.UsersContacts, self.AllUsers.name)
            .filter_by(user=user.id)
            .join(self.AllUsers, self.UsersContacts.contact == self.AllUsers.id)
        )

        # выбираем только имена пользователей и возвращаем их.
        return [contact[1] for contact in query.all()]

    # Функция возвращает количество переданных и полученных сообщений
    def message_history(self):
        query = self.session.query(
            self.AllUsers.name, self.AllUsers.last_login, self.UsersHistory.sent, self.UsersHistory.accepted
        ).join(self.AllUsers)
        # Возвращаем список кортежей
        return query.all()


if __name__ == "__main__":
    test_db = ServerStorage()
    test_db.user_login("client_1", "192.168.1.4", 8888)
    test_db.user_login("client_2", "192.168.1.5", 7777)

    test_db.user_logout("client_1")

    test_db.login_history("client_1")
