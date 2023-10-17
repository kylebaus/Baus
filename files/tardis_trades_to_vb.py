'''
Genearte volume based bars from trades files. The tardis trades files must exist in ../hist_data/datasets/ for this to work.
generated files are in hist_data/vb/.

Usage: 
    cd ~/baus_backtesting/hist_data/
    python ../src/tardis_trades_to_vb.py
'''

import copy
import os
from datetime import datetime
import pandas as pd
import pytz

s_start = '20230701'
s_end =   '20230731'
SYMBOL = "BTCUSDT"
EXCHANGE = "binance-futures"

class TradeBar:
    def __init__(self, d_trade_bar):
        self.type = 'trade_bar'
        if d_trade_bar is not None:
            self.symbol = d_trade_bar['symbol']
            self.exchange = d_trade_bar['exchange']
            self.name = d_trade_bar['name']
            self.interval = d_trade_bar['interval']
            self.bar_kind = d_trade_bar['kind']
            self.open = d_trade_bar['open']
            self.high = d_trade_bar['high']
            self.low = d_trade_bar['low']
            self.close = d_trade_bar['close']
            self.volume = d_trade_bar['volume']
            self.buy_volume = d_trade_bar['buyVolume']
            self.sell_volume = d_trade_bar['sellVolume']

            self.trades = d_trade_bar['trades']
            self.vwap = d_trade_bar['vwap']
            self.open_timestamp = d_trade_bar['openTimestamp']
            self.open_timestamp = self.convert_epoch_to_str_time(self.open_timestamp)

            self.close_timestamp = d_trade_bar['closeTimestamp']
            self.close_timestamp = self.convert_epoch_to_str_time(self.close_timestamp)

            self.timestamp = d_trade_bar['timestamp']
            self.timestamp = self.convert_epoch_to_str_time(self.timestamp)

            self.local_timestamp = d_trade_bar['localTimestamp']
            self.local_timestamp = self.convert_epoch_to_str_time(self.local_timestamp)
        else:
            self.symbol = None
            self.exchange = None
            self.name = None
            self.interval = None
            self.bar_kind = None
            self.open = None
            self.high = None
            self.low = None
            self.close = None
            self.volume = None
            self.buy_volume = None
            self.sell_volume = None

            self.trades = None
            self.vwap = None
            self.open_timestamp = None
            self.close_timestamp = None

            self.timestamp = None
            self.local_timestamp = None

    def to_dict(self):
        return {
            'type': self.type,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'name': self.name,
            'interval': self.interval,
            'kind': self.bar_kind,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'buyVolume': self.buy_volume,
            'sellVolume': self.sell_volume,
            'trades': self.trades,
            'vwap': self.vwap,
            'openTimestamp': self.open_timestamp,
            'closeTimestamp': self.close_timestamp,
            'timestamp': self.timestamp,
            'localTimestamp': self.local_timestamp
        }

