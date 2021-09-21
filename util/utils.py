"""
1.Написать функцию host_ping(), в которой с помощью утилиты ping будет
проверяться доступность сетевых узлов.Аргументом функции является список,
    в котором каждый сетевой узел должен быть представлен именем хоста
	или ip-адресом. В функции необходимо перебирать ip-адреса и проверять
	их доступность с выводом соответствующего сообщения
	(«Узел доступен», «Узел недоступен»). При этом ip-адрес сетевого узла
	должен создаваться с помощью функции ip_address().
2.Написать функцию host_range_ping() для перебора ip-адресов из заданного
    диапазона. Меняться должен только последний октет каждого адреса.
    По результатам проверки должно выводиться соответствующее сообщение.
3.Написать функцию host_range_ping_tab(), возможности которой основаны
    на функции из примера 2. Но в данном случае результат должен быть
    итоговым по всем ip-адресам, представленным в табличном формате
    (использовать модуль tabulate). Таблица должна состоять из двух
    колонок и выглядеть примерно так:
	Reachable
	-------------
	10.0.0.1
	10.0.0.2
	Unreachable
	-------------
	10.0.0.3
	10.0.0.4
"""
import ipaddress
import os
import socket
import subprocess

from tabulate import tabulate

lst_ip = ["127.0.0.1", "192.168.0.1", "mail.ru", "google.mon", "telegram.org", 2130706433]


def ip_address(host):
    try:
        if type(host) in (int, str):
            check = str(ipaddress.ip_address(host))
        else:
            return False
    except ValueError:
        try:
            check = socket.gethostbyname(host)
        except socket.gaierror:
            return False
    return check


def host_ping(lst):
    result = []
    for host in lst:
        verified_ip = ip_address(host)
        if verified_ip:
            with open(os.devnull, "w") as DNULL:
                response = subprocess.call(["ping", "-c", "2", "-W", "2", verified_ip], stdout=DNULL)
            if response == 0:
                result.append(("Доступен", str(host), f"[{verified_ip}]"))
                continue
        result.append(("Не доступен", str(host), f'[{verified_ip if verified_ip else "Не определён"}]'))
    return result


def host_range_ping(network):
    try:
        hosts = list(map(str, ipaddress.ip_network(network).hosts()))
    except ValueError as e:
        print(e)
    else:
        count = 255
        for host in host_ping(hosts):
            if not count:
                break
            count -= 1
            print(f"{host[0].ljust(15)} {host[1].ljust(15)} {host[2]}")


def host_range_ping_tab(network):
    table = [("Доступные", "Недоступные")]
    sort = [[], []]
    try:
        hosts = list(map(str, ipaddress.ip_network(network).hosts()))
    except ValueError as e:
        print(e)
    else:
        result = host_ping(hosts)
        for host in result:
            if len(host[0]) == 8:
                sort[0].append(f"{host[1].ljust(15)}")
            else:
                sort[1].append(f"{host[1].ljust(15)}")
        table.extend(list(zip(*sort)))
        if len(sort[0]) > len(sort[1]):
            for item in sort[0][len(sort[1]) :]:
                table.append((item, None))
        elif len(sort[0]) < len(sort[1]):
            for item in sort[1][len(sort[0]) :]:
                table.append((None, item))
        print(tabulate(table, headers="firstrow", stralign="center", tablefmt="grid"))


print("\nЗадача №1:", end="\n")
for i in host_ping(lst_ip):
    print(f"{i[0].ljust(15)} {i[1].ljust(15)} {i[2]}")


print("\nЗадача №2:", end="\n")
host_range_ping("192.168.0.128/29")


print("\nЗадача №3:", end="\n")
host_range_ping_tab("192.168.0.128/29")
