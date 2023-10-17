
class Transfer:
    def __init__(self, timestamp, id, sending_account, receiving_account, currency, amount):
        self.timestamp = timestamp
        self.id = id
        self.sending_account = sending_account
        self.receiving_account = receiving_account
        self.currency = currency
        self.amount = amount
