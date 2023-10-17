import aiohttp


class HttpClient:
    def __init__(self, executor, host, timeout):
        self.executor = executor
        self.host = host
        self.timeout = timeout

    async def get(self, endpoint, header, params):
        async with aiohttp.ClientSession(headers=header) as session:
            async with session.get(self.host + "/" + endpoint, params=params, 
                                   timeout=self.timeout) as response:
                return await response.json()

    async def post(self, endpoint, header, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(self.host + "/" + endpoint, headers=header, json=data) as response:
                return await response.json()

    async def delete(self, endpoint, header):
        async with aiohttp.ClientSession() as session:
            async with session.delete(self.host + "/" + endpoint, headers=header) as response:
                return await response.json()

    async def put(self, endpoint, header, data):
        async with aiohttp.ClientSession() as session:
            async with session.put(self.host + "/" + endpoint, headers=header, json=data) as response:
                return await response.json()