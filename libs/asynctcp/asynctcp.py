import base64
from contextlib import suppress
from importlib import import_module
import json
import logging
from multiprocessing import cpu_count, current_process
from os import remove, environ as env
from os.path import exists
from secrets import token_bytes
from signal import SIGTERM, SIGINT
import socket
import sys
from warnings import catch_warnings, filterwarnings

from curio import (
    aside,
    CancelledError,
    Channel,
    Queue,
    run,
    SignalSet,
    socket as curiosocket,
    spawn,
    TaskError,
    TaskTimeout,
    timeout_after,
    wait,
)

from rsyslog import setup


LOGGER = logging.getLogger(__name__)


async def worker_main(
    id,
    channel,
    authkey,
    request_handler,
    search_path
):
    '''
    This task runs inside a subprocess spawned by the AsyncTcpCallbackServer.
    It creates a connection to the 'channel', receives requests via the connection,
    runs the 'request_handler' on the request, 
    sends the response back to the AsyncTcpCallbackServer via the connection.
    '''
    if search_path is not None:
        sys.path.insert(0, search_path)

    if isinstance(request_handler, str):
        module, handler_name = request_handler.rsplit('.', 1)
        handler = getattr(import_module(module), handler_name)
        current_process().name = f'{request_handler}.{id}.{current_process().pid}'
    else:
        handler = request_handler
        current_process().name = f'{request_handler.__module__}.{request_handler.__name__}.{id}.{current_process().pid}'

    setup(log_level=env['LOG_LEVEL'] if 'LOG_LEVEL' in env else 'DEBUG')

    async with await channel.connect(authkey=authkey) as connection:
        while True:
            try:
                request = await connection.recv()
                try:
                    handler_task  = await spawn(handler(request))
                    response = await handler_task.join()
                except TaskError as exc:
                    LOGGER.exception('TaskError detected in worker_main')
                    response = json.dumps(None)
                finally:
                    await connection.send(response)
            except CancelledError:
                break


