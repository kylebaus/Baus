
class Price:
    def __init__(self, account, instrument, value):
        self.account = account
        self.instrument = instrument
        self.value = value

    def get_account(self):
        return self.account

    def get_instrument(self):
        return self.instrument

    def get_value(self):
        return self.value