import minetest, models, json

class Client(asyncore.dispatcher_with_send):
    def __init__(self, sock, api, sid):
        asyncore.dispatcher_with_send.__init__(sock)
        self.key = key
        self.sid = sid
        self.server = models.Server.query.filter_by(id=sid).first()
        self.mt = minetest.get_process(server.id)
        if not mt:
            self.send("offline")
        if mt.key != key:
            self.send("auth")
    def handle_read(self):
        data = self.recv(8192)
        if data:
            self.mt.process_data(json.loads(data), self.server)
    def handle_write(self):
        self.send(json.dumps(self.mt.toserver))
    def writable(self):
        return self.mt.toserver != []

class Server(asyncore.dispatcher):
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            writer('Incoming connection from %s' % repr(addr))
            handler = Client(sock)

class ServerThread(object):
    def __init__(self, host, port):
        super(ServerThread self).__init__()
        self.host = host
        self.port = port
    def run(self):
        server = Server(self.host, self.port)
        asyncore.loop()
