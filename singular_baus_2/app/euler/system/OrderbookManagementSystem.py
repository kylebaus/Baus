import mmap
import struct

from singular.core import Orderbook, OrderbookLevel, Side
from singular.config import exchange_str_to_exchange

### TODO: maybe lift this from this file at some point

class MappedMemoryClient:
    def __init__(self, path):
        self.path = path
        self.file = open(path, mode="r", encoding="utf8")
        self.shared_memory = mmap.mmap(
            self.file.fileno(), length=0, access=mmap.ACCESS_READ
        )

    def read(self, offset, length):
        self.shared_memory.seek(offset)
        return self.shared_memory.read(length)

# This has the same interface as Orderbook

class MappedOrderbook:
    def __init__(self, mapped_memory_client, offset, data_size):
        self.mapped_memory_client = mapped_memory_client
        self.offset = offset
        self.data_size = data_size
    
    def get_data(self):
        return struct.unpack("dd", self.client.read(self.offset, self.data_size))

    def get_instrument(self):
        return None

    def get_last_update_dt(self):
        return None

    def get_bids(self):
        return None

    def get_asks(self):
        return None

    def get_best_bid_level(self):
        return OrderbookLevel(
            None,
            Side.BUY,
            struct.unpack("dd", self.mapped_memory_client.read(self.offset, self.data_size))[0],
            None
        )

    def get_best_ask_level(self):
        return OrderbookLevel(
            None,
            Side.SELL,
            struct.unpack("dd", self.mapped_memory_client.read(self.offset, self.data_size))[1],
            None
        )

class OrderbookManagementSystem:
    def __init__(self, config):
        self.config = config
        self.orderbook_map = {}
        self.orderbook_services = {}

        for service in self.config["orderbook_services"]:
            exchange = exchange_str_to_exchange(service["exchange"])
            self.orderbook_services[exchange] =\
                MappedMemoryClient(service["path"])
            offset = 0
            for symbol in service["symbols"]:
                key = (exchange, symbol)
                self.orderbook_map[key] = MappedOrderbook(
                    self.orderbook_services[exchange],
                    offset,
                    service["data_size"]
                )

                offset += 1

    def get_orderbook(self, instrument):
        key = (instrument.get_exchange(), instrument.get_external_symbol())
        return self.orderbook_map[key]

    def subscribe_orderbook(self, instrument):
        key = (instrument.get_exchange(), instrument.get_external_symbol())
        if (key in self.orderbook_map.keys()):
            # this means already subscribed/mapped
            return False
        else:
            self.orderbook_map[key] = Orderbook(instrument)
            return True

    def handle_event(self, event):
        key = (event.instrument.get_exchange(), event.instrument.get_external_symbol())
        self.orderbook_map[key].handle_event(event)