
class Position:
    def __init__(self, account, instrument, amount):
        self.account = account
        self.instrument = instrument
        self.amount = amount

    def get_account(self):
        return self.account

    def get_instrument(self):
        return self.instrument

    def get_amount(self):
        return self.amount