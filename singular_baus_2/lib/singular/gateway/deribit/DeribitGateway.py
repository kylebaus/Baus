from distutils.command.config import config
import json
import datetime as dt
import hmac
import hashlib
import asyncio
import urllib
import time
from loguru import logger
from collections import defaultdict

from singular.gateway import AbstractGateway, GatewayCallbacks
from singular.core import Exchange, Account, OrderbookLevel, Side, Order, OrderType
from singular.event import TopOfBookUpdate, PlaceAck, PlaceReject, CancelAck, CancelReject, Fill, Trade, \
    GatewayDisconnect
from singular.network import HttpClient, WebsocketClient
from singular.core.Instrument import Instrument


# logger.configure(handlers=[
#     {'sink': 'logs/deribit_gateway.log', 'level': 'DEBUG', 'backtrace': False, 'diagnose': True, 'rotation': '00:00'}])


class DeribitGateway(AbstractGateway):
    def __init__(self, executor, callbacks, config):
        super().__init__(Exchange.DERIBIT, executor, callbacks)
        self.websocket_client = WebsocketClient(self.executor, config["host"],
                                                self.parse_websocket, self.notify_disconnect)
        self.account = Account(Exchange.DERIBIT, config['account']['name'])
        self.config = config
        self.active = False
        self.orderbook_subscription_map = {}
        self.trade_subsciption_map = {}
        self.internal_to_external_map = {}
        self.external_to_internal_map = {}
        self.internal_id_to_instrument_map = {}
        self.external_id_to_instrument_map = {}
        self.cached_fills = defaultdict(list)  # fill before place ack
        self.acked_fills = set()  # place ack before fill
        self.login_ids = set()
        self.place_ids = set()
        self.cancel_ids = set()
        self.sub_ids = set()
        self.tasks = set()
        self.logger = logger
        self.logger.add(sink='logs/deribit_gateway.log', level='DEBUG', backtrace=False,
                        diagnose=True, rotation='00:00')

    def is_active(self):
        return self.websocket_client.is_active()

    async def login(self, status):
        timestamp = round(dt.datetime.now().timestamp() * 1000)
        nonce = str(dt.datetime.now().timestamp())
        message = json.dumps({
            'jsonrpc': '2.0',
            'id': timestamp,
            'method': 'public/auth',
            'params': {
                'grant_type': 'client_signature',
                'client_id': self.config['key'],
                'timestamp': timestamp,
                'signature': self.signature(timestamp, nonce),
                'nonce': nonce,
                'data': ''
            }
        })
        await status.wait()
        await self.websocket_client.send(message)
        self.login_ids.add(timestamp)

    def signature(self, timestamp: int = None, nonce: str = None, data: str = ''):
        timestamp = round(dt.datetime.now().timestamp() * 1000) if not timestamp else timestamp
        nonce = str(dt.datetime.now().timestamp()) if not nonce else nonce
        signature = hmac.new(
            bytes(self.config['secret'], "latin-1"),
            msg=bytes('{}\n{}\n{}'.format(timestamp, nonce, data), "latin-1"),
            digestmod=hashlib.sha256
        ).hexdigest().lower()

        return signature

    @logger.catch
    def place(self, internal_order_id, order):
        # print("DeribitGateway: place:", order.quantity)
        if self.is_active():
            method = 'private/buy' if order.side == Side.BUY else 'private/sell'
            message = json.dumps(
                {
                    'jsonrpc': '2.0',
                    'id': internal_order_id,
                    'method': method,
                    'params': {
                        'instrument_name': order.instrument.get_external_symbol(),
                        'amount': order.quantity,
                        'price': order.price,
                        'type': 'limit',
                        'post_only': True if order.type == OrderType.POST_ONLY else False,
                        'time_in_force': 'immediate_or_cancel' if order.type == OrderType.IOC else 'good_til_cancelled',
                        'label': internal_order_id
                    }
                }
            )
            self.internal_id_to_instrument_map[internal_order_id] = order.instrument
            task = self.executor.create_task(self.websocket_client.send(message))
            self.tasks.add(task)
            self.place_ids.add(internal_order_id)
        else:
            self.callbacks.on_order_update(PlaceReject(order_id=internal_order_id,
                                                       reason="websocket client NOT active"))

    @logger.catch
    def cancel(self, internal_order_id):
        if self.is_active():
            external_order_id = self.internal_to_external_map[internal_order_id]
            message = json.dumps(
                {
                    'jsonrpc': '2.0',
                    'id': internal_order_id,
                    'method': 'private/cancel',
                    'params': {
                        'order_id': external_order_id
                    }
                }
            )
            task = self.executor.create_task(self.websocket_client.send(message))
            self.tasks.add(task)
            self.cancel_ids.add(internal_order_id)
        else:
            self.callbacks.on_order_update(CancelReject(order_id=internal_order_id,
                                                        reason="websocket client NOT active"))

    @logger.catch
    def cancel_all(self):
        message = json.dumps(
            {
                'jsonrpc': '2.0',
                'id': int(dt.datetime.now().timestamp() * 1000),
                'method': 'private/cancel_all',
                'params': {

                }
            }
        )
        task = self.executor.create_task(self.websocket_client.send(message))
        self.tasks.add(task)

    def subscribe_fills(self):
        channel = f'user.trades.any.any.raw'
        request_id = int(dt.datetime.now().timestamp() * 1000)
        message = json.dumps({
            'jsonrpc': '2.0',
            'id': request_id,
            'method': 'private/subscribe',
            'params': {
                'channels': [channel]
            }
        })
        task = self.executor.create_task(self.websocket_client.send(message))
        self.tasks.add(task)
        # self.external_id_to_instrument_map[instrument.get_external_symbol()] = instrument
        self.sub_ids.add(request_id)

    def subscribe_trades(self, instrument: Instrument):
        channel = f'trades.{instrument.get_external_symbol()}.raw'
        request_id = int(dt.datetime.now().timestamp() * 1000)
        message = json.dumps({
            'jsonrpc': '2.0',
            'id': request_id,
            'method': 'public/subscribe',
            'params': {
                'channels': [channel]
            }
        })
        task = self.executor.create_task(self.websocket_client.send(message))
        self.tasks.add(task)
        self.trade_subsciption_map[instrument.get_external_symbol()] = instrument
        self.sub_ids.add(request_id)

    def subscribe_orderbook(self, instrument: Instrument):
        channel = f'ticker.{instrument.get_external_symbol()}.raw'
        request_id = int(dt.datetime.now().timestamp() * 1000)
        message = json.dumps({
            'jsonrpc': '2.0',
            'id': request_id,
            'method': 'public/subscribe',
            'params': {
                'channels': [channel]
            }
        })
        task = self.executor.create_task(self.websocket_client.send(message))
        self.tasks.add(task)
        self.orderbook_subscription_map[instrument.get_external_symbol()] = instrument
        self.sub_ids.add(request_id)

    @logger.catch
    def parse_websocket(self, message: str):
        if message:
            message = json.loads(message)
            request_id = int(message['id']) if 'id' in message else None
            if message.get('method') == 'subscription':
                params = message['params']
                channel = params['channel']
                if channel.startswith('user.trades'):
                    self.parse_fills(params['data'])
                elif channel.startswith('trades'):
                    self.parse_trades(params)
                elif channel.startswith('ticker'):
                    self.parse_orderbook(params)
                else:
                    self.logger.info(
                        f'DeribitGateway: Unrecognized subscription channel when parsing: {params}')
                    # self.logger.exception(
                    #     f'DeribitGateway: Unrecognized subscription channel when parsing: {params}')
            elif request_id in self.place_ids:
                self.parse_place(message)
            elif request_id in self.cancel_ids:
                self.parse_cancel(message)
            elif request_id in self.login_ids:
                self.parse_login(message)
            elif request_id in self.sub_ids:
                self.parse_subs(message)
            else:
                self.logger.info(f'DeribitGateway: unhandled parse websocket message {message}')

    def parse_fills(self, trades: dict):
        for trade in trades:
            ext_id = trade['order_id']
            int_id = self.external_to_internal_map.get(ext_id)
            trade_id = trade['trade_id']
            fill = Fill(
                timestamp=int(trade['timestamp']),
                fill_id=trade_id,
                order_id=int_id,
                account=self.account,
                instrument=None,
                side=Side[trade['direction'].upper()],
                price=float(trade['price']),
                quantity=float(trade['amount']),
                fees=float(trade['fee']),
                fee_currency=trade['fee_currency']
            )
            if ext_id not in self.external_to_internal_map.keys():
                # self.logger.info(f"DeribitGateway: parse_websocket: Fill internal id not in map, "
                #                     f"likely race condition "
                #                     f"with immediate Fill before PlaceAck response received "
                #                     f"OR a manual fill / fill from another strategy")
                self.cached_fills[ext_id].append(fill)  # cached_fills is a defaultdict(list), so safe to append
            else:
                if trade_id in self.acked_fills:
                    self.logger.info(f"DeribitGateway: encountered a fill acked in parse_place {trade_id}")
                    self.acked_fills.remove(trade_id)
                    continue
                self.callbacks.on_order_update(fill)

    def parse_trades(self, message: dict):
        for data in message['data']:
            instrument = self.trade_subsciption_map[data['instrument_name']]
            trade = Trade(
                instrument=instrument,
                side=Side[data['direction'].upper()],
                price=float(data['price']),
                quantity=float(data['amount'])
            )
            self.callbacks.on_marketdata_update(trade)

    def parse_orderbook(self, message: dict):
        last_orderbook_event_dt = dt.datetime.fromtimestamp(message["data"]["timestamp"] / 1000)
        data = message['data']
        instrument = self.orderbook_subscription_map[data['instrument_name']]
        bid_level = OrderbookLevel(
            instrument=instrument,
            side=Side.BUY,
            price=float(data['best_bid_price']),
            quantity=float(data['best_bid_amount'])
        )
        ask_level = OrderbookLevel(
            instrument=instrument,
            side=Side.SELL,
            price=float(data['best_ask_price']),
            quantity=float(data['best_ask_amount'])
        )

        self.callbacks.on_marketdata_update(
            TopOfBookUpdate(instrument=instrument,
                            update_dt=last_orderbook_event_dt,
                            best_bid=bid_level,
                            best_ask=ask_level)
        )

    def parse_place(self, message: dict):
        try:
            if 'result' in message:
                order_dict = message['result']['order']
                internal_id = int(order_dict['label'])
                external_id = order_dict['order_id']
                self.internal_to_external_map[internal_id] = external_id
                self.external_to_internal_map[external_id] = internal_id

                event = PlaceAck(order_id=internal_id,
                                 account=self.account,
                                 instrument=self.internal_id_to_instrument_map[internal_id],
                                 side=Side[order_dict['direction'].upper()],
                                 price=order_dict['price'],
                                 quantity=order_dict['amount'])
                self.callbacks.on_order_update(event)
                self.place_ids.remove(message['id'])

                # A fill is already seen for an order_id due to race condition
                if external_id in self.cached_fills:
                    for fill_update in self.cached_fills[external_id]:
                        fill_update.order_id = internal_id
                        self.callbacks.on_order_update(fill_update)
                    del self.cached_fills[external_id]

                # immediate fill, most likely due to marketable limit orders, send to parse_fills
                if len(message['result']['trades']) > 0:
                    self.parse_fills(message['result']['trades'])
                    self.acked_fills.update([x['trade_id'] for x in message['result']['trades']])
            else:
                if 'error' in message:
                    self.logger.error(
                        f'DeribitGateway: Failed to place order {message["id"]}, message: {message["error"]}')
                else:
                    self.logger.info(f'DeribitGateway: Unrecognized message in parse_place: {message}')
                    # self.logger.exception(f'DeribitGateway: Unrecognized message in parse_place: {message}')
                self.callbacks.on_order_update(PlaceReject(order_id=message['id'], reason=str(message)))
        except Exception as e:
            self.logger.info(f'DeribitGateway Exception: parse_place failed to parse {message}, error {e}')
            # self.logger.exception(f'DeribitGateway Exception: parse_place failed to parse {message}, error {e}')
            self.callbacks.on_order_update(PlaceReject(order_id=message['id'], reason=str(e)))

    def parse_cancel(self, message: dict):
        try:
            if 'result' in message:
                self.callbacks.on_order_update(CancelAck(int(message['result']['label'])))
            else:
                if 'error' in message:
                    self.logger.error(
                        f'DeribitGateway: Failed to cancel order {message["id"]}, message: {message["error"]}')
                else:
                    self.logger.info(f'DeribitGateway: Unrecognized message in parse_cancel: {message}')
                    # self.logger.exception(f'DeribitGateway: Unrecognized message in parse_cancel: {message}')
                self.callbacks.on_order_update(CancelReject(int(message['id']), message))
        except Exception as e:
            self.logger.info(f'DeribitGateway: Unhandled parse_cancel exception {e}')
            # self.logger.exception(f'DeribitGateway: Unhandled parse_cancel exception {e}')
            self.callbacks.on_order_update(CancelReject(message['id'], str(e)))

    def parse_login(self, message: dict):
        if 'result' in message:
            self.logger.info('Logged in')

    def parse_subs(self, message: dict):
        if 'result' in message:
            self.logger.info(f"Subscribed to {message['result']} channel")

    def notify_disconnect(self):
        self.logger.info("DeribitGateway: notify_disconnect: propagate GatewayDisconnect")
        self.callbacks.on_gateway_update(GatewayDisconnect(self.account))
        self.reconnect()

    def reconnect(self):
        self.logger.info("DeribitGateway: reconnect: new websocket and re-run")
        self.websocket_client = WebsocketClient(self.executor, self.config["host"],
                                                self.parse_websocket, self.notify_disconnect)
        self.run()

    def run(self):
        self.logger.info("DeribitGateway: run: connecting to websocket")
        status = asyncio.Event()
        task = self.executor.create_task(self.websocket_client.run(status))
        self.tasks.add(task)

        self.logger.info("DeribitGateway: run: logging in")
        task = self.executor.create_task(self.login(status))
        self.tasks.add(task)