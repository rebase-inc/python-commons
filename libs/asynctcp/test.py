from contextlib import contextmanager
from logging import getLogger, Formatter, StreamHandler
from time import sleep, perf_counter
import json
from multiprocessing import Process, Pipe, current_process
from os.path import exists
import socket
from sys import stdout
from unittest import TestCase


from . import AsyncTcpCallbackServer, BlockingTcpClient


LOGGER = getLogger(__name__)


class ServerTest(TestCase):
    async def echojson(self, data):
        return json.dumps(data)

    def setUp(self):
        self.server = AsyncTcpCallbackServer('0.0.0.0', 9898, self.echojson, memoized=True, parallel=False)
        self.server_process = Process(target = self.server.run)
        self.server_process.start()
        sleep(0.005) # wait a bit to make sure server is ready
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


def log_to_stdout():
    root_logger = getLogger()
    root_logger.setLevel('DEBUG')
    streamingHandler = StreamHandler(stdout)
    streamingHandler.setFormatter(Formatter('%(asctime)s %(levelname)s %(processName)s %(message)s'))
    root_logger.addHandler(streamingHandler)
    return streamingHandler


@contextmanager
def server(request_handler, address='127.0.0.1', port=11111, parallel=True, cpus=None, worker_timeout=1):
    async_server = AsyncTcpCallbackServer(
        address,
        port,
        request_handler,
        memoized=False,
        parallel=parallel,
        cpus=cpus,
        worker_subprocess_timeout=worker_timeout,
    )
    def run():
        log_to_stdout()
        async_server.run()
    server_process = Process(target=run)
    server_process.start()
    sleep(.5)
    yield
    if server_process.is_alive():
        server_process.terminate()
        server_process.join()


@contextmanager
def Client(host='127.0.0.1', port=11111):
        sync_client = BlockingTcpClient(host, port)
        yield sync_client
        sync_client.close()



class Parallel(TestCase):

    def setUp(self):
        log_to_stdout()

    def tearDown(self):
        getLogger().handlers.clear()

    async def echo(request):
        return json.dumps(request)

    async def sleep_1_echo(request):
        sleep(1)
        return json.dumps(request)

    async def boom(request):
        raise Exception

    def evaluate(self, request_handler, parallel, cpus, timeout):
        data = {'foo': 'bar'}
        request = json.dumps(data)
        response = None
        with server(request_handler, parallel=parallel, cpus=cpus, worker_timeout=timeout):
            with Client() as client:
                response = client.send(request)
                sleep(timeout) # makes sure we give time for the server to shutdown its subprocesses
                response = client.send(request)
                response = client.send(request)
                response = client.send(request)
        self.assertEqual(data, response)

    def test_non_parallel(self):
        self.evaluate(Parallel.echo, False, None, 1)

    def test_parallel_all_cores(self):
        self.evaluate(Parallel.echo, True, None, 1)

    def test_parallel_1_worker(self):
        self.evaluate(Parallel.echo, True, 1, .5)

    def test_parallel_20_workers(self):
        self.evaluate(Parallel.echo, True, 20, 1)

    def test_exception_raising_handler(self):
        response = None
        with server(Parallel.boom):
            with Client() as client:
                response = client.send(json.dumps(''))
                self.assertIsNone(response)
                response = client.send(json.dumps(''))
                self.assertIsNone(response)
                response = client.send(json.dumps(''))
                self.assertIsNone(response)

    def many_connections_client(pipe, host='127.0.0.1', port=11111, connections=10, repeat_request=1, sleep_between_requests=None):
        sockets = [ socket.socket(socket.AF_INET, socket.SOCK_STREAM) for i in range(connections) ]
        LOGGER.debug('Creating %d connections', connections)
        for s in sockets:
            s.connect((host, port))
        LOGGER.debug('Done creating connections')
        while True:
            request = pipe.recv()
            if request:
                responses = []
                LOGGER.debug('Processing %d requests', repeat_request)
                for i in range(repeat_request):
                    for s in sockets:
                        s.sendall(request)
                    for s in sockets:
                        responses.append(s.recv(1024))
                    if sleep_between_requests:
                        sleep(sleep_between_requests)
                pipe.send(responses)
                LOGGER.debug('Done processing request')
            else:
                # empty string is shutdown signal
                break
        for s in sockets:
            s.close()

    def launch_client(id, connections=10, repeat=1, snooze=None):
        pipe, client_pipe = Pipe()
        process = Process(
            target=Parallel.many_connections_client,
            args=(client_pipe,),
            kwargs={
                'connections': connections,
                'repeat_request': repeat,
                'sleep_between_requests': snooze,
            },
            name='Client '+str(id)
        )
        process.start()
        return process, pipe

    def single_client(self, request, expected_response, connections=10, repeat=1, snooze=None):
        process, pipe = Parallel.launch_client(0, connections=connections, repeat=repeat, snooze=snooze)
        pipe.send(request)
        responses = pipe.recv()
        pipe.send('') # shutdown
        process.join()
        for response in responses:
            self.assertEqual(response, expected_response)

    def test_fat_client_1_connection(self):
        request = json.dumps('yo mama').encode()
        expected_response = request
        with server(Parallel.echo):
            self.single_client(request, expected_response, connections=1)

    def test_fat_client(self):
        request = json.dumps('yo mama').encode()
        expected_response = request
        with server(Parallel.echo):
            self.single_client(request, expected_response)

    def test_snooze(self):
        ''' this test is designed to exercise the on-demand subprocess shutdown
        worker_timeout is 1s but we'll wait 3s between requests, which should teardown the worker process
        and restart it.
        '''
        request = json.dumps('yo mama').encode()
        expected_response = request
        with server(Parallel.sleep_1_echo, cpus=1, worker_timeout=1):
            self.single_client(request, expected_response, connections=1, repeat=2, snooze=3)

    def many_clients(self, handler, clients, connections, repeat, cpus):
        # the whole bit: many clients, each running many connections, with server using many workers
        request = json.dumps('yo mama').encode()
        expected_response = request
        all_responses = []
        with server(handler, cpus=cpus):
            clients = [ Parallel.launch_client(i, connections=connections, repeat=repeat) for i in range(clients) ]
            start = perf_counter()
            LOGGER.debug('Start sending requests to all clients')
            for _, pipe in clients:
                pipe.send(request)
            for index, (_, pipe) in enumerate(clients):
                responses = pipe.recv()
                all_responses.append(responses)
            LOGGER.debug('Processing all requests took: %f seconds', perf_counter() - start)
            for process, pipe in clients:
                pipe.send('') # shutdown signal
                process.join()
        for responses in all_responses:
            self.assertEqual(len(responses), connections*repeat)
            for response in responses:
                self.assertEqual(response, expected_response)

    def test_many_clients_all_cores(self):
        self.many_clients(Parallel.sleep_1_echo, 4, 1, 5, None)

    def test_many_clients_1_core(self):
        self.many_clients(Parallel.sleep_1_echo, 4, 1, 5, 1)

    def test_many_clients_5_cores(self):
        self.many_clients(Parallel.sleep_1_echo, 4, 1, 5, 5)

    def test_a(self):
        # that's 900 requests per second using 2 cores on a MacBook Early 2015
        self.many_clients(Parallel.echo, 2, 2, 450, None)

            


