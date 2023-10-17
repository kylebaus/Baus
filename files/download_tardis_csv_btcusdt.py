'''
Downloads trades and/or L1 book data files from tardis.

Usage: 
    cd ~/baus_backtesting/hist_data/
    mkdir -p datasets
    python ../src/download_tardis_csv_btcusdt.py
'''

s_start = "2023-07-01"
s_end   = "2023-07-31"
SYMBOL = "BTCUSDT"
data_types=["trades"]
#data_types=["trades", "incremental_book_L2"],
#data_types=["incremental_book_L2"],

import os
import logging
from datetime import timedelta, datetime

import pandas as pd
from tardis_dev import datasets, get_exchange_details
from tqdm import tqdm

def download_tardis():
    
    TARDIS_API_KEY="TD.dFOmPVJ2cc4Tlob6.VuN4h5OxTXihxx1.JfLxcoxhK9ExqIw.Rh3S6YRwImlTPsS.GzivdR3Mq7aMJiY.4p94"

    # comment out to disable debug logs
    logging.basicConfig(level=logging.INFO)

    # function used by default if not provided via options
    def default_file_name(exchange, data_type, date, symbol, format):
        return f"{exchange}_{data_type}_{date.strftime('%Y%m%d')}_{symbol}.{format}.gz"

    # customized get filename function - saves data in nested directory structure
    #def file_name_nested(exchange, data_type, date, symbol, format):
    #    return f"{exchange}/{data_type}/{date.strftime('%Y%m%d')}_{symbol}.{format}.gz"

    # returns data available at https://api.tardis.dev/v1/exchanges/binance-futures
    binance_usdt_details = get_exchange_details("binance-futures")
    # print(deribit_details)


    dt_start = datetime.strptime(s_start, "%Y-%m-%d")
    dt_end = datetime.strptime(s_end, "%Y-%m-%d")

    # create a list of dates for each day between dt_start and dt_end
    #ls_dates = pd.date_range(dt_start, dt_end - timedelta(days=1), freq='d')
    ls_dates = pd.date_range(dt_start, dt_end, freq='d')

    s_dates = []

    # convert the list of dates to a list of strings in the format YYYY-MM-DD
    for dt in ls_dates:
        s_dates.append(dt.strftime("%Y-%m-%d"))

    for i in tqdm(range(len(s_dates))):
        datasets.download(
            # one of https://api.tardis.dev/v1/exchanges with supportsDatasets:true - use 'id' value
            exchange="binance-futures",
            # accepted data types - 'datasets.symbols[].dataTypes' field in https://api.tardis.dev/v1/exchanges/deribit,
            # or get those values from 'deribit_details["datasets"]["symbols][]["dataTypes"] dict above

            # data_types=["incremental_book_L2", "trades", "quotes", "derivative_ticker", "book_snapshot_25", "book_snapshot_5", "liquidations"],
            # change date ranges as needed to fetch full month or year for example
            data_types = data_types,
            from_date=s_dates[i],
            # to date is non inclusive
            to_date=s_dates[i],
            # accepted values: 'datasets.symbols[].id' field in https://api.tardis.dev/v1/exchanges/deribit
            symbols=[SYMBOL],
            # (optional) your API key to get access to non sample data as well
            api_key=TARDIS_API_KEY,
            # (optional) path where data will be downloaded into, default dir is './datasets'
            # download_dir="./datasets",
            # (optional) - one can customize downloaded file name/path (flat dir strucure, or nested etc) - by default function 'default_file_name' is used
            get_filename=default_file_name,
            # (optional) file_name_nested will download data to nested directory structure (split by exchange and data type)
            #get_filename=file_name_nested,
        )


def main():
    download_tardis()


if __name__ == "__main__":
    main()
