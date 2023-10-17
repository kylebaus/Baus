import copy

class OrderStatus:
    def __init__(self, strategy_id, pending, order):
        self.strategy_id = strategy_id
        self.pending = pending
        self.order = order

class OrderManagementSystem:
    def __init__(self):
        self.order_map = {}
        self.order_id = 0

    def place(self, strategy_id, order):
        self.order_id += 1
        order_id = copy.copy(self.order_id)
        self.order_map[order_id] = OrderStatus(strategy_id, True, copy.copy(order))
        return self.order_id 

    def cancel(self, account, order_id):
        pass

    def modify(self, strategy_id, order_id, order):
        pass
    
    def get_strategy_id(self, order_id):
        return self.order_map[order_id].strategy_id