class TradeBarComputable:
    # use book_change messages as workaround for issue when time passes for new bar to be produced but there's no trades,
    # so logic `compute` would not execute
    # assumption is that if one subscribes to book changes too then there's pretty good chance that
    # even if there are no trades, there's plenty of book changes that trigger computing new trade bar if time passess

    # class init
    def __init__(self, config):
        self.source_data_types = ['trade', 'book_change']
        self.bar_kind = config['bar_kind']
        self.interval = config['interval']
        self.type = 'trade_bar'

        self.in_progress_bar = TradeBar(None)

        self.d_kind_suffix = {
            'tick': 'ticks',
            'time': 'ms',
            'volume': 'vol'
        }

        if config['name'] is None:
            # `${this._type}_${interval}${kindSuffix[kind]}`
            self.name = f'{self.type}_{self.interval}_{self.d_kind_suffix[self.bar_kind]}'
        else:
            self.name = config['name']

        self.reset()

    def compute(self, message):
        if (message.type != 'trade'):
            return

        # update in progress trade bar with new data
        self.update(message)

        if (self.has_new_bar(message.ts_event)):
            return self.compute_bar(message)

    def convert_epoch_to_str_time(self, i_epoch_time):
        dt_time = datetime.fromtimestamp(i_epoch_time / 1_000_000)
        dt_time = dt_time.astimezone(pytz.utc)
        return (dt_time).strftime("%Y-%m-%d %H:%M:%S.%f")

    def compute_bar(self, message):
        #print("message.ts_event=", message.ts_event)
        self.in_progress_bar.local_timestamp = message.ts_event
        # convert epoch time to datetime

        self.in_progress_bar.local_timestamp = self.convert_epoch_to_str_time(self.in_progress_bar.local_timestamp)

        #print("self.in_progress_bar.local_timestamp=", self.in_progress_bar.local_timestamp)

        self.in_progress_bar.symbol = SYMBOL
        self.in_progress_bar.exchange = EXCHANGE

        o_trade_bar = copy.deepcopy(self.in_progress_bar)

        self.reset()

        return o_trade_bar

    def has_new_bar(self, timestamp):
        if self.in_progress_bar.trades == 0:
            return False

        if (self.bar_kind == 'volume'):
            return self.in_progress_bar.volume >= self.interval
        else:
            assert False, 'only volume bars are currently implemented!'

    def update(self, trade):
        is_not_opened_yet = self.in_progress_bar.trades == 0

        if (is_not_opened_yet):
            self.in_progress_bar.open = float(trade.price)
            self.in_progress_bar.open_timestamp = int(trade.ts_event)
            self.in_progress_bar.open_timestamp = self.convert_epoch_to_str_time(self.in_progress_bar.open_timestamp)

        if (self.in_progress_bar.high < float(trade.price)):
            self.in_progress_bar.high = float(trade.price)

        if (self.in_progress_bar.low > float(trade.price)):
            self.in_progress_bar.low = float(trade.price)

        self.in_progress_bar.close = float(trade.price)
        self.in_progress_bar.close_timestamp = int(trade.ts_event)
        # convert to string format
        self.in_progress_bar.close_timestamp = self.convert_epoch_to_str_time(self.in_progress_bar.close_timestamp)

        if (trade.side == 'buy'):
            self.in_progress_bar.buy_volume += float(trade.size)
        if (trade.side == 'sell'):
            self.in_progress_bar.sell_volume += float(trade.size)

        self.in_progress_bar.trades += 1
        self.in_progress_bar.vwap = (
                                            self.in_progress_bar.vwap * self.in_progress_bar.volume + float(
                                        trade.price) * float(trade.size)) / (
                                            self.in_progress_bar.volume + float(trade.size))

        self.in_progress_bar.volume += float(trade.size)
        self.in_progress_bar.timestamp = int(trade.ts_event)
        # convert to string format
        self.in_progress_bar.timestamp = self.convert_epoch_to_str_time(self.in_progress_bar.timestamp)

    def reset(self):
        self.in_progress_bar.type = self.type
        self.in_progress_bar.symbol = ''
        self.in_progress_bar.exchange = ''
        self.in_progress_bar.name = self.name
        self.in_progress_bar.interval = self.interval
        self.in_progress_bar.bar_kind = self.bar_kind

        self.in_progress_bar.open = 0
        self.in_progress_bar.high = float("-inf")
        self.in_progress_bar.low = float("inf")
        self.in_progress_bar.close = 0

        self.in_progress_bar.volume = 0
        self.in_progress_bar.buy_volume = 0
        self.in_progress_bar.sell_volume = 0

        self.in_progress_bar.trades = 0
        self.in_progress_bar.vwap = 0

        self.in_progress_bar.open_timestamp = 0
        self.in_progress_bar.close_timestamp = 0
        self.in_progress_bar.local_timestamp = 0
        self.in_progress_bar.timestamp = 0


# def compute_trade_bars(d_trade_bar_compute_options):
#     return TradeBarComputable(d_trade_bar_compute_options)

# def get_ticks(s_date, catalog):
#     from nautilus_trader.core.datetime import dt_to_unix_nanos

#     start = dt_to_unix_nanos(pd.Timestamp(s_date, tz="UTC"))
#     end = start + 86400000000000

#     ls_ticks = catalog.trade_ticks(start=start, end=end)

#     return ls_ticks


