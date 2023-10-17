# Singular
from singular.gateway import MultiprocessingGateway

from singular.config import exchange_str_to_exchange
from singular.core import Exchange

class GatewayManagementSystem:
    def __init__(self, config, executor, callbacks): 
        self.config = config
        self.executor = executor
        self.callbacks = callbacks
        self.gateway_map = {}

        for gateway in self.config["gateways"]:
            self.register_gateway(gateway)

    def register_gateway(self, config):
        exchange = exchange_str_to_exchange(config["account"]["exchange"])
        key = (exchange, config["account"]["name"])
        self.gateway_map[key] = MultiprocessingGateway(self.callbacks, config)

    def run(self):
        for gateway in self.gateway_map.values():
            gateway.run()

    def is_active(self, account):
        return self.gateway_map[(account.get_exchange(), account.get_name())].is_active()

    def place(self, order_id, order):
        self.gateway_map[(order.account.get_exchange(), order.account.get_name())].place(order_id, order)
        
    def cancel(self, account, order_id):
        self.gateway_map[(account.get_exchange(), account.get_name())].cancel(order_id)

    def modify(self, order_id, order):
        self.gateway_map[(order.account.get_exchange(), order.account.get_name())].modify(order_id, order)

    def subscribe_orderbook(self, account, instrument):
        self.gateway_map[(account.get_exchange(), account.get_name())].subscribe_orderbook(instrument)

    def subscribe_fills(self, account):
        self.gateway_map[(account.get_exchange(), account.get_name())].subscribe_fills()

    def subscribe_trades(self, account, instrument):
        self.gateway_map[(account.get_exchange(), account.get_name())].subscribe_trades(instrument)

    def get_funding(self, account, instrument):
        self.gateway_map[(account.get_exchange(), account.get_name())].get_funding(instrument)
