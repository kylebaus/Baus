How to setup python backtesting environment for Baus strategies

1. install anaconda if it is not already installed

2. download baus.yml

3. create basu environment by running the following

   conda env create -f baus.yml

4. start baus environment by running the following

   conda activate baus

NOTE: if step 3 failed, skip step 3 and step 4, and run the following instead:
   pip install numpy
   pip install numba
   pip install matplotlib
   pip install pandas
   pip install tardis_dev
   
5. run a simple test

   python hello.py

6. run real backtest

   mkdir -p  baus_backtesting/vb_v8_results
   cd baus_backtesting/vb_v8_results 
   python ../src/vb_v8_short_term.py



Manifest:
==============

src/download_tardis_csv_btcusdt.py   -  script to download tardis data files

src/tardis_trades_to_vb.py           -  scirpt to generate volume bar files from tardis trade files    

src/tardis_trades_to_mbar.py         -  scirpt to generate minute bar files from tardis trade files

src/vb_v8_short_term_reverse_logic_basic.py  - VB (v8) Short Term Prediction Using 3880 Bars, implementation of 
                                               the following with focus on the reverse logic basic test
src/vb_v8_short_term.py              -  VB (v7) Vol Imb test 5

src/vb_v7.py                         -  VB (v8) Short Term Prediction Using 3880 Bars

src/vb_tp6_aggregate-test5-follow-trend.py  - VB TP6_Aggregate reserach (Test #5) follow trend

src/vb_tp6_aggregate-test5.py               - VB TP6_Aggregate reserach (Test #5) 

src/vb_tp6_aggregate.py                     - VB TP6_Aggregate reserach 

src/vb_v6_alt_test.py                -  VB (v6) TP6_Aggregate strategy altnative test

src/vb_v6.py                         -  VB (v6) TP6_Aggregate strategy

src/vb_expectancy.py                 - expectancy research

src/vb_v5_tp_sl_with_atr.py          - based on vb_v5, added atr column in the reports

src/vb_v5.py                         - BV (v5) implemented the orignal v5 logic





