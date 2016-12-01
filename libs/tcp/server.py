from signal import SIGTERM, SIGINT

import curio
from curio import socket, task, run

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
          data = await stream.readline()
          if not data:
            break
          callback_response = await self.callback(data)
          await stream.write(callback_response)
    except curio.CancelledError:
      sock._socket.close()

  async def memoized_callback(self, data):
    if data in self._saved_responses:
      return self._saved_responses[data]
    else:
      response = self._callback(data)
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
    except curio.CancelledError:
      sock._socket.close()

  async def run_graceful_client(self, sock, address):
    client_task = await task.spawn(self.run_client(sock, address))
    await curio.SignalSet(SIGINT, SIGTERM).wait()
    await client_task.cancel()

  async def run_graceful_server(self):
    server_task = await task.spawn(self.run_server())
    await curio.SignalSet(SIGINT, SIGTERM).wait()
    await server_task.cancel()

  def run(self):
    run(self.run_graceful_server())

if __name__ == '__main__':
  async def callback(data):
    return bytes('This is a test!\n', 'utf-8')
  AsyncTCPCallbackServer(callback = callback).run()
