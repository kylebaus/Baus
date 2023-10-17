import json
import hmac
import hashlib
from urllib import parse
import asyncio
import requests
import time
import datetime as dt
from loguru import logger

from .. import AbstractGateway
from ...core import Exchange, Account, OrderbookLevel, Side, OrderType
from ...event import TopOfBookUpdate, PlaceAck, PlaceReject, CancelAck, CancelReject, Fill, GatewayDisconnect
from ...network import HttpClient, WebsocketClient


# logger.configure(handlers=[
#     {'sink': 'logs/binancecm_gateway.log', 'level': 'DEBUG', 'backtrace': False, 'diagnose': True,
#      'rotation': '00:00'}])


class BinancecmGateway(AbstractGateway):
    def __init__(self, executor, callbacks, config):
        super().__init__(Exchange.BINANCECM, executor, callbacks)
        self.config = config
        self.http_client = HttpClient(self.executor, "https://dapi.binance.com", 10)
        self.listen_key = self.get_listen_key()
        self.websocket_client = WebsocketClient(self.executor, config["host"] + "/" + self.listen_key, 
                                                self.parse_websocket, self.notify_disconnect)
        self.account = Account(Exchange.BINANCECM, config["account"]["name"])
        self.active = False
        self.orderbook_subscription_map = {}
        self.trade_subsciption_map = {}
        self.internal_to_external_map = {}
        self.external_to_internal_map = {}
        self.internal_id_to_instrument_map = {}
        self.cached_fills = {}
        self.tasks = set()
        self.ws_id = 0
        self.logger = logger
        self.logger.add(sink='logs/binancecm_gateway.log', level='DEBUG', backtrace=False,
                        diagnose=True, rotation='00:00')
        self.rate_limited = False
        self.rate_limited_ts = None

    def is_active(self):
        return self.websocket_client.is_active()

    def signature(self, payload_str: str = None):
        sig = hmac.new(
            self.config['secret'].encode(),
            msg=payload_str.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        return sig

    def sign_payload(self, payload: dict = None, rec_window: int = 60000):
        timing_security = {'timestamp': int(time.time() * 1000),
                           'recvWindow': rec_window}
        payload = payload if payload else {}
        signed_payload = parse.urlencode({**payload, **timing_security})
        sig = self.signature(signed_payload)

        return f"{signed_payload}&signature={sig}"

    def get_headers(self, method: str):
        headers = {'X-MBX-APIKEY': self.config['key']}
        if method.upper() == 'GET':
            headers['Content-Type'] = 'application/json'

        return headers

    def get_listen_key(self):
        BINANCE_FUTURES_END_POINT = "https://dapi.binance.com/dapi/v1/listenKey"
        header = {"X-MBX-APIKEY": self.config["key"]}
        response = requests.post(url=BINANCE_FUTURES_END_POINT, headers=header).json()
        return response["listenKey"]

    async def keep_alive_listen_key(self):
        while True:
            message = await self.http_client.put(endpoint='dapi/v1/listenKey',
                                                 header=self.get_headers('PUT'),
                                                 data=None)
            if message == {}:
                self.logger.info("BinancecmGateway: keep_alive_listen_key success")
            else:
                self.logger.info("BinancecmGateway: keep_alive_listen_key failure")
            await asyncio.sleep(60*30)

    def subscribe_fills(self):
        self.logger.info("BinancecmGateway: subscribe_fills")
        message = json.dumps({"method": "SUBSCRIBE", 
                              "params": ["ORDER_TRADE_UPDATE"], 
                              "id": self.ws_id})
        self.ws_id += 1
        task = self.executor.create_task(self.websocket_client.send(message))
        self.tasks.add(task)

    async def place_wrapper(self, order_id, order):
        try:
            endpoint = 'dapi/v1/order'
            if order.type == OrderType.IOC:
                time_in_force = 'IOC'
            elif order.type == OrderType.POST_ONLY:
                time_in_force = 'GTX'
            else:  # limit
                time_in_force = 'GTC'
            payload = {
                'symbol': order.instrument.get_external_symbol(),
                'side': order.side.name.upper(),
                'type': 'LIMIT',
                'timeInForce': time_in_force,
                'quantity': order.quantity,
                'price': round(order.price, 2)
            }

            signed_payload_str = self.sign_payload(payload)
            message = await self.http_client.post(endpoint=f'{endpoint}?{signed_payload_str}',
                                                  header=self.get_headers(method='POST'),
                                                  data=None)

            if 'orderId' in message:
                self.internal_to_external_map[order_id] = message["orderId"]
                self.external_to_internal_map[message["orderId"]] = order_id
                self.internal_id_to_instrument_map[order_id] = order.instrument

                event = PlaceAck(order_id,
                                 self.account,
                                 order.instrument,
                                 order.side,
                                 float(message["price"]),
                                 float(message["origQty"]))

                self.callbacks.on_order_update(event)

                # print("Placing", order_id, message["id"], message, type(message["id"]))

                if message["orderId"] in self.cached_fills.keys():
                    for fill_update in self.cached_fills[message["orderId"]]:
                        fill_update.order_id = order_id
                        self.callbacks.on_order_update(fill_update)
                    del self.cached_fills[message["orderId"]]
            else:
                self.logger.info(f'BinancecmGateway: unable to parse place_wrapper message {message}')
                self.callbacks.on_order_update(PlaceReject(order_id, message))
                if "code" in message.keys():
                    if message["code"] == -1015:
                        self.rate_limited = True
                        self.rate_limited_ts = time.time()

        except Exception as e:
            self.logger.info(f'BinancecmGateway: place wrapper error {e}')
            # self.logger.info("BinancecmGateway: place_wrapper", order.instrument.get_external_symbol(), "Error", str(e))
            # self.logger.exception("BinancecmGateway: place_wrapper", order.instrument.get_external_symbol(), "Error", str(e))
            self.callbacks.on_order_update(PlaceReject(order_id, e))
    
    def place(self, order_id, order):
        if not self.rate_limited:
            task = self.executor.create_task(self.place_wrapper(order_id, order))
            self.tasks.add(task)
        else:
            self.callbacks.on_order_update(PlaceReject(order_id=order_id, reason="INTERNAL RATE LIMIT"))
            if time.time() - self.rate_limited_ts > 4.20:
                self.rate_limited = False

    async def cancel_wrapper(self, order_id, instrument):
        try:
            # message =\
            #     await self.ccxt_client.cancel_order(self.internal_to_external_map[order_id],
            #                                         instrument.get_external_symbol())
            endpoint = 'dapi/v1/order'
            payload = {
                'symbol': instrument.get_external_symbol(),
                'orderId': self.internal_to_external_map[order_id],
            }
            signed_payload_str = self.sign_payload(payload)
            message = await self.http_client.delete(endpoint=f"{endpoint}?{signed_payload_str}",
                                                    header=self.get_headers('DELETE'))

            event = CancelAck(order_id)
        except Exception as e:
            self.logger.info((f"BinancecmGateway: cancel_wrapper error for {order_id}, reason: {e}"))
            # self.logger.exception((f"BinancecmGateway: cancel_wrapper error for {order_id}, reason: {e}"))
            event = CancelReject(order_id, e)

        self.callbacks.on_order_update(event)

    def cancel(self, order_id):
        instrument = self.internal_id_to_instrument_map[order_id]
        task = self.executor.create_task(self.cancel_wrapper(order_id, instrument))
        self.tasks.add(task)

    def subscribe_orderbook(self, instrument):
        self.logger.info("BinancecmGateway: subscribe_orderbook")
        symbol = instrument.get_external_symbol().lower()
        message = json.dumps({"method": "SUBSCRIBE", 
                              "params": [symbol+"@bookTicker"], 
                              "id": self.ws_id})
        self.ws_id += 1
        task = self.executor.create_task(self.websocket_client.send(message))
        self.tasks.add(task)
        self.orderbook_subscription_map[instrument.get_external_symbol()] = instrument


    # def subscribe_trades(self, instrument):
    #     message = \
    #         json.dumps({"op": "subscribe", 
    #                     "channel": "trades", 
    #                     "market": instrument.get_external_symbol()})

    #     task = self.executor.create_task(self.websocket_client.send(message))
    #     self.tasks.add(task)
    #     self.trade_subsciption_map[instrument.get_external_symbol()] = instrument

    def parse_websocket(self, message):
        try:
            message = json.loads(message)
            # print(message)
            if "e" in message.keys():
                if message["e"] == "bookTicker":
                    last_bookTicker_event_dt = dt.datetime.fromtimestamp(message["E"] / 1000)

                    bid_level = OrderbookLevel(None, Side.BUY, 
                                               float(message["b"]), float(message["B"]))
                    ask_level = OrderbookLevel(None, Side.SELL, 
                                               float(message["a"]), float(message["A"]))

                    self.callbacks.on_marketdata_update(
                        TopOfBookUpdate(self.orderbook_subscription_map[message["s"]], 
                                        last_bookTicker_event_dt,
                                        bid_level, 
                                        ask_level))
                                        
                elif message["e"] == "ORDER_TRADE_UPDATE":
                    # print("ORDER TRADE UPDATE", message)
                    if message["o"]["L"] != "0":  #TODO confirm this is the way to filter for fills
                        ext_id = int(message["o"]["i"])
                        # print("BinancecmGateway: parse_websocket: fill msg", ext_id, message)
                        if ext_id in self.external_to_internal_map.keys():
                            order_id = self.external_to_internal_map[ext_id]
                        else:
                            order_id = None
                            # self.logger.info(f"BinancecmGateway: parse_websocket: Fill internal id not in map, "
                            #                  f"likely race condition "
                            #                  f"with immediate Fill before PlaceAck response received "
                            #                  f"OR a manual fill / fill from another strategy")

                        fill = Fill(timestamp=int(message["o"]["T"]),
                                    fill_id=None,
                                    order_id=order_id,
                                    account=self.account,
                                    instrument=None,
                                    side=None,
                                    price=float(message["o"]["L"]),
                                    quantity=float(message["o"]["l"]),
                                    fees=float(message["o"]["n"]),
                                    fee_currency=message["o"]["N"])

                        if not order_id:
                            if ext_id in self.cached_fills.keys():
                                self.cached_fills[ext_id].append(fill)
                            else:
                                self.cached_fills[ext_id] = [fill]
                        else:
                            self.callbacks.on_order_update(fill)
                else:
                    pass
                    # print("BinancecmGateway: parse_websocket: event type not parsed", message)
            else:
                pass
                # print("BinancecmGateway: parse_websocket: no event in message keys", message)
            #     elif message["channel"] == "fills":
            #         print(message)
            #         if message["type"] == "update":
            #             order_id = str(message["data"]["orderId"])
            #             # print(order_id, type(message["data"]["orderId"]))
            #             if order_id in self.external_to_internal_map.keys():
            #                 self.callbacks.on_order_update(
            #                     Fill(None, None, self.external_to_internal_map[order_id], self.account,
            #                         None, Side.BUY if message["data"]["side"] == "buy" else Side.SELL,
            #                         float(message["data"]["price"]), float(message["data"]["size"]),
            #                         None, None))
            #             else: # Fill before PlaceAck
            #                 print(f"Fill internal id not in map, likely race condition "
            #                     f"with immediate Fill before PlaceAck response received " 
            #                     f"OR a manual fill / fill from another strategy")
            #                 fill = Fill(None, None, None, self.account, None,
            #                             Side.BUY if message["data"]["side"] == "buy" else Side.SELL,
            #                             float(message["data"]["price"]), float(message["data"]["size"]),
            #                             None, None)
            #                 if order_id in self.cached_fills.keys():
            #                     self.cached_fills[order_id].append(fill)
            #                 else:
            #                     self.cached_fills[order_id] = [fill]

            #     else:
            #         print("Unknown channel", message)
            # else:
            #     print("Channel not present", message)
        except Exception as e:
            self.logger.info("BinancecmGateway: parse_websocket exception: ", e)
            # self.logger.exception("BinancecmGateway: parse_websocket exception: ", e)

    def notify_disconnect(self):
        self.logger.info("BinancecmGateway: notify_disconnect")
        self.callbacks.on_gateway_update(GatewayDisconnect(self.account))
        self.reconnect()
        
    def reconnect(self):
        self.logger.info("BinancecmGateway: reconnect")
        self.websocket_client = WebsocketClient(self.executor, self.config["host"], 
                                                self.parse_websocket, self.notify_disconnect)
        self.run()
                
    def run(self):
        self.logger.info("BinancecmGateway: run")
        status = asyncio.Event()
        task = self.executor.create_task(self.websocket_client.run(status))
        self.tasks.add(task)

        self.logger.info("BinancecmGateway: keep_alive_listen_key")
        task = self.executor.create_task(self.keep_alive_listen_key())
        self.tasks.add(task)

