from signal import SIGTERM, SIGINT
from socket import socket, SHUT_RDWR

from curio import socket, task, run, SignalSet, CancelledError

class AsyncTCPCallbackServer(object):
  def __init__(self, callback, host = 'localhost', port = 25000):
    self.host = host
    self.port = port
    self.callback = callback
    self._saved_responses = {}

  async def run_client(self, sock, address):
    try:
      async with sock:
        stream = sock.as_stream()
        while True:
          data = await stream.read()
          if not data:
            break
          callback_response = await self.memoized_callback(data.decode('utf-8').strip())
          await stream.write(callback_response)
    except CancelledError:
      sock._socket.close()

  async def memoized_callback(self, data):
    if data in self._saved_responses:
      return self._saved_responses[data]
    else:
      response = await self.callback(data)
      response = bytes(str(response) + '\n', 'utf-8')
      self._saved_responses[data] = response
      return response

  async def run_server(self):
    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
      sock.bind((self.host, self.port))
      sock.listen(100)
      async with sock:
        while True:
          client_socket, client_address = await sock.accept()
          await task.spawn(self.run_graceful_client(client_socket, client_address))
          del client_socket
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

class BlockingTCPClient(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket()
        self.read_stream = self.socket.makefile()
        self.write_stream = self.socket.makefile(mode='w')
        self.socket.connect((self.host, self.port))

    def close(self):
        self.socket.shutdown(SHUT_RDWR)
        self.read_stream.close()
        self.write_stream.close()
        self.socket.close()

    def send(self, data):
        self.write_stream.write(frame)
        self.write_stream.write('\n')
        self.write_stream.flush()
        return loads(self.read_stream.readline())

if __name__ == '__main__':
  async def callback(data):
    return bytes('This is a test!\n', 'utf-8')
  AsyncTCPCallbackServer(callback = callback).run()
