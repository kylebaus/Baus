
class PlaceAck:
    def __init__(self, order_id, account, instrument, side, price, quantity):
        self.order_id = order_id
        self.account = account
        self.instrument = instrument
        self.side = side
        self.price = price
        self.quantity = quantity