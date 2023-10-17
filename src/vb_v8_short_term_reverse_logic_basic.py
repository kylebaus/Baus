#!/usr/bin/env python
# coding: utf-8

# # VB (v8) Short Term Prediction Using 3880 Bars, implementation of the following with focus on the reverse logic basic test

# https://docs.google.com/document/d/1lpudJs5gkXs55fUjEfrKdffDQMl6Np1qj84ct13RcAk/edit


# ## Import data and libraries

# In[284]:


import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# In[286]:

use_abs_tp6_tp30_cmp_for_category = False
enable_tp_sl_cap = True
do_inverse_signal = True
stop_loss_start_after_3_bars = True

config = {
    "common": {
        "taker_rate": 3.0/10000,
        "maker_rate": 0.0/10000,
        "trade_size": 1.0, #in BTC
    },
    "model": {
        "implementation": ["1a", "1b"],
        "sl_multiples": [0.1, 0.3, 0.8,],
    },
    "data": {
        "vbar_file": '../hist_data/vb/volume_bar_btcusdt_20220101_20230630_3880.csv',
        #"vbar_file": '../hist_data/vb/volume_bar_btcusdt_20210101_20211231_3880.csv',
        "split_cnt": 1,  # 1 means no split
        "use_range_filter": True,
        "start_date": "2022-01-01", 
        "end_date": "2022-12-30"
    },     
    "plots": {
        "show_plots": False,
        "save_plots": True,
    },
    "verbose": False
}


# In[ ]:

#see https://www.codearmo.com/blog/sharpe-sortino-and-calmar-ratios-python
def sharpe_ratio(return_series, N, rf):
    mean = return_series.mean()
    sigma = return_series.std()
    return (mean - rf) / sigma * np.sqrt(N)

def sortino_ratio(series, N,rf):
    mean = series.mean()-rf
    std_neg = series[series<0].std()
    return mean/std_neg * np.sqrt(N)

def max_drawdown_with_reinvest(return_series):
    comp_ret = (return_series+1).cumprod()
    peak = comp_ret.expanding(min_periods=1).max()
    dd = (comp_ret/peak)-1
    return dd.min()

def max_drawdown(return_series):    
    comp_ret = return_series.cumsum()+1
    peak = comp_ret.expanding(min_periods=1).max()
    dd = (comp_ret/peak)-1
    return dd.min()


# In[287]:


df_vb = None
df_order = None
df_full_vb = None
df_full_order = None

def get_model_str(model):
    short_key_map={
        'implementation': 'impl',
        'sl_multiples': 'sl_multiples'
    }

    return "".join(["_" + short_key_map[key] + "_" + str(model[key]) if short_key_map[key] is not None else "" for key in model])

def load_data(split_idx, model):
    global df_vb
    
    #in sample
    df_vb = pd.read_csv(config['data']['vbar_file'])

    # Convert timestamp to datetime type
    df_vb['ts_local'] = pd.to_datetime(df_vb['localTimestamp'])
    
    # If range filter is used, limit data to the range
    if config['data']['use_range_filter']:
        start_date = pd.to_datetime(config['data']['start_date'])
        end_date = pd.to_datetime(config['data']['end_date'])
   
        print(f"Using date in range [{start_date}, {end_date})")
        df_vb = df_vb[df_vb['ts_local'] >= start_date]
        df_vb = df_vb[df_vb['ts_local'] < end_date]
        
       
    data_len = len(df_vb) 
    split_cnt = config['data']['split_cnt']
    split_len = data_len // split_cnt
    df_vb = df_vb[split_idx * split_len: (split_idx+1) * split_len]
    

    #df_vb.set_index('ts_local')
    df_vb['ts_close']=pd.to_datetime(df_vb['closeTimestamp'])
    df_vb['ts_open']=pd.to_datetime(df_vb['openTimestamp'])
    
    duration = 15
    consecutive = 15

    df_vb['duration']=(df_vb['ts_close']-df_vb['ts_open']).dt.total_seconds()
    df_vb['duration_sma100'] = df_vb['duration'].rolling(100).mean()
    df_vb['duration_ratio'] = (df_vb['duration_sma100']/df_vb['duration'] > duration)

    df_vb['consecutive'] = df_vb['duration_ratio'].rolling(consecutive).sum()


    df_vb['open_close_bps'] = abs((df_vb['open'] - df_vb['close'])/df_vb['open']*10000)
    
    df_vb['bwd1_close'] = df_vb.close.shift(1)
    df_vb['bwd2_close'] = df_vb.close.shift(2)
    
    
    df_vb['bwd30_open'] = df_vb.open.shift(30)
    
    df_vb['bwd6_open'] = df_vb.open.shift(6)
    df_vb['bwd7_open'] = df_vb.open.shift(7)
    df_vb['bwd8_open'] = df_vb.open.shift(8)
    df_vb['bwd1_close'] = df_vb.close.shift(1)
    df_vb['bwd2_close'] = df_vb.close.shift(2) 
    
    df_vb['vol_imb'] = df_vb.buyVolume - df_vb.sellVolume
    
    df_vb['tp6_aggr'] = df_vb.vol_imb.rolling(6).sum()  
    df_vb['tp6']= df_vb['close'] - df_vb['bwd6_open']
    df_vb['tp30']= df_vb['close'] - df_vb['bwd30_open']
    
    if config['verbose']:
        pd.set_option('display.max_rows', 20)
        print(df_vb)
        len(df_vb)

