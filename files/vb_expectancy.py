#!/usr/bin/env python
# coding: utf-8

# # VB expectancy reserach 
# 
# This is to plot signal and expectancy relationship
# 

# ## Import data and libraries

# In[ ]:


import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


# In[ ]:


filter_dup = True
split_cnt = 1

config = {
    "common": {
        "taker_rate": 1.6/10000,
        "maker_rate": 0.0/10000,
        "trade_size": 1.0, #in BTC
    },
    "model": {
        "duration_consecutive": [(7,2), (7,3), (7,5), (10,2), (10,3), (10,5)],
        "expectancy_measurement_bars": [30],
        "trend_period": [30],
        "trend_follow": [False],
        "dispersion": [(0.050, 10000), (0.030, 0.050), (0.015, 0.030), (0.005, 0.015), (0.000, 0.005)], 
    },
    "//model": {
        "duration_consecutive": [(10,5)],
        "expectancy_measurement_bars": [30],
        "trend_period": [30],
        "trend_follow": [False],
        "dispersion": [(0.000, 0.005)], 
    },    
    "data": {
        "vbar_file": '../hist_data/vb/volume_bar_btcusdt_20220101_20230630_3880.csv',
        #"vbar_file": '../hist_data/vb/volume_bar_btcusdt_20210101_20211231_3880.csv',
        "split_cnt": split_cnt,  # 1 means no split
        "use_range_filter": True,
        "start_date": "2022-01-01", 
        "end_date": "2022-12-31"
    },     
    "plots": {
        "show_plots": True,
        "xticks_interval": 10,
        "color_actual": "#001f3f",
        "color_train": "#3D9970",
        "color_val": "#0074D9",
        "color_pred_train": "#3D9970",
        "color_pred_val": "#0074D9",
        "color_pred_test": "#FF4136",
    },
    "verbose": False
}


# In[ ]:


df_vb = None
df_order = None
df_trade = None

def get_model_str(model):
    short_key_map={
        'duration_multiple': 'dur', 
        'consecutive': 'con',
        'expectancy_measurement_bars': None, 
        'trend_period': 'trend', 
        'dispersion': 'tp30_range', 
    }

    s= "".join(["_" + short_key_map[key] + "_" + str(model[key]) if short_key_map[key] is not None else "" for key in model])
    return s.replace("(","").replace(")","").replace(",","_").replace(" ","")

def load_data(split_idx, model):
    global df_vb
   
    duration = model['duration_multiple']
    consecutive= model['consecutive']
    trend_period= model['trend_period']
    
    df_vb = pd.read_csv(config['data']['vbar_file'])

    # Set the timestamp to be the index for the data
    df_vb['ts_local'] = pd.to_datetime(df_vb['localTimestamp'])
    
    
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

    df_vb['duration']=(df_vb['ts_close']-df_vb['ts_open']).dt.total_seconds()
    df_vb['duration_sma100'] = df_vb['duration'].rolling(100).mean()
    #df_vb['duration_sma100'] = df_vb['duration'].rolling(1008).mean()  #144 for day, 1008 for week 4032 for month
    
    df_vb['duration_ratio'] = (df_vb['duration_sma100']/df_vb['duration'] > duration) # & (df_vb['duration_sma100']/df_vb['duration'] < 20)
    df_vb['consecutive'] = df_vb['duration_ratio'].rolling(consecutive).sum()

    df_vb['bwd30_open'] = df_vb.open.shift(30)
    df_vb['bwd6_open'] = df_vb.open.shift(6)

    df_vb['vol_imb'] = df_vb.buyVolume - df_vb.sellVolume

    df_vb['tp6_aggr'] = df_vb.vol_imb.rolling(6).sum()
    
    df_vb['tp6']= df_vb['close'] - df_vb['bwd6_open']
    df_vb['tp30']= df_vb['close'] - df_vb['bwd30_open']
        
    if config['verbose']:
        pd.set_option('display.max_rows', 20)
        print(df_vb)
        len(df_vb)
        
        
        


# ### Generate the VB signals

# In[ ]:


#@numba.njit
def process_orders(b, ts_close, model):
    n = len(b)
    #b = np.full(n, 0, dtype=np.int32)
    #print(b)
    
    #prev_buy_distance = expectancy
    #prev_sell_distance = expectancy
    

    dps = []
    
    prev_candidate_signal_index = -1
    for i in range(30, n-50):
        
        current_price = b[i][1]
        
        #book entry order
        side = signal = b[i][0]
        entry_price = b[i][1]
        
        if signal != 0:
            if not filter_dup or i - prev_candidate_signal_index > 1:
                ret={"bar_seq":[], "expectancy": []}
                for j in range(0,51):
                    bps = side * (b[i+j][1] - current_price)/current_price * 10000
                    ret["bar_seq"].append(j)
                    ret["expectancy"].append(bps)
                dps.append((ret, ts_close[i]))
            prev_candidate_signal_index = i    
    return dps

