from singular.core import Order, Side
from singular.event import  PlaceAck, ModifyAck, CancelAck, Fill, PlaceReject, CancelReject

EPS = 0.0000001

class PersistentOrder:
    def __init__(self, strategy, account, instrument, side, order_type):
        ### Parameters ###
        self.strategy = strategy
        self.account = account
        self.instrument = instrument
        self.side = side
        self.order_type = order_type

        ### State ###
        self.order = Order(instrument, account, side, None, None, order_type)
        self.order_id = None
        self.order_ids = []
        self.pending = False
        self.active = False

    def get_order_id(self):
        return self.order_id

    def get_order_ids(self):
        return self.order_ids

    def handle_update(self, update):
        if type(update) == PlaceAck:
            self.pending = False
            self.active = True
            self.order.set_price(update.price)
            self.order.set_quantity(update.quantity)
        elif type(update) == CancelAck or type(update) == PlaceReject:
            self.pending = False
            self.active = False
            self.order.set_price(None)
            self.order.set_quantity(None)
            self.order_id = None
        elif type(update) == CancelReject:
            self.pending = False
        elif type(update) == Fill:
            remaining_quantity = self.order.get_quantity() - update.quantity
            self.order.set_quantity(remaining_quantity)
            if (remaining_quantity < EPS):  # order fully filled, close it
                # print("Closing ", self.order_id)
                self.active = False
                self.pending = False
                self.order.set_price(None)
                self.order.set_quantity(None)
                self.order_id = None
        else:
            pass

    def update(self, active, price, quantity):
        if active:
            # order should be active
            if self.active:
                # order is active - check if price/quantity is correct
                if self.pending:
                    # order is pending - do nothing
                    pass
                else:
                    # check if price/quantity is correct
                    # print(self.order.get_price(), price, self.instrument.get_min_price_precision())
                    if (abs(self.order.get_price() - price) > self.instrument.get_min_price_precision()) or \
                        (abs(self.order.get_quantity() - quantity) > self.instrument.get_min_quantity_precision()):
                        # need to modify
                        self.pending = True
                        # print("PersistentOrder: need to modify cancel ", self.order_id)
                        # print("State: ", self.order_id, self.active, self.pending)
                        self.strategy.cancel(self.account, self.order_id)
            else:
                # order is not active - place
                # print("StateTop: ", self.order_id, self.active, self.pending)
                if not self.pending:
                    self.order.set_price(price)
                    self.order.set_quantity(quantity)
                    self.pending = True
                    self.order_id = self.strategy.place(self.order)
                    self.order_ids.append(self.order_id)
                # print("PersistentOrder: order is not active - place", self.order_id)
                # print("StateBottom: ", self.order_id, self.active, self.pending)
        else:
            # order should be inactive
            if self.active:
                # orer is active - cancel
                if self.pending:
                    # order is pending - do nothing
                    pass
                else:
                    # cancel
                    self.pending = True
                    self.strategy.cancel(self.account, self.order_id)
                    # print("PersistentOrder: cancel", self.order_id)
                    # print("State: ", self.order_id, self.active, self.pending)
            else:
                # order is inactive - do nothing
                pass
            