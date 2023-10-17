import base64
import json
import time
import datetime as dt
import hmac
import asyncio
from loguru import logger

from singular.gateway import AbstractGateway
from singular.core import Exchange, Account, OrderbookLevel, Side, Instrument, InstrumentType, Order, OrderType
from singular.event import TopOfBookUpdate, PlaceAck, PlaceReject, CancelAck, CancelReject, Trade, Fill, \
    GatewayDisconnect
from singular.network import HttpClient, WebsocketClient


class OkxGateway(AbstractGateway):
    def __init__(self, executor, callbacks, config):
        super().__init__(Exchange.OKX, executor, callbacks)
        self.public_websocket_client = WebsocketClient(self.executor, config["public_host"],
                                                       self.parse_websocket, self.notify_disconnect)
        self.private_websocket_client = WebsocketClient(self.executor, config["private_host"],
                                                        self.parse_websocket, self.notify_disconnect)
        self.account = Account(Exchange.OKX, config["account"]["name"])
        self.config = config
        self.active = False
        self.orderbook_subscription_map = {}
        self.trade_subsciption_map = {}
        self.client_to_external_map = {}
        self.external_to_client_map = {}
        self.client_id_to_instrument_map = {}
        self.client_id_to_order_map = {}
        self.client_to_internal_id_map = {}
        self.place_ids = set()
        self.cancel_ids = set()
        self.tasks = set()
        self.cached_place_acks = {}
        self.logger = logger
        self.logger.add(sink='logs/okx_gateway.log', level='DEBUG', backtrace=False, diagnose=False, rotation='00:00')
        self.init_time = int(time.time() * 1000)
        self.rate_limited = False
        self.rate_limited_ts = None

    def private_is_active(self):
        return self.private_websocket_client.is_active()

    def public_is_active(self):
        return self.public_websocket_client.is_active()

    def is_active(self):
        return self.public_is_active() and self.private_is_active()

    def signature(self, timestamp: int, request_path: str):
        method = 'GET'
        payload = f'{timestamp}{method}{request_path}'.encode()
        mac = hmac.new(self.config['secret'].encode(), payload, digestmod='sha256').digest()
        return base64.b64encode(mac)

    async def login(self, status: asyncio.locks.Event):
        timestamp = int(dt.datetime.now().timestamp())
        sign = self.signature(timestamp, request_path='/users/self/verify')

        message = json.dumps(
            {
                'op': 'login',
                'args': [
                    {'apiKey': self.config['key'],
                     'passphrase': self.config['passphrase'],
                     'timestamp': str(timestamp),
                     'sign': sign.decode(),
                     }
                ]
            }
        )
        await status.wait()
        await self.private_websocket_client.send(message)

    def subscribe_fills(self):
        message = json.dumps(
            {
                'op': 'subscribe',
                'args': [
                    {
                        'channel': 'orders',
                        'instType': 'ANY'
                    },
                ]
            }
        )
        task = self.executor.create_task(self.private_websocket_client.send(message))
        self.tasks.add(task)

    def place(self, order_id, order):
        if self.is_active():
            if not self.rate_limited:
                client_id = self.get_client_id(order_id)
                message = json.dumps(
                    {
                        'id': client_id,
                        'op': 'order',
                        'args': [
                            {
                                'side': order.side.name.lower(),
                                'instId': order.instrument.get_external_symbol(),
                                # todo: tdMode might need to be changed after starting to quote spot
                                'tdMode': 'cash' if order.instrument.type == InstrumentType.SPOT else 'cross',
                                'ordType': order.type.name.lower(),
                                'clOrdId': client_id,
                                'sz': order.quantity,
                                'px': order.price
                            }
                        ]
                    }
                )
                self.client_id_to_instrument_map[client_id] = order.instrument
                self.client_id_to_order_map[client_id] = order
                self.client_to_internal_id_map[client_id] = order_id
                task = self.executor.create_task(self.private_websocket_client.send(message))
                self.tasks.add(task)
                self.place_ids.add(client_id)
            else:
                self.callbacks.on_order_update(PlaceReject(order_id=order_id, reason="INTERNAL RATE LIMIT"))
                if time.time() - self.rate_limited_ts > 4.20:
                    self.rate_limited = False
        else:
            self.callbacks.on_order_update(PlaceReject(order_id=order_id, reason="websocket client NOT active"))

    def cancel(self, order_id):
        if self.is_active():
            client_id = self.get_client_id(order_id)
            external_symbol = self.client_id_to_instrument_map[client_id].get_external_symbol()
            message = json.dumps(
                {
                    'id': client_id,
                    'op': 'cancel-order',
                    'args': [
                        {
                            'instId': external_symbol,
                            'clOrdId': client_id
                        }
                    ]
                }
            )
            task = self.executor.create_task(self.private_websocket_client.send(message))
            self.tasks.add(task)
            self.cancel_ids.add(client_id)
        else:
            self.callbacks.on_order_update(CancelReject(order_id=order_id, reason="websocket client NOT active"))

    def subscribe_orderbook(self, instrument: Instrument):
        external_symbol = instrument.get_external_symbol()
        message = json.dumps({
            "op": "subscribe",
            "args": [
                {
                    "channel": "bbo-tbt",
                    "instId": external_symbol
                }
            ]
        })
        task = self.executor.create_task(self.public_websocket_client.send(message))
        self.tasks.add(task)
        self.orderbook_subscription_map[external_symbol] = instrument

    def get_funding(self, account, instrument: Instrument):
        # TODO
        task = self.executor.create_task()
        self.tasks.add(task)

    def subscribe_tickers(self, instrument: Instrument):
        message = json.dumps({
            "op": "subscribe",
            "args": [
                {
                    "channel": "tickers",
                    "instId": instrument.get_external_symbol()
                }
            ]
        })
        task = self.executor.create_task(self.public_websocket_client.send(message))
        self.tasks.add(task)

    def subscribe_trades(self, instrument: Instrument):
        message = json.dumps({
            "op": "subscribe",
            "args": [
                {
                    "channel": "trades",
                    "instId": instrument.get_external_symbol()
                }
            ]
        })
        task = self.executor.create_task(self.public_websocket_client.send(message))
        self.tasks.add(task)
        self.trade_subsciption_map[instrument.get_external_symbol()] = instrument

    @logger.catch
    def parse_websocket(self, message: str):
        if message:
            # print(f'websocket received {message}')
            message_dict = json.loads(message)

            if message_dict.get('event') in ['subscribe', 'unsubscribe']:  # successful subscription
                self.logger.info(f"OKXGateway: {message_dict.get('event')} to {message_dict.get('arg')}")
            elif message_dict.get('event') == 'login':
                self.logger.info(f'OKXGateway: login success')
            elif message_dict.get('event') == 'error':
                self.logger.error(f"OKXGateway: Error subscribing: {message_dict.get('msg')}")
            elif message_dict.get('arg'):  # subscription push data
                self.parse_subs(message_dict)
            elif message_dict.get('op') == 'order':
                self.parse_place(message_dict)
            elif message_dict.get('op') == 'cancel-order':
                self.parse_cancel(message_dict)
            else:
                self.logger.info(f'OKXGateway: Unhandled parse websocket message: {message}')

    def parse_place(self, message: dict):
        for data in message['data']:
            try:
                if data['sCode'] == '0':
                    client_id = int(data['clOrdId'])
                    external_id = int(data['ordId'])
                    self.client_to_external_map[client_id] = external_id
                    self.external_to_client_map[external_id] = client_id
                    if client_id in self.place_ids:
                        self.ack_place(client_id)

                else:
                    order_id = self.client_to_internal_id_map[int(data['clOrdId'])]
                    self.logger.exception(
                        f"OKXGateway: failed to place order {order_id}, "
                        f"msg {data}")
                    if data['sCode'] == '50011':  # rate-limit
                        self.rate_limited = True
                        self.rate_limited_ts = time.time()

                    self.callbacks.on_order_update(
                        PlaceReject(order_id=order_id,
                                    reason=data['sMsg']))

            except Exception as e:
                self.logger.exception(f'OKXGateway parse_place Exception: {e}')
                self.callbacks.on_order_update(
                    PlaceReject(order_id=self.client_to_internal_id_map[int(data['clOrdId'])],
                                reason=str(e))
                )

    def parse_cancel(self, message: dict):
        for data in message['data']:
            try:
                client_id = int(data['clOrdId'])
                order_id = self.client_to_internal_id_map[client_id]
                if data['sCode'] == '0':
                    if client_id in self.cancel_ids:
                        self.ack_cancel(client_id)
                else:
                    if data['sCode'] == '51401' or data['sCode'] == '51402':  # order already cancelled / completed
                        self.ack_cancel(client_id)
                    else:
                        if data['sCode'] == '50011':  # rate-limit
                            self.rate_limited = True
                            self.rate_limited_ts = time.time()
                        else:
                            self.logger.exception(f"OKXGateway: failed to cancel order {order_id}, msg {data}")
                        self.callbacks.on_order_update(CancelReject(order_id=order_id, reason=data['sMsg']))

            except Exception as e:
                self.logger.exception(f'OKXGateway: parse_cancel exception {e}')
                self.callbacks.on_order_update(
                    CancelReject(order_id=self.client_to_internal_id_map[int(data['clOrdId'])],
                                reason=str(e))
                )

    def parse_subs(self, message: dict):
        channel = message['arg']['channel'].replace('-', '_')
        parser = getattr(self, f'parse_{channel}')
        return parser(message)

    def parse_orders(self, message: dict):
        for data in message.get('data'):
            client_id = int(data['clOrdId'])
            if client_id in self.client_id_to_instrument_map:  # so it doesn't care about other algos
                if client_id in self.place_ids:
                    # self.logger.info(f"OKXGateway: order {client_id} updated before place ws msg arrives: {data}")
                    self.ack_place(client_id)
                elif client_id in self.cancel_ids:
                    # self.logger.info(f"OKXGateway: order {client_id} updated before cancel ws msg arrives: {data}")
                    self.ack_cancel(client_id)

                if data['fillPx'] != '':
                    fill = Fill(timestamp=int(data['fillTime']),
                                fill_id=int(data['tradeId']),
                                order_id=self.client_to_internal_id_map[int(data['clOrdId'])],
                                account=self.account,
                                instrument=self.client_id_to_instrument_map[client_id],
                                side=self.client_id_to_order_map[client_id].side,
                                price=float(data['fillPx']),
                                quantity=float(data['fillSz']),
                                fees=-float(data['fee']),
                                fee_currency=data['feeCcy'])
                    self.callbacks.on_order_update(fill)

    def parse_bbo_tbt(self, message: dict):
        # orderbook update -- 1 depth level snapshot every 10ms
        last_bbo_event_dt = dt.datetime.fromtimestamp(float(message["data"][0]["ts"]) / 1000)  # okx ts in ms
        external_symbol = message['arg']['instId']
        bid = message['data'][0]['bids'][0]
        ask = message['data'][0]['asks'][0]
        bid_level = OrderbookLevel(
            instrument=self.orderbook_subscription_map[external_symbol],
            side=Side.BUY,
            price=float(bid[0]),
            quantity=float(bid[1])
        )
        ask_level = OrderbookLevel(
            instrument=self.orderbook_subscription_map[external_symbol],
            side=Side.SELL,
            price=float(ask[0]),
            quantity=float(ask[1])
        )
        self.callbacks.on_marketdata_update(
            TopOfBookUpdate(instrument=self.orderbook_subscription_map[external_symbol],
                            update_dt=last_bbo_event_dt,
                            best_bid=bid_level,
                            best_ask=ask_level)
        )

    def parse_trades(self, message: dict):
        external_symbol = message['arg']['instId']
        data = message['data'][0]
        trade = Trade(
            instrument=self.trade_subsciption_map[external_symbol],
            side=Side[data['side'].upper()],
            price=float(data['px']),
            quantity=float(data['sz'])
        )
        self.callbacks.on_marketdata_update(trade)

    def ack_place(self, client_id: int):
        order = self.client_id_to_order_map[client_id]
        event = PlaceAck(
            order_id=self.client_to_internal_id_map[client_id],
            account=self.account,
            instrument=self.client_id_to_instrument_map[client_id],
            side=order.side,
            price=order.price,
            quantity=order.quantity
        )
        self.callbacks.on_order_update(event)
        self.place_ids.remove(client_id)

    def ack_cancel(self, client_id: int):
        event = CancelAck(order_id=self.client_to_internal_id_map[client_id])
        self.callbacks.on_order_update(event)
        if client_id in self.cancel_ids:
            self.cancel_ids.remove(client_id)

    def get_client_id(self, order_id: int) -> int:
        return int(str(self.init_time) + str(order_id))

    def notify_disconnect(self):
        print("OkxGateway: notify_disconnect: propagate GatewayDisconnect")
        self.callbacks.on_gateway_update(GatewayDisconnect(self.account))
        self.reconnect()

    def reconnect(self):
        print("OkxGateway: reconnect: new websockets and re-run")
        self.public_websocket_client = WebsocketClient(self.executor, self.config['public_host'],
                                                       self.parse_websocket, self.notify_disconnect)
        self.private_websocket_client = WebsocketClient(self.executor, self.config['private_host'],
                                                        self.parse_websocket, self.notify_disconnect)
        self.run()

    def run(self):
        print("OkxGateway: run: connecting to websockets")
        public_status = asyncio.Event()
        private_status = asyncio.Event()
        public_connect_task = self.executor.create_task(self.public_websocket_client.run(public_status))
        private_connect_task = self.executor.create_task(self.private_websocket_client.run(private_status))
        self.tasks.add(public_connect_task)
        self.tasks.add(private_connect_task)

        print("OkxGateway: run: logging in")
        login_task = self.executor.create_task(self.login(private_status))
        self.tasks.add(login_task)