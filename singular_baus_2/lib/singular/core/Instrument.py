
class Instrument:
    def __init__(self, exchange, internal_symbol, external_symbol, 
                 base_currency, quote_currency, min_price_precision,
                 min_quantity_precision, min_order_quantity, 
                 min_order_notional_quantity, type, contract_value=None, expiry=None):

        self.exchange = exchange
        self.internal_symbol = internal_symbol
        self.external_symbol = external_symbol
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.min_price_precision = min_price_precision
        self.min_quantity_precision = min_quantity_precision
        self.min_order_quantity = min_order_quantity
        self.min_order_notional_quantity = min_order_notional_quantity
        self.type = type
        self.contract_value = contract_value
        self.expiry = expiry

    ### Interface ###
    
    def get_exchange(self):
        return self.exchange

    def get_internal_symbol(self):
        return self.internal_symbol

    def get_external_symbol(self):
        return self.external_symbol

    def get_base_currency(self):
        return self.base_currency

    def get_quote_currency(self):
        return self.quote_currency

    def get_min_price_precision(self):
        return self.min_price_precision

    def get_min_quantity_precision(self):
        return self.min_quantity_precision

    def get_min_order_quantity(self):
        return self.min_order_quantity

    def get_min_order_notional_quantity(self):
        return self.min_order_notional_quantity

    def get_type(self):
        return self.type

    def get_contract_value(self):
        return self.contract_value

    def get_expiry(self):
        return self.expiry