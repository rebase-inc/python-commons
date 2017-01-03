import time
import json
import curio
import socket
import unittest
import multiprocessing

from . import AsyncTcpCallbackServer, BlockingTcpClient

class ServerTest(unittest.TestCase):
    async def echojson(self, data):
        return json.dumps(data)

    def setUp(self):
        self.server = AsyncTcpCallbackServer('0.0.0.0', 9898, self.echojson, memoized = True)
        self.server_process = multiprocessing.Process(target = self.server.run)
        self.server_process.start()
        time.sleep(0.005) # wait a bit to make sure server is ready
        self.client = BlockingTcpClient('localhost', 9898, timeout = 0.5)

    def test_echo(self):
        data = { 'foo': 'bar' }
        response = self.client.send(json.dumps(data))
        self.assertEqual(data, response)

    def test_invalid_json(self):
        invalid_json = '{"foo":"ba}'
        with self.assertRaises(socket.timeout):
            self.client.send(invalid_json)

    def test_package_split(self):
        data = { 'foo': 'bar' }
        first_half = json.dumps(data)[0:5]
        second_half = json.dumps(data)[5:]
        self.client.write_stream.write(first_half.encode('utf-8'))
        self.client.write_stream.flush()
        response = self.client.send(second_half)
        self.assertEqual(data, response)

    def tearDown(self):
        self.server_process.terminate()
        self.client.close()