# ### Generate the VB signals

# In[289]:

#@numba.njit
def process_orders(b, ts_close, model):
    n = len(b)
    
    entry_id = 1
    
    pending_order_indices = []
    
    ret={"bar_seq":[], "entry_id": [], "order_side": [], "entry_exit_type": [], 
         "entry_price": [], "exit_price": [], "target_tp_px": [], "target_sl_px": [], "ts_entry": [], "ts_exit": [], "ts_close":[], "qty":[], "exit_condition":[], "tp6_greater": [], "tp6_aggr_more_buy": [], "bwd6_open": [], "bwd7_open": [], "bwd8_open": [], 'duration_ratio': []}
    # order_side: 1 buy,-1 sell, 0 else

    implementation = model["implementation"] 
    sl_multiples = model["sl_multiples"]
    
    for i in range(8, n):

        signal, current_price, tp6, tp30, tp6_aggr, open_px, high1, low1, vol_imb1, bwd6_open1, bwd7_open1, bwd8_open1, duration_ratio1 = b[i-1]
        signal, current_price, tp6, tp30, tp6_aggr, open_px, high2, low2, vol_imb2, bwd6_open2, bwd7_open2, bwd8_open2, duration_ratio2 = b[i-2]
        signal, current_price, tp6, tp30, tp6_aggr, open_px, high, low, vol_imb, bwd6_open, bwd7_open, bwd8_open,  duration_ratio = b[i]
        
        bar_seq = i + 1
        
        # take profit
        for po_idx in range(0, len(pending_order_indices)):
            row_idx = pending_order_indices[po_idx]
            #print("row_idx=", row_idx, "po_idx=", po_idx, "pending_order_indices=", pending_order_indices)
            if row_idx is not None:
                exit_condition = ret["exit_condition"][row_idx]
                side = ret["order_side"][row_idx]
                tp_px = ret["target_tp_px"][row_idx]
                tp6_greater = ret["tp6_greater"][row_idx]
                tp6_aggr_more_buy = ret["tp6_aggr_more_buy"][row_idx]
                if side == 1:
                    if high >= tp_px:
                        ret["bar_seq"].append(bar_seq)
                        ret["entry_id"].append(ret["entry_id"][row_idx])
                        ret["order_side"].append(-side)
                        ret["entry_exit_type"].append('take profit') 
                        ret["entry_price"].append(ret["entry_price"][row_idx])
                        ret["target_tp_px"].append(None)
                        ret["target_sl_px"].append(None)                         
                        ret["exit_price"].append(tp_px) 
                        ret["ts_close"].append(ts_close[i])
                        ret["ts_entry"].append(ret["ts_close"][row_idx])
                        ret["ts_exit"].append(ts_close[i])
                        ret["qty"].append(1.0)
                        ret["exit_condition"].append(exit_condition)
                        ret["tp6_greater"].append(tp6_greater)
                        ret["tp6_aggr_more_buy"].append(tp6_aggr_more_buy)
                        ret["bwd6_open"].append(bwd6_open)
                        ret["bwd7_open"].append(bwd7_open)
                        ret["bwd8_open"].append(bwd8_open)
                        ret['duration_ratio'] = duration_ratio
                    
                        pending_order_indices[po_idx] = None
                if side == -1:
                    if low <= tp_px:
                        ret["bar_seq"].append(bar_seq)
                        ret["entry_id"].append(ret["entry_id"][row_idx])
                        ret["order_side"].append(-side)
                        ret["entry_exit_type"].append('take profit') 
                        ret["entry_price"].append(ret["entry_price"][row_idx])
                        ret["target_tp_px"].append(None)
                        ret["target_sl_px"].append(None)                         
                        ret["exit_price"].append(tp_px) 
                        ret["ts_close"].append(ts_close[i])
                        ret["ts_entry"].append(ret["ts_close"][row_idx])
                        ret["ts_exit"].append(ts_close[i])
                        ret["qty"].append(1.0)
                        ret["exit_condition"].append(exit_condition)
                        ret["tp6_greater"].append(tp6_greater)
                        ret["tp6_aggr_more_buy"].append(tp6_aggr_more_buy)  
                        ret["bwd6_open"].append(bwd6_open)        
                        ret["bwd7_open"].append(bwd7_open)
                        ret["bwd8_open"].append(bwd8_open)
                        ret['duration_ratio'] = duration_ratio                  
             
                        pending_order_indices[po_idx] = None


        # exit by stop loss
        reverse_orders = []
       
        for po_idx in range(0, len(pending_order_indices)):
            row_idx = pending_order_indices[po_idx]
            if row_idx is not None:
                
                
                # Reverse Logic Basic Test: rule 3. Stop Loss should not be allowed for the first 3 bars.  Notably, some losses will surpass 50bp…. In which case if they are at a loss exceeding 50bp at bar3 close then the system should execute stop loss at bar4 open. 

                exit_condition = ret["exit_condition"][row_idx]
                side = ret["order_side"][row_idx]
                sl_px = ret["target_sl_px"][row_idx]

                if stop_loss_start_after_3_bars:
                    if bar_seq <= ret["bar_seq"][row_idx] + 1: continue

                    # since we have to wait for 3 bars, the stop loss could be over the target stoplss price. if that happens, exit immediately using the open price.                 
                    if -side == 1:
                        if open_px > sl_px: 
                            sl_px = open_px
                    else:
                        if open_px < sl_px: 
                            sl_px = open_px
                
                sl_qty = ret["qty"][row_idx]
                if (side == 1 and low < sl_px) or (side == -1 and high > sl_px):
                    ret["bar_seq"].append(bar_seq)
                    ret["entry_id"].append(ret["entry_id"][row_idx])
                    ret["order_side"].append(-side)
                    ret["entry_exit_type"].append(f'condition: {exit_condition}: basic stop loss') 
                    ret["entry_price"].append(ret["entry_price"][row_idx])
                    ret["target_tp_px"].append(None)
                    ret["target_sl_px"].append(None)           
                    ret["exit_price"].append(sl_px) 
                    ret["ts_close"].append(ts_close[i])
                    ret["ts_entry"].append(ret["ts_close"][row_idx])
                    ret["ts_exit"].append(ts_close[i])
                    ret["qty"].append(sl_qty)
                    ret["exit_condition"].append(exit_condition)
                    ret["tp6_greater"].append(tp6_greater)
                    ret["tp6_aggr_more_buy"].append(tp6_aggr_more_buy)  
                    ret["bwd6_open"].append(bwd6_open)  
                    ret["bwd7_open"].append(bwd7_open)
                    ret["bwd8_open"].append(bwd8_open)
                    ret['duration_ratio'] = duration_ratio                        
                    pending_order_indices[po_idx] = None
                
                    if exit_condition != "stoploss reverse":        
                        reverse_orders.append([-side, sl_px, abs(sl_px - ret["entry_price"][row_idx])])
                        
        pending_order_indices = [i for i in pending_order_indices if i is not None]
        
        # book stop loss/reverse order
        for side, entry_price, tp_amount in reverse_orders:
            signal = side
                
            exit_condition = "stoploss reverse"
            if use_abs_tp6_tp30_cmp_for_category:
                tp6_greater = abs(tp6) > abs(tp30)
            else:
                tp6_greater = tp6 > tp30

            tp6_aggr_more_buy = tp6_aggr > 0  
            
            target_tp_px = entry_price + side * tp_amount
            target_sl_px = entry_price - side * tp_amount

            if side == 1:
                if enable_tp_sl_cap:
                    # New rule: Can we add a cap to prevent any stop loss from exceeding 75bp and take profit from exceeding 35bp?   Some of the “tails” are too extreme in their current form.
                    target_tp_px = min(target_tp_px, entry_price * (1 + 0.0025))
                    target_sl_px = max(target_sl_px, entry_price * (1 - 0.0030 * sl_multiples))                    
                    
                #Reverse Logic Basic Test: rule 1
                target_tp_px = max(target_tp_px, entry_price * (1 + 0.0020))
                target_sl_px = min(target_sl_px, entry_price * (1 - 0.0010 * sl_multiples))              
            else:
                if enable_tp_sl_cap:
                    # New rule: Can we add a cap to prevent any stop loss from exceeding 75bp and take profit from exceeding 35bp?   Some of the “tails” are too extreme in their current form.
                    target_tp_px = max(target_tp_px, current_price * (1 - 0.0025))
                    target_sl_px = min(target_sl_px, current_price * (1 + 0.0030 * sl_multiples))                    

                #Reverse Logic Basic Test: rule 1
                target_tp_px = min(target_tp_px, current_price * (1 - 0.0020))
                target_sl_px = max(target_sl_px, current_price * (1 + 0.0010 * sl_multiples))                              
            
            
            ret["bar_seq"].append(bar_seq)
            ret["entry_id"].append(entry_id)
            ret["order_side"].append(side)
            ret["entry_exit_type"].append('entry order')      # entry order
            ret["exit_price"].append(None)
            ret["entry_price"].append(entry_price)
            ret["target_tp_px"].append(target_tp_px)
            ret["target_sl_px"].append(target_sl_px)           
            ret["ts_close"].append(ts_close[i])
            ret["ts_entry"].append(ts_close[i])
            ret["ts_exit"].append(None)
            ret["qty"].append(1.0)

            ret["exit_condition"].append(exit_condition)
            ret["tp6_greater"].append(tp6_greater)
            ret["tp6_aggr_more_buy"].append(tp6_aggr_more_buy)
            ret["bwd6_open"].append(bwd6_open)
            ret["bwd7_open"].append(bwd7_open)
            ret["bwd8_open"].append(bwd8_open)
            ret['duration_ratio'] = duration_ratio
            
            entry_id += 1
            pending_order_indices.append(len(ret["entry_id"])-1)

        #book entry order
        side = signal = b[i][0]
        entry_price = b[i][1]
        
        if signal != 0:
            if signal == 1:
                
                if implementation == "1a" or implementation == "1b":
                    X_tp = abs(current_price - open_px)
                    Y_tp = X_tp / 2
                                        
                    X_sl = current_price - low
                    
                if implementation == "1a":
                    target_tp_px = current_price + Y_tp
                    target_sl_px = min(low, current_price - X_sl * sl_multiples)
                    
                elif implementation == "1b":
                    target_tp_px = current_price + X_tp
                    target_sl_px = min(low, current_price - X_sl * sl_multiples)
                    
                if enable_tp_sl_cap:
                    # New rule: Can we add a cap to prevent any stop loss from exceeding 75bp and take profit from exceeding 35bp?   Some of the “tails” are too extreme in their current form.
                    target_tp_px = min(target_tp_px, current_price * (1 + 0.0025))
                    target_sl_px = max(target_sl_px, current_price * (1 - 0.0030 * sl_multiples))                    
                    
                #Reverse Logic Basic Test: rule 1
                target_tp_px = max(target_tp_px, current_price * (1 + 0.0020))
                target_sl_px = min(target_sl_px, current_price * (1 - 0.0010 * sl_multiples))                    
                    
            else:
                if implementation == "1a" or implementation == "1b":
                    #Reverse Logic Basic Test: rule 2
                    X_tp = abs(current_price - open_px)
                    Y_tp = X_tp / 2

                    X_sl = high - current_price
            
                if implementation == "1a":
                    target_tp_px = current_price - Y_tp
                    target_sl_px = max(high, current_price + X_sl * sl_multiples)
                        
                elif implementation == "1b":
                    target_tp_px = current_price - X_tp           
                    target_sl_px = max(high, current_price + X_sl * sl_multiples)
                             
                if enable_tp_sl_cap:
                    # New rule: Can we add a cap to prevent any stop loss from exceeding 75bp and take profit from exceeding 35bp?   Some of the “tails” are too extreme in their current form.
                    target_tp_px = max(target_tp_px, current_price * (1 - 0.0025))
                    target_sl_px = min(target_sl_px, current_price * (1 + 0.0030 * sl_multiples))                    

                #Reverse Logic Basic Test: rule 1
                target_tp_px = min(target_tp_px, current_price * (1 - 0.0020))
                target_sl_px = max(target_sl_px, current_price * (1 + 0.0010 * sl_multiples))                    
        
            exit_condition = None
            if use_abs_tp6_tp30_cmp_for_category:
                tp6_greater = abs(tp6) > abs(tp30)
            else:
                tp6_greater = tp6 > tp30

            tp6_aggr_more_buy = tp6_aggr > 0
            
                           
            ret["bar_seq"].append(bar_seq)
            ret["entry_id"].append(entry_id)
            ret["order_side"].append(side)
            ret["entry_exit_type"].append('entry order')      # entry order
            ret["exit_price"].append(None)
            ret["entry_price"].append(entry_price)
            ret["target_tp_px"].append(target_tp_px)
            ret["target_sl_px"].append(target_sl_px)
            ret["ts_close"].append(ts_close[i])
            ret["ts_entry"].append(ts_close[i])
            ret["ts_exit"].append(None)
            ret["qty"].append(1.0)
            
            ret["exit_condition"].append(exit_condition)
            ret["tp6_greater"].append(tp6_greater)
            ret["tp6_aggr_more_buy"].append(tp6_aggr_more_buy)
            ret["bwd6_open"].append(bwd6_open)
            ret["bwd7_open"].append(bwd7_open)
            ret["bwd8_open"].append(bwd8_open)
            ret['duration_ratio'] = duration_ratio
            
            entry_id += 1
            pending_order_indices.append(len(ret["entry_id"])-1)
           
            
    return ret

