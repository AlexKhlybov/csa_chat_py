import argparse

from app.client_cls import Client
from app.common.variables import (DEFAULT_IP_ADDRESS, DEFAULT_PORT,
                                  DEFAULT_SERVER)
from app.db.server_db import ServerStorage
from app.server_cls import Server


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--type", type=str, default=DEFAULT_SERVER)
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("-a", "--addr", type=str, default=DEFAULT_IP_ADDRESS)
    parser.add_argument("-n", "--name", type=str, default=None)
    return parser


def start():
    parser = parse_args()
    namespace = parser.parse_args()
    return namespace


if __name__ == "__main__":
    ns = start()
    if ns.type == "server":
        db = ServerStorage()
        server = Server(ns.addr, ns.port, db)
        server.start()
    elif ns.type == "client":
        client = Client(ns.addr, ns.port, ns.name)
        client.start()