def get_trade_data(s_start, s_end):
    df_trade_return = pd.DataFrame()

    ls_dates = pd.date_range(s_start, s_end).strftime("%Y%m%d").tolist()
    
    #catalog = data_catalog()

    df = None
    for date in ls_dates:
        srcfile=f"../hist_data/datasets/binance-futures_trades_{date}_{SYMBOL}.csv.gz"
        df_new_row = pd.read_csv(srcfile)
        df_trade_return = pd.concat([df_trade_return, df_new_row])

    df_trade_return['type'] = 'trade'
    df_trade_return['ts_event'] = df_trade_return['local_timestamp']
    df_trade_return['size'] = df_trade_return['amount']
    
    #print(df_trade_return)
    return df_trade_return


def build_volume_bars(s_start, s_end, ls_btc_bar_sizes):
    print("building volume bars for: ", s_start, s_end, ls_btc_bar_sizes)
    df_dollar_volume_bars = {}

    # Create a new instance of the TradeBarComputable

    fast_start_date = pd.to_datetime(s_end, utc=True).date()

    ls_trade_bar_computable=[]
    for i_bar_size_btc in ls_btc_bar_sizes:
        config = dict(
            name=None,
            interval=i_bar_size_btc,
            bar_kind="volume"
        )
        out_file = "vb/volume_bar_"+SYMBOL.lower()+"_" + s_start + "_" + s_end + "_" + str(i_bar_size_btc) + ".csv"
        if os.path.exists(out_file):
            df=pd.read_csv(out_file)
            
            existing_local_timestamp =int(pd.to_datetime(df['localTimestamp'].iloc[-1], utc=True).timestamp()*1_000_000)
            fast_start_date = min(fast_start_date, datetime.fromtimestamp(existing_local_timestamp / 1_000_000).date())
        else:
            existing_local_timestamp = 0
            fast_start_date = pd.to_datetime(s_start, utc=True).date()    
            
        ls_trade_bar_computable.append((TradeBarComputable(config), [], out_file, existing_local_timestamp))
    
    print("fast_start_date=", fast_start_date)
    
    for date in pd.date_range(s_start, s_end):

        print(f"Processing date {date}...")        
        if date.date() < fast_start_date:
            print(f"Skip fully processed date {date}")
            continue

        # populate df_trades global by pulling trade data from cache
        df_trade_data = get_trade_data(date, date)

        #test_cnt = 1000000
        for tick in df_trade_data.itertuples():
            for o_trade_bar_computable,df_dollar_volume_bars, out_file, existing_local_timestamp in ls_trade_bar_computable:
                if tick.ts_event <= existing_local_timestamp:
                    continue

                result = o_trade_bar_computable.compute(tick)

                # if result is None, the trade tick does not result in a new bar
                if result is not None:
                    result = result.to_dict()
                    df_new_row = pd.DataFrame.from_dict(result, orient='index').transpose()
                    df_dollar_volume_bars.append(df_new_row) 
                    #print("volume bar computed: ", result)
            #test_cnt -= 1
            #if test_cnt == 0: break    

        for o_trade_bar_computable, df_dollar_volume_bars, out_file, existing_local_timestamp in ls_trade_bar_computable:
            if len(df_dollar_volume_bars) > 0:
                df_merged = pd.concat(df_dollar_volume_bars, ignore_index=True)
                df_merged.reset_index(drop=True, inplace=True)
                df_merged.to_csv(out_file, mode='a', header=not os.path.exists(out_file), index=False)
                df_dollar_volume_bars.clear()

def multiprocess_wrapper(ls_args):
    print("build_volume_bars ", ls_args[0], ls_args[1], ls_args[2])
    return build_volume_bars(ls_args[0], ls_args[1], ls_args[2])

def main():
    #s_end_eod = datetime.strptime(s_end, '%Y%m%d') + pd.Timedelta(hours=24)

    ls_bar_sizes = [1, 2, 3, 5, 10, 15, 20]
    #ls_bar_sizes = [1,2,3]
    f_minute_volume = 388

    ls_btc_bar_sizes = [int(f_minute_volume * i) for i in ls_bar_sizes]

    build_volume_bars(s_start, s_end, ls_btc_bar_sizes)

if __name__ == '__main__':
    main()