def calculate_signal(model):
    global df_vb
    global df_order
    df_vb['signal'] = 0
    
    #mean reversion only
    df_vb['signal'] = 0

    df_vb['date'] = pd.to_datetime(df_vb['ts_close']).dt.date

    #condition 1
    df_vb['signal'] = np.where( (df_vb.bwd6_open > df_vb.bwd7_open) & 
                                (df_vb.bwd6_open > df_vb.bwd8_open) & 
                                (df_vb.close > df_vb.bwd1_close) & 
                                (df_vb.close > df_vb.bwd2_close), 1, df_vb.signal) 

    #condition 2    
    df_vb['signal'] = np.where( (df_vb.bwd6_open > df_vb.bwd7_open) & 
                                (df_vb.bwd6_open > df_vb.bwd8_open) & 
                                (df_vb.close < df_vb.bwd1_close) & 
                                (df_vb.close < df_vb.bwd2_close), -1, df_vb.signal) 

    #condition 1
    df_vb['signal'] = np.where( (df_vb.bwd6_open < df_vb.bwd7_open) & 
                                (df_vb.bwd6_open < df_vb.bwd8_open) & 
                                (df_vb.close < df_vb.bwd1_close) & 
                                (df_vb.close < df_vb.bwd2_close), -1, df_vb.signal) 
    
    #condition 2
    df_vb['signal'] = np.where( (df_vb.bwd6_open < df_vb.bwd7_open) & 
                                (df_vb.bwd6_open < df_vb.bwd8_open) & 
                                (df_vb.close > df_vb.bwd1_close) & 
                                (df_vb.close > df_vb.bwd2_close), 1, df_vb.signal) 
    
    #if not meeting basic requirement, no signal 
    df_vb['signal'] = np.where( ~(((df_vb.close <= 25000) & (df_vb.open_close_bps >= 25)) | ((df_vb.close > 25000) & (df_vb.open_close_bps >= 20))), 0, df_vb.signal) 
    
    
    #additional rules 1:
    df_vb['signal'] = np.where( ~((df_vb.close <= 25000) | (abs(df_vb.bwd8_open - df_vb.bwd6_open)/df_vb.bwd8_open > 0.0015)), 0, df_vb.signal) 
    

    #additional rules 2:
    df_vb['signal'] = np.where( ~((df_vb.close > 25000) | (abs(df_vb.bwd8_open - df_vb.bwd6_open)/df_vb.bwd8_open > 0.0030)), 0, df_vb.signal) 
   
    #additional rule added on Aug 9: We want to AVOID duration_ratio of True (can defer to any Duration 7 with consecutive 1+).  If we are in a trade and the duration ratio turns “True” for a bar, we want to play out that trade and then cease all new trades from entering as part of the strategy until 6 bars have gone by without any “True” duration_ratio bars.
    df_vb['signal'] = np.where( (df_vb.consecutive > 0), 0, df_vb.signal) 
    
    
    if do_inverse_signal:
        df_vb['signal'] = - df_vb['signal']
            
    df_vb['consecutive']

    if use_abs_tp6_tp30_cmp_for_category:
        df_vb['tp6_greater'] = abs(df_vb['tp6']) > abs(df_vb['tp30'])
    else:
        df_vb['tp6_greater'] = df_vb['tp6'] > df_vb['tp30']
    df_vb['tp6_aggr_more_buy'] = df_vb['tp6_aggr'] > 0
    
    df_order = pd.DataFrame(process_orders(df_vb[['signal', 'close', 'tp6', 'tp30', 'tp6_aggr','open','high','low', 'vol_imb', 'bwd6_open', 'bwd7_open', 'bwd8_open', 'duration_ratio']].to_numpy(), df_vb['ts_close'].to_numpy(), model))
    
    df_order['bwd8_open-bwd6_open'] = df_order['bwd8_open'] - df_order['bwd6_open'] 
    df_order['bwd7_open-bwd6_open'] = df_order['bwd7_open'] - df_order['bwd6_open'] 
    df_order['bwd6_open-entry_price'] = df_order['bwd6_open'] - df_order['entry_price'] 

