import matplotlib.pyplot as plt
from zmq_sender import send_order
import random
import numpy as np

class MyStrategy:
    def __init__(self):
        self.prices = []
        self.buy_signals = []
        self.sell_signals = []
        self.mean = 0
        self.std_dev = 0
        self.lookback_period = 20
        self.threshold = 2

        # Initialize plot
        plt.ion()
        self.fig, self.ax = plt.subplots()

    def update_prices(self, new_price):
        self.prices.append(new_price)
        if len(self.prices) > self.lookback_period:
            self.prices.pop(0)

    def calculate_statistics(self):
        self.mean = np.mean(self.prices)
        self.std_dev = np.std(self.prices)

    def visualize(self):
        self.ax.clear()
        plt.title("Trading Strategy Visualization")
        plt.xlabel("Time")
        plt.ylabel("Price")

        self.ax.plot(self.prices, label="Price", color="blue")
        self.ax.axhline(y=self.mean + self.threshold * self.std_dev, color='r', linestyle='--', label="Sell threshold")
        self.ax.axhline(y=self.mean - self.threshold * self.std_dev, color='g', linestyle='--', label="Buy threshold")
        
        for buy in self.buy_signals:
            self.ax.plot(buy[0], buy[1], 'go')
        
        for sell in self.sell_signals:
            self.ax.plot(sell[0], sell[1], 'ro')
            
        plt.legend(loc="upper left")
        plt.draw()
        plt.pause(1)

    def generate_order(self):
        current_price = self.prices[-1]

        if current_price > self.mean + self.threshold * self.std_dev:
            order = [b'PT76', b'PLACE PT76AAAAQ20000009546 S ZMQ.BUF/P_BTCUSDT 10 @ 30514.1 (PENDING,PLACE,LIMIT,jynx1)']
            send_order(order)
            self.sell_signals.append([len(self.prices) - 1, current_price])
        elif current_price < self.mean - self.threshold * self.std_dev:
            order = [b'PT76', b'PLACE PT76AAAAQ20000009546 B ZMQ.BUF/P_BTCUSDT 10 @ 30514.1 (PENDING,PLACE,LIMIT,jynx1)']
            send_order(order)
            self.buy_signals.append([len(self.prices) - 1, current_price])

    def execute(self):
        # Simulating price feed. You would replace this with real-time data.
        new_price = random.uniform(30000, 31000)
        self.update_prices(new_price)
        
        if len(self.prices) >= self.lookback_period:
            self.calculate_statistics()
            self.generate_order()
            self.visualize()
