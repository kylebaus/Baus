
class Currency:
    def __init__(self, exchange, internal_symbol, external_symbol, 
                 min_price_precision, min_quantity_precision):
        self.exchange = exchange
        self.internal_symbol = internal_symbol
        self.external_symbol = external_symbol
        self.min_price_precision = min_price_precision 
        self.min_quantity_precision = min_quantity_precision 

    ### Interface ###
    
    def get_exchange(self):
        return self.exchange

    def get_internal_symbol(self):
        return self.internal_symbol

    def get_external_symbol(self):
        return self.external_symbol

    def get_min_price_precision(self):
        return self.min_price_precision

    def get_min_quantity_precision(self):
        return self.get_min_quantity_precision