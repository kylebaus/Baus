import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import datetime

mbar_files = ['../hist_data/mbar/mbar_btcusdt_20210101_20211231_60_sec.csv',
              '../hist_data/mbar/mbar_btcusdt_20220101_20221231_60_sec.csv',
              '../hist_data/mbar/mbar_btcusdt_20230101_20230630_60_sec.csv']

df_vb = pd.DataFrame()
for datafile in mbar_files:
    df_vb = pd.concat([df_vb, pd.read_csv(datafile)], ignore_index=True)

df_vb['ts_close']=pd.to_datetime(df_vb['closeTimestamp'])
df_vb['ts_open']=pd.to_datetime(df_vb['openTimestamp'])

df_vb['date'] = pd.to_datetime(df_vb['ts_close']).dt.date

df_day = df_vb[['date', 'ts_close', 'close']]
df_day = df_day.groupby(['date']).last()
df_day = df_day.reset_index()

def hma(df, period):
     wma_1 = df['close'].rolling(period//2).apply(lambda x: \
         np.sum(x * np.arange(1, period//2+1)) / np.sum(np.arange(1, period//2+1)), raw=True)
     wma_2 = df['close'].rolling(period).apply(lambda x: \
         np.sum(x * np.arange(1, period+1)) / np.sum(np.arange(1, period+1)), raw=True)
     diff = 2 * wma_1 - wma_2
     df[f'hma{period}'] = diff.rolling(int(np.sqrt(period))).mean()
     return hma

for period in (6, 30, 45, 60):
    df_day[f'ema{period}'] = df_day['close'].ewm(span=period, adjust=False).mean()
    df_day[f'dema{period}'] = df_day[f'ema{period}']*2 - df_day[f'ema{period}'].ewm(span=period, adjust=False).mean()
    hma(df_day,period)
  
def get_hma30(timestamp):
    return df_day[df_day['date'] >= pd.to_datetime(timestamp)].head(1)['ema30'].values[0]

def get_dema30(timestamp):
    return df_day[df_day['date'] >= pd.to_datetime(timestamp)].head(1)['dema30'].values[0]

df_day_ind = df_day[['date', 'ema6', 'hma30', 'dema30', 'hma45', 'dema45', 'hma60', 'dema60']].copy()    

# a date is mapped to its previous date's indicators for practical use
df_day_ind['date'] = df_day_ind['date'] + datetime.timedelta(days=1)


if __name__ == "__main__":
    #quick test

    # plt.figure(figsize=(10, 7))
    # plt.plot(df_day.ts_close, df_day.close, label='close_px')
    # plt.plot(df_day.ts_close, df_day.dema30, label='dema30')
    # plt.plot(df_day.ts_close, df_day.hma30, label='hma30')
    # plt.title("dema and hma")
    # plt.show()
    
    print("get_hma30('2021-12-31') ->", get_hma30("2021-12-31"))
    print("get_dema30('2021-12-31') ->", get_dema30("2021-12-31"))
   
    print(df_day_ind)
    
