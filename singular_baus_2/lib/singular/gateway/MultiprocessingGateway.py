import asyncio
import multiprocessing
from queue import Empty

import singular.gateway
import singular.config 
import singular.core
import singular.event

class PlaceRequest:
    def __init__(self, order_id, order):
        self.order_id = order_id
        self.order = order

class CancelRequest:
    def __init__(self, order_id):
        self.order_id = order_id

class ModifyRequest:
    def __init__(self, order_id, order):
        self.order_id = order_id
        self.order = order

class SubscribeOrderbookRequest:
    def __init__(self, instrument):
        self.instrument = instrument

class SubscribeTradesRequest:
    def __init__(self, instrument):
        self.instrument = instrument

class SubscribeFillsRequest:
    def __init__(self):
        pass

class Handler:
    def __init__(self, executor, gateway, inbound_queue):
        self.executor = executor
        self.gateway = gateway
        self.inbound_queue = inbound_queue

    async def poll(self):
        while True:
            request_future = self.executor.run_in_executor(None, self.inbound_queue.get)
            await request_future
            request = request_future.result()

            if type(request) == PlaceRequest:
                self.gateway.place(request.order_id, request.order)
            elif type(request) == CancelRequest:
                self.gateway.cancel(request.order_id)
            elif type(request) == ModifyRequest:
                self.gateway.modify(request.order_id, request.order)
            elif type(request) == SubscribeOrderbookRequest:
                self.gateway.subscribe_orderbook(request.instrument)
            elif type(request) == SubscribeTradesRequest:
                self.gateway.subscribe_trades(request.instrument)
            elif type(request) == SubscribeFillsRequest:
                self.gateway.subscribe_fills()

class MultiprocessingGateway:
    def __init__(self, callbacks, config):
        self.config = config
        self.callbacks = callbacks
        self.outbound_queue = multiprocessing.Queue()
        self.inbound_queue = multiprocessing.Queue()

    def run(self):
        def create_process():
            executor = asyncio.new_event_loop()
            asyncio.set_event_loop(executor)
            
            callbacks = singular.gateway.GatewayCallbacks(
                lambda event: self.outbound_queue.put(event),
                lambda event: self.outbound_queue.put(event),
                lambda event: self.outbound_queue.put(event)
            )

            exchange = singular.config.exchange_str_to_exchange(
                self.config["account"]["exchange"]
            )
            
            if exchange == singular.core.Exchange.OKX:
                gateway = singular.gateway.OkxGateway(executor, callbacks, self.config)
            elif exchange == singular.core.Exchange.BINANCECM:
                gateway = singular.gateway.BinancecmGateway(executor, callbacks, self.config)
            elif exchange == singular.core.Exchange.BINANCEUSDM:
                gateway = singular.gateway.BinanceusdmGateway(executor, callbacks, self.config)
            elif exchange == singular.core.Exchange.DERIBIT:
                gateway = singular.gateway.DeribitGateway(executor, callbacks, self.config)
            else:
                print("MultiprocessingGateway: exchange not supported")

            gateway.run()
           
            handler = Handler(executor, gateway, self.inbound_queue)
            executor.create_task(handler.poll())
            executor.run_forever()

        process = multiprocessing.Process(
            target=create_process,
        )

        process.start()

    def is_active(self):
        # TODO: figure out way of passing bool
        return True

    def place(self, order_id, order):
        # try:
        #     print("MultiprocessingGateway: place:", order_id, "start")
        self.inbound_queue.put(
            PlaceRequest(order_id, order)
        )
        #     print("MultiprocessingGateway: place:", order_id, "end")
        # except Exception as e:
        #     print("MultiprocessingGateway: place:", order.instrument.get_external_symbol(), "Error", e, e.message)

    def cancel(self, order_id):
        self.inbound_queue.put(
            CancelRequest(order_id)
        )

    def modify(self, order_id, order):
        self.inbound_queue.put(
            ModifyRequest(order_id, order)
        )

    def subscribe_orderbook(self, instrument):
        self.inbound_queue.put(
            SubscribeOrderbookRequest(instrument)
        )

    def subscribe_trades(self, instrument):
        self.inbound_queue.put(
            SubscribeTradesRequest(instrument)
        )

    def subscribe_fills(self):
        self.inbound_queue.put(
            SubscribeFillsRequest()
        )

    def consume_all(self):
        while True:
            try:
                event = self.outbound_queue.get_nowait()
                
                if type(event) in [singular.event.PlaceAck,
                                   singular.event.CancelAck,
                                   singular.event.ModifyAck,
                                   singular.event.PlaceReject,
                                   singular.event.CancelReject,
                                   singular.event.Fill]:
                    self.callbacks.on_order_update(event)
                elif type(event) in [singular.event.OrderbookSnapshot,
                                     singular.event.OrderbookLevelUpdate,
                                     singular.event.TopOfBookUpdate]:
                    self.callbacks.on_marketdata_update(event)
                elif type(event) in [singular.event.GatewayDisconnect]:
                    self.callbacks.on_gateway_update(event)
                else:
                    print("MultiprocessingGateway: unhandled event type")
            except Empty:
                break