
class GatewayCallbacks:
    def __init__(self, on_order_update, on_marketdata_update, on_gateway_update):
        self.on_order_update = on_order_update
        self.on_marketdata_update = on_marketdata_update
        self.on_gateway_update = on_gateway_update