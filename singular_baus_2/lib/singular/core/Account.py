
class Account:
    def __init__(self, exchange, name):
        self.exchange = exchange
        self.name = name

    ### Interface ###
    
    def get_exchange(self):
        return self.exchange

    def get_name(self):
        return self.name