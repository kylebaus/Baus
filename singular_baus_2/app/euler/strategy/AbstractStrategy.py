import queue

class AbstractStrategy:
    def __init__(self, strategy_id, dispatcher, event_queue, config):
        self.strategy_id = strategy_id
        self.dispatcher = dispatcher
        self.event_queue = event_queue

    ### Strategy Manager Interface ###

    def update(self):
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self.handle_event(event)
        
        self.update_state()

    ### Strategy Inbound Interface ###

    def is_active(self, account):
        return self.dispatcher.is_active(account)
        
    def place(self, order):
        return self.dispatcher.place(self.strategy_id, order)

    def cancel(self, account, order_id):
        self.dispatcher.cancel(account, order_id)

    def modify(self, order_id, order):
        self.dispatcher.modify(self.strategy_id, order_id, order)

    def subscribe_orderbook(self, account, instrument):
        print("AbstractStrategy: subscribe_orderbook")
        self.dispatcher.subscribe_orderbook(self.strategy_id, account, instrument)

    def subscribe_trades(self, account, instrument):
        print("AbstractStrategy: subscribe_trades")
        self.dispatcher.subscribe_trades(self.strategy_id, account, instrument)

    def subscribe_fills(self, account):
        print("AbstractStrategy: subscribe_fills")
        self.dispatcher.subscribe_fills(self.strategy_id, account)

    def get_orderbook(self, instrument):
        return self.dispatcher.get_orderbook(instrument)

    def get_funding(self, account, instrument):
        return self.dispatcher.get_funding(account, instrument)

    ### Virtual Strategy Methods ###

    def update_state(self):
        pass

    def handle_event(self, event):
        pass