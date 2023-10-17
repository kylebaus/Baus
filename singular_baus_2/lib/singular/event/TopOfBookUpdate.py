
class TopOfBookUpdate:
    def __init__(self, instrument, update_dt, best_bid, best_ask):
        self.instrument = instrument
        self.update_dt = update_dt
        self.best_bid = best_bid
        self.best_ask = best_ask