class AsyncTcpCallbackServer(object):
    '''
    1) receives json as utf-8 encoded bytestream
    2) sends json object to callback as native python object (dict)
        - callback should return a string type
    3) encodes string as utf-8 encoded bytestring and sends to client
    '''
    def __init__(
        self,
        address,
        port,
        request_handler,
        memoized = True,
        buffer_size = 1 << 13,
        parallel = True,
        cpus = None,
        search_path = None,
        worker_subprocess_timeout = 5,
    ):
        '''
            address:        the address the listening socket will bind to.
            port:           the port the listening socket will bind to.
            request_handler: an importable async function handling the received request as a dict.
                            If 'parallel' is True, this can be either the dot-path to the function or the function itself.
                            You may need to provide an additional search path in 'search_path' if the handler can't be found. 
                            This usually happens if your handler is defined in a script but not in a library.
            memoized:       True is responses are to be cached. Defaults to True.
            buffer_size:    the maximum amount of data to be received at once from the client connection. Defaults to 8KB.
            parallel:       if True, handle all received requests in parallel, using a pool of processes. Defaults to True.
            cpus:           number of processes if 'parallel' is True. Defaults to None which means match the number of CPUs on the host machine.
            search_path:    path of the module containing the 'request_handler' definition. Will be prepended to sys.path when workers boot.
            worker_subprocess_timeout: timeout in seconds after which the subprocesses will be killed if no new request is queued up.
                            Defaults to 5 seconds.
        '''
        self.address = address
        self.port = port
        self.buffer_size = buffer_size
        self.memoized = memoized
        self.request_handler = request_handler
        self._saved_responses = {}
        self.parallel = parallel
        self.cpus = cpus or cpu_count()
        if parallel:
            self.requests = Queue()
            self.authkey = token_bytes()
            self.search_path = search_path
            # tag the socket path with the pid so we can run the multiple servers,
            # as is the case when running the tests while in a container that runs the official server.
            self.unix_socket_path = f'/var/run/asynctcp.server.channel.{current_process().pid}'
            self.channel = Channel(self.unix_socket_path, family=socket.AF_UNIX)
            self.subprocess_launch_request = Queue(maxsize=self.cpus)
            self.worker_subprocess_timeout = worker_subprocess_timeout

    async def run_client(self, sock, address):
        response_queue = Queue(maxsize=1) if self.parallel else None
        try:
            async with sock:
                data_as_str = ''
                while True:
                    rawdata = await sock.recv(self.buffer_size)
                    if not rawdata:
                        return
                    data_as_str += rawdata.decode('utf-8').strip()
                    try:
                        request = json.loads(data_as_str)
                    except ValueError:
                        continue
                    response = await self.memoized_handler(request, response_queue=response_queue)
                    data_as_str = ''
                    await sock.sendall(response.encode('utf-8'))
        except CancelledError:
            await sock.close()

    async def memoized_handler(self, request, response_queue=None):
        if self.memoized:
            hashable_request = str(request).strip()
            if hashable_request not in self._saved_responses:
                if response_queue:
                    await self.requests.put((response_queue, request))
                    # next available 'worker' task will put the response on the queue.
                    self._saved_responses[hashable_request] = await response_queue.get()
                    await response_queue.task_done()
                else:
                    self._saved_responses[hashable_request] = await self.request_handler(request)
            return self._saved_responses[hashable_request]
        else:
            if response_queue:
                await self.requests.put((response_queue, request))
                response = await response_queue.get()
                await response_queue.task_done()
            else:
                response = await self.request_handler(request)
            return response

    async def worker(self, id, subprocess_timeout=5):
        '''
        There is exactly one 'worker' task per subprocess.
        This is the link between one client connection and one subprocess.
        It waits for a (response_queue, request) from the 'self.requests' queue,
        sends the request to the subprocess,
        waits to receive the response and puts it in the client's response queue.

        The subprocess is started on-demand, so as not to consume CPU and memory when the server is idle.
        '''
        subprocess_task = None
        subprocess_connection = None
        subprocess_launch_response = Queue(maxsize=1) # receives the (connection, task) for a requested worker subprocess
        try:
            while True:
                if subprocess_connection:
                    try:
                        response_queue, request = await timeout_after(subprocess_timeout, self.requests.get())
                    except TaskTimeout:
                        await subprocess_task.cancel()
                        await subprocess_connection.close()
                        subprocess_connection = None
                        subprocess_task = None
                        continue
                else:
                    response_queue, request = await self.requests.get()
                    await self.subprocess_launch_request.put((id, subprocess_launch_response))
                    subprocess_connection, subprocess_task = await subprocess_launch_response.get()
                await subprocess_connection.send(request)
                response = await subprocess_connection.recv()
                await response_queue.put(response)
                await self.requests.task_done()
        except CancelledError:
            if subprocess_task:
                await subprocess_task.cancel()
            if subprocess_connection:
                await subprocess_connection.close()

    async def subprocess_launcher(self):
        '''
        Launches a subprocess whenever a 'worker' task requests it.
        '''
        async with self.channel:
            while True:
                try:
                    worker_id, response = await self.subprocess_launch_request.get()
                    subprocess_task = await aside(
                        worker_main,
                        worker_id,
                        self.channel,
                        self.authkey,
                        self.request_handler,
                        self.search_path
                    )
                    subprocess_connection = await self.channel.accept(authkey=self.authkey)
                    await response.put((subprocess_connection, subprocess_task))
                except CancelledError:
                    break

    async def run_server(self):
        try:
            if self.parallel:
                subprocess_launcher_task = await spawn(self.subprocess_launcher())
                worker_tasks = []
                for id in range(self.cpus):
                    worker_tasks.append( await spawn(self.worker(id, self.worker_subprocess_timeout)) )
            async with curiosocket.socket(curiosocket.AF_INET, curiosocket.SOCK_STREAM) as listening_socket:
                listening_socket.setsockopt(curiosocket.SOL_SOCKET, curiosocket.SO_REUSEADDR, True)
                listening_socket.bind((self.address, self.port))
                listening_socket.listen(100)
                while True:
                    client_socket, remote_address = await listening_socket.accept()
                    await spawn(self.run_graceful_client(client_socket, remote_address))
        except CancelledError:
            if self.parallel:
                await wait(worker_tasks).cancel_remaining()
                await subprocess_launcher_task.cancel()
                if exists(self.unix_socket_path):
                    remove(self.unix_socket_path)

    async def run_graceful_client(self, sock, address):
        client_task = await spawn(self.run_client(sock, address))
        await SignalSet(SIGINT, SIGTERM).wait()
        await client_task.cancel()

    async def run_graceful_server(self):
        server_task = await spawn(self.run_server())
        await SignalSet(SIGINT, SIGTERM).wait()
        await server_task.cancel()

    def run(self):
        with catch_warnings():
            filterwarnings('ignore', category=DeprecationWarning)
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
