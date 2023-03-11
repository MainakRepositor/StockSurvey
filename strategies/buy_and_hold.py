import os, sys, datetime
import numpy as np
import pandas as pd

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.ta_utils import add_moving_average, add_MACD, \
                            add_ATR, add_market_classification
from toolbox.yf_utils import df_to_weekly
from strategies.basic import detect_macd_crossover

def get_last_monday(date_obj, b_pd_datetime = False):
    last_monday = date_obj - datetime.timedelta(days = date_obj.weekday(), weeks =1)
    return pd.to_datetime(last_monday) if b_pd_datetime else last_monday

def daily_buy_and_hold(df_daily, atr_stop = 3, req_pos_macd = False,
        b_trading_window_only: bool = False):
    ''' financial wisdom's dual MACD approach
    '''
    df_w = df_to_weekly(df_daily)
    df_w = detect_macd_crossover(df_w, updown= 1, is_pos_macd= req_pos_macd)
    df_daily = df_daily if "MACD" in df_daily.columns else add_MACD(df_daily)
    df_daily = df_daily if 'ema_22' in df_daily.columns else \
                add_moving_average(df_daily,22)
    df_daily = df_daily if 'ATR' in df_daily.columns else \
                add_ATR(df_daily, channel_dict = None, normalize = False)
    df_daily['trading_window'] = df_daily['position']= df_daily['stop'] = 0

    # TODO: first add trading window from weekly MACD to daily df
    for i, row in df_daily.iterrows():
        last_monday = get_last_monday(i, b_pd_datetime= True)
        last_week = df_w.loc[last_monday] if last_monday in df_w.index else None
        if isinstance(last_week, pd.Series):
            trade_on = last_week['MACD_histogram']>0
            if req_pos_macd:
                trade_on = trade_on and last_week['MACD']>0
            df_daily.at[i, 'trading_window'] = 1 if trade_on else 0
    if b_trading_window_only:
        return df_daily

    # TODO: then entry and stop management
    for i, row in df_daily.iterrows():
        lastTD_loc = df_daily.index.get_loc(i)-1
        lastTD = df_daily.iloc[lastTD_loc] if lastTD_loc >=1 else None
        if not isinstance(lastTD, pd.Series):
            continue
        if lastTD['position'] >0:
            # manage position
            if row['Low']< lastTD['stop']:
                #   STOP-LOSS
                print(f'STOP out on {i}, (stop: {lastTD["stop"]})')
                df_daily.at[i, 'position'] = 0
            elif row['trading_window']==0 or row['MACD_histogram']<0:
                #   EXIT
                print(f'exit on {i}, (Close: {row["Close"]})')
                df_daily.at[i, 'position']=0
            else:#  manage STOP
                df_daily.at[i, 'position'] = 1
                df_daily.at[i, 'stop'] = max(
                    lastTD["stop"],
                    row['Close'] - atr_stop * row['ATR']
                )
        elif row['trading_window']==1:
            # look for Entry
            buy_signal = 1 if row['MACD_histogram']>0 else 0
            if req_pos_macd:
                buy_signal = buy_signal if row['MACD']>0 else 0
            if buy_signal:
                print(f'buy on {i} (Close: {row["Close"]}, ATR: {row["ATR"]})')
                df_daily.at[i, 'position'] = 1
                df_daily.at[i, 'stop'] = row['Close'] - atr_stop * row['ATR']
    return df_daily

def value_surfing(df, stop_ATR: float, exit_ATR: float,
    ma_period_fast:int = 11, ma_period_slow:int = 22, min_atr_wide:float = 0,
    trading_signal_col:str = None):
    '''buy in the value zone and sell X ATR above fast EMA
    Args:
        stop_ATR: trailing stop ATR, set at entry; 0 means use slow MA as stop
        exit_ATR: how many ATR above fast EMA to exit
        trading_signal_col: if given, only enter if this column is True
    '''
    if trading_signal_col:
        assert trading_signal_col in df.columns, f'column {trading_signal_col} does not exist in given dataframe'
    assert min_atr_wide >=0, f'min_atr_wide cannot be less than 0'

    df = add_moving_average(df, period = ma_period_fast, type = 'ema')
    df = add_moving_average(df, period = ma_period_slow, type = 'ema')
    df = df if 'ATR' in df.columns else \
        add_ATR(df, period = ma_period_slow, channel_dict = None, normalize = False)
    df['setup'] = (
        df[f'ema_{ma_period_fast}']> df[f'ema_{ma_period_slow}']
        ) & (
        (df[f'ema_{ma_period_fast}']- df[f'ema_{ma_period_slow}']) > (df['ATR']* min_atr_wide)
        )
    df['position']= df['stop'] = 0

    for i, row in df.iterrows():
        lastTD_loc = df.index.get_loc(i)-1
        lastTD = df.iloc[lastTD_loc] if lastTD_loc >=1 else None
        if not isinstance(lastTD, pd.Series):
            continue
        if lastTD['position'] >0:
            # manage position
            if row['Low']< lastTD['stop']:
                #   STOP-LOSS
                print(f'STOP out on {i}, (stop: {lastTD["stop"]})')
                df.at[i, 'position'] = 0
            elif row['High']>= exit_ATR * row['ATR'] + row[f'ema_{ma_period_fast}']:
                #   EXIT
                print(f'exit on {i}, (Target: {row[f"ema_{ma_period_fast}"]})')
                df.at[i, 'position']=0
            elif trading_signal_col:
                #   EXIT
                if not row[trading_signal_col]:
                    print(f'exit on {i}, (Close: {row["Close"]})')
                    df.at[i, 'position']=0
            else:#  manage STOP
                new_stop = row['Close'] - stop_ATR * row['ATR'] if stop_ATR else \
                            row[f'ema_{ma_period_slow}']
                df.at[i, 'position'] = 1
                df.at[i, 'stop'] = max(lastTD["stop"], new_stop)
        elif row['setup']:
            entry = 1 if row['Low'] < row[f'ema_{ma_period_fast}'] and \
                        row['Low'] > row[f'ema_{ma_period_slow}'] else 0
            if trading_signal_col:
                entry = entry if row[trading_signal_col] else 0
            if entry:
                print(f'buy on {i} (Entry: {row[f"ema_{ma_period_fast}"]}, ATR: {row["ATR"]})')
                df.at[i, 'position'] = 1
                df.at[i, 'stop'] = row[f"ema_{ma_period_fast}"] - stop_ATR * row['ATR'] if stop_ATR else \
                                    row[f"ema_{ma_period_slow}"]
    return df
