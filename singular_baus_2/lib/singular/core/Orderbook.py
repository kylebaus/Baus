from ..event.TopOfBookUpdate import TopOfBookUpdate

class Orderbook:
    def __init__(self, instrument):
        self.instrument = instrument
        self.last_update_dt = None
        self.bids = {}
        self.asks = {}
        self.best_bid_level = None
        self.best_ask_level = None

    ### Interface ###

    def get_instrument(self):
        return self.instrument

    def get_last_update_dt(self):
        return self.last_update_dt

    def get_bids(self):
        return self.bids

    def get_asks(self):
        return self.asks

    def get_best_bid_level(self):
        return self.best_bid_level

    def get_best_ask_level(self):
        return self.best_ask_level

    ### Handlers ###

    def handle_event(self, event):
        if type(event) == TopOfBookUpdate:
            self.last_update_dt = event.update_dt
            self.best_bid_level = event.best_bid
            self.best_ask_level = event.best_ask
