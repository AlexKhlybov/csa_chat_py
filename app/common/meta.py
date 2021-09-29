import dis


class ServerVerifier(type):
    def __init__(self, clsname, bases, clsdict):
        methods = []
        attrs = []
        for func in clsdict:
            try:
                ret = dis.get_instructions(clsdict[func])
            except TypeError:
                pass
            else:
                for i in ret:
                    if i.opname == "LOAD_GLOBAL":
                        if i.argval not in methods:
                            methods.append(i.argval)
                    if i.opname == "LOAD_ATTR":
                        if i.argval not in attrs:
                            attrs.append(i.argval)
        if "connect" in methods:
            raise TypeError('Использование метода "connect" недопустимо в серверном классе')
        super().__init__(clsname, bases, clsdict)


class ClientVerifier(type):
    def __init__(self, clsname, bases, clsdict):
        methods = []
        attrs = []
        for func in clsdict:
            try:
                ret = dis.get_instructions(clsdict[func])
            except TypeError:
                pass
            else:
                for i in ret:
                    if i.opname == "LOAD_GLOBAL":
                        if i.argval not in methods:
                            methods.append(i.argval)
                    if i.opname == "LOAD_ATTR":
                        if i.argval not in attrs:
                            attrs.append(i.argval)
        for command in ("accept", "listen"):
            if command in methods:
                raise TypeError("В классе обнаружено использование запрещённого метода")
        super().__init__(clsname, bases, clsdict)
