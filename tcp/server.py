from curio import run, tcp_server

class SimpleServer(object):
  def __init__(self, callback, host = 'localhost', port = 25000):
    self.host = host
    self.port = port
    self._callback = callback
    self._saved_responses = {}

  async def client(self, client, address):
    while True:
      data = await client.recv(100000)
      if not data:
        break
      response_data = await self.callback(data)
      await client.sendall(response_data)

  async def callback(self, data):
    if data in self._saved_responses:
      return self._saved_responses[data]
    else:
      response = self._callback(data)
      self._saved_responses[data] = response
      return response 

  def run(self):
    run(tcp_server(self.host, self.port, self.client))

if __name__ == '__main__':
  SimpleServer(callback = lambda foo: bytes('This is a test!\n', 'utf-8')).run()