def calculate_signal(model):
    global df_vb
    global df_order
    
    consecutive = model['consecutive']
    dispersion = model["dispersion"]

    #mean reversion only
    df_vb['signal'] = 0
    df_vb['signal'] = np.where((df_vb.consecutive >= consecutive) & (- dispersion[1] < (df_vb.close - df_vb.bwd30_open)/df_vb.bwd30_open) & ((df_vb.close - df_vb.bwd30_open)/df_vb.bwd30_open <= - dispersion[0]) ,  1, df_vb.signal)
    df_vb['signal'] = np.where((df_vb.consecutive >= consecutive) & (  dispersion[1] > (df_vb.close - df_vb.bwd30_open)/df_vb.bwd30_open) & ((df_vb.close - df_vb.bwd30_open)/df_vb.bwd30_open >=   dispersion[0]) , -1, df_vb.signal)
    
    dps = process_orders(df_vb[['signal', 'close']].to_numpy(), df_vb['ts_close'].to_numpy(), model)
    return dps


# In[ ]:





# In[ ]:


def plot_cumulative_return(model, dps, split_index, use_average):
    
    plt.figure(figsize=(10, 7))
    
    title=get_model_str(model)[1:]
    if config["data"]["split_cnt"] == 4:        
        title +="_qtr_"+str(split_index+1)
    if use_average:
        title +="_average"
    filename = 'expectancy_cureve_vb_3880_%s.png'%title    
    csv_file = 'expectancy_cureve_vb_3880_%s.csv'%title    

    print(f"{filename} has {len(dps)} data points")
    
    if not use_average:
        print(f"{filename} #datapoints = {len(dps)}")

        for dp in dps:
            df_expe = pd.DataFrame(dp[0])  
            plt.plot(df_expe.bar_seq, df_expe.expectancy)
            #plt.plot(x, np.sin(x), label = "curve 1")
            #plt.legend()
            plt.xlabel('Bar sequence')
            plt.ylabel('Expectancy (bps)')
            

        #generate csv file for the expectancy data
        df_expe = pd.DataFrame()    
        for dp in dps:
            row = pd.DataFrame(dp[0])[['expectancy']].T
            row['ts_close'] = dp[1]
            df_expe = pd.concat([df_expe, row], ignore_index=True)
        
        df_expe = pd.merge(left=df_expe, right=df_vb, how='left', left_on='ts_close', right_on='ts_close')
        
        print ("columns=", df_expe.columns)
        
        
        cols=[i for i in range(1,51)]
        cols=['ts_close', 'open', 'high', 'low', 'close', 'volume', 'buyVolume', 'sellVolume', 'trades', 'vwap', 'ts_open', 'ts_close', 'duration', 'duration_sma100', 'duration_ratio', 'consecutive', 'vol_imb', 'tp6_aggr', 'tp6', 'tp30', 'signal'] + cols
        
        #print("cols=", cols)
        df_expe = df_expe[cols]
        
    
        #print(df_expe)
        
        df_expe.to_csv(csv_file, index=False)
            
    else:
        if len(dps) == 0:
            print(f"{filename} ignored, no data points available")
            return

        df_expe = pd.concat([pd.DataFrame(dp[0]) for dp in dps], ignore_index=True)
        
        df_expe = df_expe.groupby('bar_seq')[['expectancy']].mean()
        #print("df_expe=\n", df_expe)
        #plt.plot(df_expe.bar_seq, df_expe.expectancy)
        df_expe.plot()
        #plt.plot(x, np.sin(x), label = "curve 1")
        #plt.legend()
        plt.xlabel('Bar sequence')
        plt.ylabel('Avg Expectancy (bps)')
        
    plt.title(title)
    plt.savefig(filename)    
    #plt.show()


# In[ ]:


model={}

models = [{'duration_multiple': duration_consecutive[0],
          'consecutive': duration_consecutive[1],
          'expectancy_measurement_bars': expectancy,
          'trend_period': trend_period,
          'dispersion': dispersion,
          }
          #for duration in config['model']['duration_multiple']
          #for consecutive in config['model']['consecutive']
          for duration_consecutive in config['model']['duration_consecutive']
          for expectancy in config['model']['expectancy_measurement_bars']
          for trend_period in config['model']['trend_period']
          for dispersion in config['model']['dispersion']
        ]

for model in models:
    #for option in (False, True):
    for option in (False,):
        #test_options["atr_reverse"]["active"] = option
        print ("atr_reverse.active=", option)

        print(f"model={model}")

        for split_idx in range(config['data']['split_cnt']):
            load_data(split_idx, model)
            dps=calculate_signal(model)
            plot_cumulative_return(model, dps, split_idx, True)
            plot_cumulative_return(model, dps, split_idx, False)


