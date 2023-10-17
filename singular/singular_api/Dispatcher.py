from datetime import datetime
import queue
import logging

# Singular
from singular.gateway.GatewayCallbacks import GatewayCallbacks
from singular.event import TopOfBookUpdate, Trade

# Euler
from euler.system.GatewayManagementSystem import GatewayManagementSystem
from euler.system.OrderManagementSystem import OrderManagementSystem
from euler.system.OrderbookManagementSystem import OrderbookManagementSystem

class Dispatcher:
    def __init__(self, executor, config):
        self.config = config
        self.executor = executor

        ### Systems ###

        callbacks =\
            GatewayCallbacks((lambda event: self.handle_order_event(event)),
                             (lambda event: self.handle_marketdata_event(event)),
                             (lambda event: self.handle_gateway_event(event)))

        self.gateway_management_system =\
             GatewayManagementSystem(config, executor, callbacks)

        self.order_management_system = OrderManagementSystem()
        
        self.orderbook_management_system = OrderbookManagementSystem(config)

        ### Messaging ###
        self.strategy_event_queues = {}

        ### Marketdata ###
        self.orderbook_subscriptions = {}
        self.trade_subscriptions = {}

    ### Main Interface ###

    def run(self):
        self.gateway_management_system.run()

    ### Strategy Inbound Interface ###

    def register_strategy(self, strategy_id):
        self.strategy_event_queues[strategy_id] = queue.Queue()
        return self.strategy_event_queues[strategy_id]

    def is_active(self, account):
        return self.gateway_management_system.is_active(account)

    def place(self, strategy_id, order):
        order_id = self.order_management_system.place(strategy_id, order) 
        self.gateway_management_system.place(order_id, order)
        return order_id

    def cancel(self, account, order_id):
        self.order_management_system.cancel(account, order_id)
        self.gateway_management_system.cancel(account, order_id)

    def modify(self, strategy_id, order_id, order):
        self.order_management_system.modify(strategy_id, order_id, order)
        self.gateway_management_system.modify(order_id, order)

    def subscribe_fills(self, strategy_id, account):
        # TODO: log subscribers
        self.gateway_management_system.subscribe_fills(account)

    def subscribe_orderbook(self, strategy_id, account, instrument):
        # add strategy_id to orderbook_subscription list for given 
        # (Account, Instrument) pair

        key = (account.get_exchange(), account.get_name(), 
                instrument.get_external_symbol())

        if key in self.orderbook_subscriptions.keys():
            self.orderbook_subscriptions[key].append(strategy_id)
        else:
            self.orderbook_subscriptions[key] = [strategy_id]

        not_mapped = self.orderbook_management_system.subscribe_orderbook(instrument)

        if not_mapped:
            self.gateway_management_system.subscribe_orderbook(account, instrument)

    def subscribe_trades(self, strategy_id, account, instrument):
        # add strategy_id to trades_subscription list for given 
        # (Account, Instrument) pair
        
        key = (account.get_exchange(), instrument.get_external_symbol())
        if key in self.trade_subscriptions.keys():
            self.trade_subscriptions[key].append(strategy_id)
        else:
            self.trade_subscriptions[key] = [strategy_id]

        self.gateway_management_system.subscribe_trades(account, instrument)

    def get_orderbook(self, instrument):
        return self.orderbook_management_system.get_orderbook(instrument)

    def get_funding(self, instrument):
        self.gateway_management_system.get_funding(account, instrument)

    ### Strategy Outbound Interface ###

    def send_event(self, strategy_id, event):
        self.strategy_event_queues[strategy_id].put(event)

    ### Gateway Inbound Interface ###

    def handle_order_event(self, event):
        strategy_id = self.order_management_system.get_strategy_id(event.order_id)
        self.send_event(strategy_id, event)

    def handle_gateway_event(self, event):
        for strategy_id in self.strategy_event_queues.keys(): 
            self.send_event(strategy_id, event)

    def handle_marketdata_event(self, event):
        if type(event) == Trade:
            key = (event.instrument.exchange, event.instrument.external_symbol)
            for strategy_id in self.trade_subscriptions[key]:
                self.send_event(strategy_id, event)
        elif type(event) == TopOfBookUpdate:
            self.orderbook_management_system.handle_event(event)
        else:
            pass
    