import websockets

class WebsocketServer:
    def __init__(self, executor, host, port, on_read_callback):
        self.executor = executor
        self.host = host
        self.port = port
        self.on_read_callback = on_read_callback

    async def handle(self, websocket, path):
        try:
            message = await websocket.recv()
            self.on_read_callback(message)
            await self.handle(websocket, path)
        except:
            print("WebsocketServer: client disconnect")

    async def run(self):
        await websockets.serve(self.handle, self.host, self.port)
