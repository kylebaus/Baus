import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import asyncio

class WebsocketSession:
    def __init__(self, host, on_read_callback, on_error_callback):
        self.host = host
        self.on_read_callback = on_read_callback
        self.on_error_callback = on_error_callback
        self.active = False

    def __await__(self):
        return self._async_init().__await__()

    def is_active(self):
        return self.active

    async def _async_init(self):
        self._conn = websockets.connect(self.host, ping_interval=20, ping_timeout=120)
        self.websocket = await self._conn.__aenter__()
        self.active = True
        return self

    async def send(self, message):
        try:
            await self.websocket.send(message)
        except (ConnectionClosedError, ConnectionClosedOK) as e:
            print(f'WebsocketClient(Session): send: Error {e.__class__.__name__}: {e}')
            raise
        except Exception as e:
            print(f"WebsocketClient(Session): send: Error {e.__class__.__name__}: {e}")

    async def receive(self):
        try:
            return await self.websocket.recv()
        except (ConnectionClosedError, ConnectionClosedOK) as e:
            print(f"WebsocketClient(Session): receive: Error {e.__class__.__name__}: {e}")
            raise
        except Exception as e:
            print(f"WebsocketClient(Session): receive: Error {e.__class__.__name__}: {e}")

    async def run(self):
        while True:
            try:
                message = await self.receive()
                self.on_read_callback(message)
            except (ConnectionClosedError, ConnectionClosedOK) as e:
                print('WebsocketClient(Session): run:', {e.__class__.__name__}, str(e),
                      'cooling off before reconnecting')
                self.active = False
                await self._conn.__aexit__()
                await asyncio.sleep(5.5)
                self.on_error_callback()
            except Exception as e:
                print("WebsocketClient(Session): run: Error", str(e))
                self.active = False
                await self._conn.__aexit__()
                self.on_error_callback()


class WebsocketClient:
    def __init__(self, executor, host, on_read_callback, on_error_callback):
        self.executor = executor
        self.host = host
        self.on_read_callback = on_read_callback
        self.on_error_callback = on_error_callback
        self.client = None
        self.active = False

    async def run(self, status):
        self.client = await WebsocketSession(self.host, self.on_read_callback, self.on_error_callback)
        self.active = True
        status.set()
        self.executor.create_task(self.client.run())

    def is_active(self):
        if self.client is None:
            return False
        else:
            return self.active

    def get_status_flag(self):
        return self.connected

    async def send(self, message):
        try:
            await self.client.send(message)
        except Exception as e:
            print("WebsocketClient: send: Error", str(e))

    async def receive(self):
        try:
            await self.client.receive()
        except Exception as e:
            print("WebsocketClient: receive: Error", str(e))
