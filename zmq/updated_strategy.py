import zmq
import time
from zmq_sender import cancel_order, send_order  # Make sure zmq_sender.py is in the same directory or in PYTHONPATH
import pandas as pd
import ShortTermPredictor

class SimpleMarketMaker:
    def __init__(self):
        self.bid_price = None
        self.ask_price = None
        self.order_id = 1  # To keep track of order IDs
        self.df_symbol_info = pd.read_csv('buf_symbol_info.csv', header=None)
        self.df_symbol_info.columns = ['exchange_symbol', 'symbol', 'size_multiplier']
        self.symbol = None  # To dynamically handle the trading symbol
        self.quantity_multiplier = 1000  # Multiplier to convert 1 unit to the minimum tradable amount

    def update_order_book(self, parts):
        # Parse Symbol
        self.symbol = parts[0]
        
        # Find index of '|' separator
        separator_index = parts.index("|")
        
        # Parse Bids
        bids = parts[3:separator_index]
        bid_prices = bids[::2]  # Every second element starting from index 0
        bid_volumes = bids[1::2]  # Every second element starting from index 1
        
        # Parse Asks
        asks = parts[separator_index + 1:]
        ask_prices = asks[::2]
        ask_volumes = asks[1::2]
        
        # You can choose to use the first, last, or any other bid and ask
        self.bid_price = float(bid_prices[0])  # Here, I used the first bid
        self.ask_price = float(ask_prices[0])  # Here, I used the first ask



    def execute(self):
        if self.bid_price and self.ask_price and self.symbol:
            mid_price = (self.bid_price + self.ask_price) / 2
            buy_order_price = round(mid_price - 0.5, 1)  # Round to 1 decimal place
            sell_order_price = round(mid_price + 0.5, 1)  # Round to 1 decimal place
            quantity = 10 * self.quantity_multiplier  # Adjust this based on your strategy

            buy_order = [b'PT76', f"PLACE PT76AAAAQ{self.order_id} B ZMQ.{self.symbol} {quantity} @ {buy_order_price} (PENDING,PLACE,LIMIT,jynx1)".encode()]
            send_order(buy_order)
            self.order_id += 1

            sell_order = [b'PT76', f"PLACE PT76AAAAQ{self.order_id} S ZMQ.{self.symbol} {quantity} @ {sell_order_price} (PENDING,PLACE,LIMIT,jynx1)".encode()]
            send_order(sell_order)
            self.order_id += 1

            print(f"Placed quantity {quantity} buy order at: {buy_order_price}, sell order at: {sell_order_price}")
            print(buy_order)


if __name__ == "__main__":
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://54.248.0.145:62297")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    market_maker = SimpleMarketMaker()

    while True:
        message = socket.recv_string()
        parts = message.split(',')

        # print out the data that we receive, all of "parts"
        print("Parts:", parts)

        market_maker.update_order_book(parts)
        market_maker.execute()

        time.sleep(1)  # To prevent high CPU usage