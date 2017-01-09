import json
import time
import socket
import base64
import logging

from contextlib import suppress
from signal import SIGTERM, SIGINT

from curio import socket as curiosocket
from curio import task, run, SignalSet, CancelledError, spawn, tcp_server, timeout_after, TaskTimeout

LOGGER = logging.getLogger()

class AsyncTcpCallbackServer(object):
    '''
    1) receives json as utf-8 encoded bytestream
    2) sends json object to callback as native python object (dict)
        - callback should return a string type
    3) encodes string as utf-8 encoded bytestring and sends to client
    '''
    def __init__(self, host, port, callback, memoized = True, buffer_size = 1 << 13):
        self.host = host
        self.port = port
        # self.encode = encode
        # self.decode = decode
        self.buffer_size = buffer_size
        self.memoized = memoized
        self.callback = callback
        self._saved_responses = {}

    async def run_client(self, sock, address):
        try:
            async with sock:
                data_as_str = ''
                while True:
                    rawdata = await sock.recv(self.buffer_size)
                    if not rawdata:
                        return
                    data_as_str += rawdata.decode('utf-8').strip()
                    try:
                        callback_response = await self.memoized_callback(json.loads(data_as_str))
                        data_as_str = ''
                        await sock.sendall(callback_response.encode('utf-8'))
                    except ValueError:
                        continue
        except CancelledError:
            try:
                sock._socket.close()
            except:
                pass

    async def memoized_callback(self, data):
        if self.memoized:
            hashable_data = str(data).strip()
            if hashable_data not in self._saved_responses:
                self._saved_responses[hashable_data] = await self.callback(data)
            return self._saved_responses[hashable_data]
        else:
            response = await self.callback(data)
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
        return run(self.run_graceful_server())

class BlockingTcpClient(object):
    def __init__(self, host = 'localhost', port = 25252, json = True, timeout = 5, buffer_size = 1 << 13):
        self.json = json
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.socket = socket.create_connection((host, port), timeout = 3)
        self.socket.settimeout(timeout)
        if not json:
            raise NotImplementedError('Non JSON version not implemented')

    def close(self):
        with suppress(Exception):
            self.socket.shutdown(socket.SHUT_RDWR)
        with suppress(Exception):
            self.socket.close()

    def read(self):
        response = ''
        while True:
            new_data = self.socket.recv(self.buffer_size).decode('utf-8')
            if not new_data:
                return
            try:
                response += new_data
                response_as_object = json.loads(response)
                break
            except ValueError:
                continue
        return response_as_object

    def send(self, data):
        self.socket.sendall(data.encode('utf-8'))
        try:
            return self.read()
        except socket.timeout as exc:
            LOGGER.error('Socket timeout trying to read from {}:{}'.format(self.host, self.port))
            raise exc

# if __name__ == '__main__':
#     async def callback(data):
#         print('returning {}'.format(str(data)))
#         return bytes(str(data), 'utf-8')
#     AsyncTcpCallbackServer(callback = callback, port = 23284, memoized = False).run()
