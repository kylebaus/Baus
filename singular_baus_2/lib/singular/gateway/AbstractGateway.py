
class AbstractGateway:
    def __init__(self, exchange, executor, callbacks):
        self.exchange = exchange
        self.executor = executor
        self.callbacks = callbacks
    
    def place(self, order):
        pass

    def cancel(self, order_id):
        pass

    def modify(self, order):
        pass

    def subscribe_orderbook(self, instrument):
        pass

    def subscribe_trades(self, instrument):
        pass