# In[291]:


def calculate_return(model):
    global df_order
    # the market returns during the execution of the strategy.
    
    taker_rate = config['common']['taker_rate']
    maker_rate = config['common']['maker_rate']
    trade_size = config['common']['trade_size']
    
    #Note: order_side is the exit order side
    df_order['return'] = df_order['order_side'] * df_order['qty'] * (df_order['entry_price'] - df_order['exit_price'])/df_order['entry_price'] - (taker_rate + maker_rate)*1.0
    df_order['dollar_return'] = df_order['return'] * 100 # df_order['entry_price'] * trade_size

# In[ ]:
# ### Plot the cumulative returns of the strategy

def plot_cumulative_return(model):
    global df_full_order
    global df_full_vb

    if config['plots']['show_plots'] or config['plots']['save_plots']:
        plt.figure(figsize=(10, 7))
        
        df_full_trade = df_full_order[df_full_order['return'] > 0].copy(deep=False) 
         
        df_full_trade['cum_dollar_return'] = df_full_order['dollar_return'].cumsum()
        df_full_trade['aum'] = df_full_order['dollar_return'].cumsum() + 100
        #df_full_order.plot()
        ax = df_full_trade.plot(x='ts_close', y='aum', color='r')
        
        plt.xlabel('Date')
        plt.ylabel('AUM')
        title=get_model_str(model)
        
        ax2=ax.twinx()
        ax2.set_ylabel('price')
        df_full_vb.plot(ax=ax2, x='ts_close', y='close')
        plt.title(title)
    if config['plots']['save_plots']:
        plt.savefig('vb_v6_3880_%s.png'%title)
    if config['plots']['show_plots']:
        plt.show()

