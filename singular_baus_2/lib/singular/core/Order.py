
class Order:
    def __init__(self, instrument, account, side, price, quantity, type):
        self.instrument = instrument
        self.account = account
        self.side = side
        self.price = price
        self.quantity = quantity
        self.type = type

    ### Interface ###

    def get_instrument(self):
        return self.instrument

    def get_account(self):
        return self.account

    def get_side(self):
        return self.side

    def get_price(self):
        return self.price

    def get_quantity(self):
        return self.quantity

    def get_type(self):
        return self.type

    def set_price(self, price):
        self.price = price

    def set_quantity(self, quantity):
        self.quantity = quantity