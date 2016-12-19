from signal import SIGTERM, SIGINT
from socket import socket, SHUT_RDWR
from json import loads
import base64

import logging
LOGGER = logging.getLogger(__name__)

from curio import socket as curiosocket

from curio import task, run, SignalSet, CancelledError, spawn, tcp_server

class AsyncTCPCallbackServer(object):
    def __init__(self, callback, host = 'localhost', port = 25000, encode = lambda d: d.encode('utf-8'), decode = lambda d: d.decode()):
        self.host = host
        self.port = port
        self.encode = encode
        self.decode = decode
        self.callback = callback
        self._saved_responses = {}

    async def run_client(self, sock, address):
        try:
            async with sock:
                stream = sock.as_stream()
                while True:
                    data = await stream.readline()
                    if not data:
                        break
                    try:
                        callback_response = await self.memoized_callback(self.decode(data.strip()))
                    except Exception:
                        callback_response = ''
                    await stream.write(self.encode(callback_response))
        except CancelledError:
            sock._socket.close()

    async def memoized_callback(self, data):
        if data in self._saved_responses:
            return self._saved_responses[data]
        else:
            response = await self.callback(data)
            self._saved_responses[data] = response
            return response

    async def run_server(self):
        try:
            sock = curiosocket.socket(curiosocket.AF_INET, curiosocket.SOCK_STREAM)
            sock.setsockopt(curiosocket.SOL_SOCKET, curiosocket.SO_REUSEADDR, True)
            sock.bind((self.host, self.port))
            sock.listen(100)
            async with sock:
                while True:
                    client, address = await sock.accept()
                    await task.spawn(self.run_graceful_client(client, address))
                    del client

        except CancelledError:
            sock._socket.close()

    async def run_graceful_client(self, sock, address):
        client_task = await task.spawn(self.run_client(sock, address))
        await SignalSet(SIGINT, SIGTERM).wait()
        await client_task.cancel()

    async def run_graceful_server(self):
        server_task = await task.spawn(self.run_server())
        await SignalSet(SIGINT, SIGTERM).wait()
        await server_task.cancel()

    def run(self):
        run(self.run_graceful_server())

def run_simple_tcp_server(host, port, callback, encode, decode):
    async def simple_callback_client(client, addr):
        while True:
            message_size = await client.recv(32)
            data = await client.recv(int(message_size))
            if not data:
                break
            try:
                callback_response = await callback(decode(data.strip()))
            except Exception:
                LOGGER.exception('Unhandled callback exception')
                callback_response = ''
            await client.send(encode(callback_response))
    run(tcp_server(host, port, simple_callback_client))

class BlockingTCPClient(object):
    def __init__(self, host = 'localhost', port = 25252, encode = lambda d: d, decode = lambda d: d):
        self.socket = socket()
        self.encode = encode
        self.decode = decode

        self.read_stream = self.socket.makefile(mode = 'rb')
        self.write_stream = self.socket.makefile(mode = 'wb')

        self.socket.connect((host, port))

    def close(self):
        self.socket.shutdown(SHUT_RDWR)
        self.socket.close()

    def send(self, data):
        self.write_stream.write(self.encode(data))
        self.write_stream.flush()
        return self.decode(self.socket.recv(10000))

if __name__ == '__main__':
    async def callback(data):
      print('DATA IS "{}"'.format(str(data)))
      return data
    AsyncTCPCallbackServer(callback = callback).run()
    # client = BlockingTCPClient('dev', 25252, encode = base64.b64encode, decode = lambda data: data.decode())
    # result = client.send('\n'.encode('utf-8'))
    # print(result)
    # async def callback(data):
    #     return 'this is a test!'
    # run_simple_tcp_server('localhost', 29292, callback, encode = lambda d: d.encode('utf-8'), decode = lambda d: d)