# In[293]:

def get_daily_risk_free_return():
    # daily risk free rate.
    # use the average t-bill from 2022 2nd quarter to 2023 1st quarter (in reverse order): (4.76+4.15+2.74+1.14)/4 = 3.1975
    # use the average t-bill from 2022 2nd quarter to 2023 1st quarter (in reverse order): (4.76+4.15)/2 = 4.455
    return ((1+3.1975/100)**(1/365))-1


def get_monthly_risk_free_return():
    # daily risk free rate.
    # use the average t-bill from 2022 2nd quarter to 2023 1st quarter (in reverse order): (4.76+4.15+2.74+1.14)/4 = 3.1975
    # use the average t-bill from 2022 2nd quarter to 2023 1st quarter (in reverse order): (4.76+4.15)/2 = 4.455
    return ((1+3.1975/100)**(1/12))-1


# In[294]:


model={}

models = [{
          'implementation': implementation,
          "sl_multiples": sl_multiples
          }
          for implementation in config['model']['implementation']
          for sl_multiples in config['model']['sl_multiples']
        ]

summary_items = []

for model in models:
    #for option in (False, True):
    for option in (False,):
        print(f"model={model}")
        df_full_order = pd.DataFrame()
        df_full_vb = pd.DataFrame()

        for split_idx in range(config['data']['split_cnt']):
            load_data(split_idx, model)
            calculate_signal(model)
            calculate_return(model)

            df_full_order = pd.concat([df_full_order, df_order], ignore_index=True)
            df_full_vb = pd.concat([df_full_vb, df_vb], ignore_index=True)

        start_date = config["data"]["start_date"]
        end_date = config["data"]["end_date"]
        all_dates=pd.DataFrame(pd.date_range(start=start_date, end=end_date), columns=["date"])
        all_dates['month'] = all_dates['date'].dt.year * 100 + all_dates['date'].dt.month
        
        all_dates['date'] = pd.to_datetime(all_dates['date']).dt.date
        df_full_order['date'] = pd.to_datetime(df_full_order['ts_close']).dt.date

        df_full_trades = df_full_order[df_full_order.entry_exit_type != 'entry order']

        merged_left = pd.merge(left=all_dates, right=df_full_trades, how='left', left_on='date',right_on='date')
        merged_left['return'] = merged_left['return'].fillna(0)
        
        daily_df = merged_left[["date", "return"]].groupby("date", group_keys=True).sum()
        n_days = len(daily_df)
        
        monthly_df = merged_left[["month", "return"]].groupby("month", group_keys=True).sum()
        
        rf = get_daily_risk_free_return()
        
        rf_montly = get_monthly_risk_free_return()
        
        sharpe = sharpe_ratio(monthly_df['return'], 12, rf_montly)    
        sortino = sortino_ratio(monthly_df['return'], 12, rf_montly)
        max_dd = max_drawdown(daily_df['return'])    
        
        #daily_df.to_csv("daily_return_vb_v6_3880_%s.csv" % get_model_str(model), index=False) 


        total_pnl = df_full_trades["return"].sum()
        total_dollar_pnl = df_full_trades["dollar_return"].sum()
        
        df_trades_by_entry = df_full_trades[["entry_id", "return"]].groupby("entry_id", group_keys=True).sum()
        
        win_trades = len(df_trades_by_entry[df_trades_by_entry["return"]>0])        
        loss_trades = len(df_trades_by_entry[df_trades_by_entry["return"]<0])
        
        #df_trades_by_entry.to_csv("trade_by_entry_vb_v6_3880_%s.csv" % get_model_str(model), index=False)
        
        plot_cumulative_return(model)

        df_full_order = df_full_order.drop(['date'], axis=1) 
        df_full_order.to_csv("order_vb_v6_3880_%s.csv" % get_model_str(model), index=False)    
        df_full_vb.to_csv("signal_vb_v6_3880_%s.csv" % get_model_str(model), index=False)
        
        summary_item_values={k: v for k, v in model.items() if v is not None}
        summary_item_values["start_date"] = start_date
        summary_item_values["end_date"] = end_date
        summary_item_values["win_trades"] = win_trades
        summary_item_values["loss_trades"] = loss_trades
        summary_item_values["total_dollar_pnl"] = total_dollar_pnl
        summary_item_values["sharpe"] = sharpe
        summary_item_values["sortino"] = sortino
        summary_item_values["max_dd"] = max_dd
        summary_items.append(summary_item_values)

      
summary_df = pd.DataFrame(summary_items)

print(summary_df)


# In[295]:

start_date = pd.to_datetime(config['data']['start_date']).strftime('%Y%m%d')
end_date = pd.to_datetime(config['data']['end_date']).strftime('%Y%m%d')

summary_df = summary_df.sort_values(by=['sharpe'], ascending=False)
summary_df.to_csv(f"summary_vb_v6_3880_{start_date}_{end_date}.csv", index=False)
