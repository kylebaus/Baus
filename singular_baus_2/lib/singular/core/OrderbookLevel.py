
class OrderbookLevel:
    def __init__(self, instrument, side, price, quantity):
        self.instrument = instrument
        self.side = side
        self.price = price
        self.quantity = quantity

### Interface ###
    
    def get_instrument(self):
        return self.instrument

    def get_side(self):
        return self.side

    def get_price(self):
        return self.price

    def get_quantity(self):
        return self.quantity