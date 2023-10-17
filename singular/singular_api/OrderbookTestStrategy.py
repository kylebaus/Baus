from euler.strategy import AbstractStrategy
from singular.core import Instrument, Exchange, InstrumentType, Account

class OrderbookTestStrategy(AbstractStrategy):
    def __init__(self, strategy_id, dispatcher, event_queue, config):
        super().__init__(strategy_id, dispatcher, event_queue, config)

        self.initialized = False

        self.account = Account(None, None)

        self.instrument = Instrument(
            Exchange.OKX, 
            "BTC-USD-SWAP",
            "BTC-USD-SWAP",
            None,
            None,
            1,
            1,
            1,
            1,
            InstrumentType.LINEAR_PERPETUAL,
            1
        )

        self.print_counter = 0

    def handle_event(self, event):
        pass

    def update_state(self):
        if self.initialized:
            orderbook = self.get_orderbook(self.instrument)
            bid_level = orderbook.get_best_bid_level()
            ask_level = orderbook.get_best_ask_level()
            if self.print_counter % 100000 == 0:
                print(bid_level.price, ask_level.price)
            self.print_counter += 1
        else:
            self.subscribe_orderbook(self.account, self.instrument)
            self.initialized = True