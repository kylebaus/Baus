class Fill:
    def __init__(self, timestamp, fill_id, order_id, account, instrument, side, 
                 price, quantity, fees, fee_currency):
        self.timestamp = timestamp
        self.fill_id = fill_id
        self.order_id = order_id
        self.account = account
        self.instrument = instrument
        self.side = side
        self.price = price
        self.quantity = quantity
        self.fees = fees
        self.fee_currency = fee_currency