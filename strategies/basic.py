import os,sys
import numpy as np
import pandas as pd

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.ta_utils import add_moving_average, add_MACD, add_ATR, \
                            add_KER, add_market_classification

def detect_period_peaks(df, period:int = 250, hilo:int = 1,
    price_col = 'Close', col_name = 'period_peak'):
    ''' check if price_col is either period High or Low
    Args:
        hilo: 1 for High, 0 for Low
    '''
    assert price_col in df.columns
    period_peak = df[price_col].rolling(period).max() if hilo == 1 else \
                    df[price_col].rolling(period).min()
    df[col_name] =  period_peak == df[price_col]
    return df

def detect_market_class(df, period:int = 66, col_name = 'market_classification',
    target_class: int = 1, use_macd = False):
    ''' check if market is trending-up, trending-down, or rangebound within the period
    Args:
        target_class: 1 for trending-up, -1 for trending-down, 0 for rangebound
        use_macd: use positive MACD to approximate trend; return 1 for positive MACD,
                    -1 for negative MACD and 0 otherwise
    '''
    assert target_class in [-1,0,1], f'target_class must be one of [-1,0,1]'
    if use_macd:
        df = df if 'MACD' in df.columns else add_MACD(df)
        df[col_name] = df['MACD'].apply(lambda x: 1 if x >0 else -1 if x <0 else 0)
    else:
        df = add_market_classification(df, period = period, class_map = None,
                col_name = col_name, debug_mode = True)
    df[col_name] = df[col_name] == target_class
    return df

def detect_value_zone(df, ma_period_fast: int = 11, ma_period_slow: int = 22,
    min_atr_wide : float = None,
    price_col = 'Close', col_name = 'value_zone'):
    ''' check if MA fast > MA Slow and if prices had history of penetrating into
        the value zone
    Args:
        min_atr_wide: requires that the value zone be at least wider than this
                    multiple of ATR
    '''
    df = add_moving_average(df, period = ma_period_fast, type = 'ema')
    df = add_moving_average(df, period = ma_period_slow, type = 'ema')
    df[col_name] = (df[price_col]> df[f'ema_{ma_period_slow}']) & \
                    (df[price_col]< df[f'ema_{ma_period_fast}'])
    if min_atr_wide:
        assert min_atr_wide > 0, 'min_atr_wide must be greater than 0'
        df = df if 'ATR' in df.columns else \
            add_ATR(df, period = ma_period_slow, channel_dict = None, normalize = False)
        df[col_name] = df[col_name] & (
            (df[f'ema_{ma_period_fast}'] - df[f'ema_{ma_period_slow}']) >= (df['ATR'] * min_atr_wide)
            )
    return df

def detect_positive_macd(df, requires_pos_hist = False, col_name = 'macd_pos'):
    ''' check if MACD is positive (good way to identify strong trend)
    Args:
        requires_pos_hist: requires MACD_histogram to also be positive
    '''
    df = df if 'MACD' in df.columns else add_MACD(df)
    df[col_name] = 0
    for i, row in df.iterrows():
        is_pos = row['MACD'] > 0
        is_pos = all([is_pos, row['MACD_histogram']>0]) \
                    if requires_pos_hist else is_pos
        df.at[i,col_name] = int(is_pos)
    return df

def detect_macd_crossover(df, updown: int = 1, is_pos_macd: bool = True,
    col_name = 'macd_crossover'):
    ''' check when MACD line cross over signal line
    Args:
        updown: 1 for up, 0 for down
        is_pos_macd: for upward cross, macd value also needs to be positive
    '''
    df = df if 'MACD' in df.columns else add_MACD(df)
    prev_MACD_Hist = df['MACD_histogram'].shift()
    cross_up = (df['MACD_histogram']>0) & (prev_MACD_Hist<0)
    cross_down = (df['MACD_histogram']<0) & (prev_MACD_Hist>0)
    if is_pos_macd:
        cross_up = cross_up & (df['MACD'] > 0)
    df[col_name] = cross_up if updown ==1 else cross_down
    return df

def detect_high_KER(df, period:int, threshold:int ,col_name = 'high_KER'):
    df = add_KER(df, period = period)
    df[col_name] = df['KER'] > threshold
    return df

def detect_gap(df, updown: int = 1, min_return: float = 0, col_name = 'gap'):
    ''' detecting GAPs which is defined by an Open that's outside of previous
        day's trading range
    Args:
        updown: 1 for up gaps, -1 for down gaps, 0 for all gaps (min_return must be 0)
        min_return: minimum %  outside previous day high/low in absolute term
    '''
    up_gap = (df['Open'] > df['High'].shift()) & \
            ((df['Open']/df['High'].shift()-1) > min_return)
    down_gap = (df['Open'] < df['Low'].shift()) & \
            ((df['Open']/df['Low'].shift()-1) < -min_return)
    df[col_name] = up_gap | down_gap
    if updown:
        df[col_name] = up_gap if updown == 1 else down_gap
    return df

def detect_in_range(df, period: int, range: float = 0.1, price_col = 'Close',
    col_name = 'in_range', debug_mode = True):
    ''' check if prices within the lookback window has been trading within range
    '''
    # range_high =  df[price_col].apply(lambda x: x * (1+ range/2))
    # range_low =  df[price_col].apply(lambda x: x * (1- range/2))
    # in_range = (df['High'].rolling(period).max() <= range_high
    #         ) & (df['Low'].rolling(period).min() >= range_low)
    # df[col_name] = in_range

    period_high = df['High'].rolling(period).max().shift()
    period_low = df['Low'].rolling(period).min().shift()
    # period_range = max(period_high / df[price_col] - 1, 0) + max(1- period_low/ df[price_col], 0)
    period_range = [
        max(h/c-1,0) + max(1-l/c,0)
        if h and c else None
        for h, l, c in zip(period_high, period_low, df[price_col])
    ]
    df[col_name] = [ r<= range for r in period_range]
    if debug_mode:
        df['period_range'] = period_range
    return df
