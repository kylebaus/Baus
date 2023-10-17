class ShortTermPredictor:
    def __init__(self, threshold_low=0.002, threshold_high=0.003, price_cutoff=25000):
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high
        self.price_cutoff = price_cutoff
        self.bars = []

    def valid_bar(self, bar):
        open_price, close_price = bar['open'], bar['close']
        difference = abs(open_price - close_price)
        threshold = self.threshold_high if close_price > self.price_cutoff else self.threshold_low
        return difference >= threshold

    def get_trade_signal(self, bar):
        if not self.valid_bar(bar):
            return None
        if len(self.bars) < 3:
            return None

        signal_bar, bar_1, bar_2 = self.bars[-1], self.bars[-2], self.bars[-3]

        # Check the trend of bwd6_open
        if signal_bar['bwd6_open'] > bar_1['bwd6_open'] and signal_bar['bwd6_open'] > bar_2['bwd6_open']:
            if signal_bar['close'] > bar_1['close'] and signal_bar['close'] > bar_2['close']:
                return 'LONG'
            elif signal_bar['close'] < bar_1['close'] and signal_bar['close'] < bar_2['close']:
                return 'SHORT'

        elif signal_bar['bwd6_open'] < bar_1['bwd6_open'] and signal_bar['bwd6_open'] < bar_2['bwd6_open']:
            if signal_bar['close'] < bar_1['close'] and signal_bar['close'] < bar_2['close']:
                return 'SHORT'
            elif signal_bar['close'] > bar_1['close'] and signal_bar['close'] > bar_2['close']:
                return 'LONG'
            
        

        return None

    def add_bar(self, bar):
        self.bars.append(bar)
        if len(self.bars) > 3:
            self.bars.pop(0)

    def process_bar(self, bar):
        self.add_bar(bar)
        return self.get_trade_signal(bar)
