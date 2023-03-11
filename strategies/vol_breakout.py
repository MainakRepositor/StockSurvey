import os, sys
import numpy as np
import pandas as pd
from tqdm import tqdm

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.yf_utils import df_to_weekly
from toolbox.ta_utils import add_avg_penetration, add_MACD, add_Impulse, \
                            add_moving_average, add_ATR

# TODO: add setup, for this concept to work the stock gotta have that explosive nature
# stocks with a recent uptrend (i.e. 66bars Uptrend) market_classification(period = 66, class_names_map = None) == 1
# currently in consolidation; market_classification(period = 22, class_names_map = None) = 0
# with low volatility; ATR at historic low (see https://stackoverflow.com/a/44825558/14285096)
# Nice to have:
# - the uptrend is young
# - historically higher than average efficiency_ratio
# - high short ratio

def get_percentile(x, A):
    ''' return a percentile of x in the sample space of A
    Args:
        x: input value to evaluate agains A
        A: our sample space to compute percentile against
    ref: https://stackoverflow.com/a/50863943/14285096
    '''
    A = np.sort(A)
    return np.interp(x, A, np.linspace(0,1, len(A)))

def detect_vol_breakout(df, period:int = 22, threshold:float = 1, ignore_gap = True,
        do_buy = True, add_entry_price = False, ignore_volume = False
    ):
    ''' add two new columns vol_breakout and entry_price to df
    '''
    # assert 'impulse' in df.columns
    threshold *= 1 if do_buy else -1
    ATR_col = 'ATR_' + str(int(period))
    df = add_ATR(df, period = period, use_ema = True,  col_name = ATR_col,
            channel_dict = None, return_TR = False
            ) if ATR_col not in df.columns else df

    close_diff = (df['Close'] - df['Open']) if ignore_gap else \
                (df['Close'] - df['Close'].shift())

    # this doesn't seem to work, check 336.hk on 11/9
    volume_confirms = df['Volume'] > df['Volume'].shift().rolling(int(period)).mean()
    vol_breakout = close_diff > (df[ATR_col].shift() * threshold) if do_buy else \
                    close_diff < (df[ATR_col].shift() * threshold)
    if not ignore_volume:
        vol_breakout = (vol_breakout & volume_confirms)
    df['vol_breakout'] = vol_breakout

    if add_entry_price:
        # df['entry_price'] = (df['Open'] + df['ATR'].shift() * threshold) * vol_breakout
        df['entry_price'] = df['Close'] * vol_breakout
    return df

def detect_low_vol_pullback(df, period, price_col = 'Low', col_name = 'LVPB'):
    ''' check if low within period is supported by decreasing volume
    Ref: https://www.investopedia.com/terms/l/low_volume_pullback.asp
    '''
    is_low = df[price_col].rolling(period).min() == df[price_col]
    vol_avg = df['Volume'].rolling(period).mean().shift()
    df[col_name] = is_low & (df['Volume'] < vol_avg)
    return df

def detect_volatility_contraction(df, atr_periods = [11,5],
        period: int = 100, threshold: float = 0.05, normalize= True, use_ema = True,
        col_name = 'VCP', debug = False):
    ''' return a column to indicate volatility contraction using ATR
    Args:
        atr_periods: check for ATRs being lower in cascading order (slowest to fastest)
        period: look-back period, number of bars
        threshold: current ATR must be less than this percentile within the look-back period
    '''
    assert 'ATR' in df.columns, 'detect_volatiliy_contraction: must add ATR first'
    assert len(atr_periods) >= 2, 'detect_volatility_contraction: must have at least two moving average periods'
    for p in atr_periods:
        df = add_ATR(df, period = p, col_name = f'ATR_{p}',
                use_ema = use_ema, channel_dict = None, normalize = normalize)
    df['ATR_percentile'] = df['ATR'].rolling(int(period)).apply(
                            lambda A: get_percentile(x = A[-1], A = A)
                            )
    df[col_name] = df['ATR_percentile'] < threshold

    for i in range(len(atr_periods))[1:]:
        ATR_slow = f'ATR_{atr_periods[i-1]}'
        ATR_fast = f'ATR_{atr_periods[i]}'
        df[col_name] = df[col_name] & (df[ATR_slow] > df[ATR_fast])

    if not debug:
        for p in atr_periods:
            del df[f'ATR_{p}']
        del df['ATR_percentile']
    return df

# def detect_volatility_contraction(df, ma_cascade = [100, 50, 25],
#         col_name = 'VCP', debug = False):
#     ''' return a column to indicate volatility contraction using ATR
#     Args:
#         ma_cascade: check for moving average being lower in cascading order
#     '''
#     assert 'ATR' in df.columns, 'add_volatility_contraction: must add ATR first'
#     assert len(ma_cascade) >= 2, 'add_volatility_contraction: must have at least two moving average periods'
#     # DO we need to normalize ATR?
#     l_ma_series = [df['ATR'].rolling(ma).mean().shift()
#                     for ma in ma_cascade]
#     df[col_name] = df['ATR'] < l_ma_series[-1]
#
#     for i in range(len(ma_cascade))[1:]:
#         df[col_name] = df[col_name] & (l_ma_series[i-1] > l_ma_series[i])
#
#     if debug:
#         for ma, ma_series in zip(ma_cascade, l_ma_series):
#             df[f'ATR_{ma}ma'] = ma_series
#     return df

### This is for the VCP dtection
###
def detect_VCP(df, ma_cascade = [100,50,25], lvpb_period = 22, ATR_period = 5,
        debug_mode = False, normalize_ATR = False, col_name = 'VCP_setup'):
    '''Minervini's Volatility Contraction Pattern detection
    returns True for when all [a] all the price MAs are in ascending order,
    and [b] all the ATR MAs are in descending order, and
    [c] there are Low Volume Pullbacks within the ATR Period.
    '''
    assert len(ma_cascade)>= 2, 'detect_VCP: must have at least 2 moving averages'
    assert ma_cascade == sorted(ma_cascade)[::-1], 'detect_VCP: ma_cascade must be descending'
    # [a] checking for trend
    for p in ma_cascade:
        df = add_moving_average(df, period = p)
    s_trending = True
    for i in range(len(ma_cascade))[1:]:
        s_trending = s_trending & (
            df[f'ema_{ma_cascade[i]}']> df[f'ema_{ma_cascade[i-1]}']
            )

    # [b] check for volatility contraction
    df = add_ATR(df, period = ATR_period, use_ema = True,
                channel_dict = None, normalize = normalize_ATR)
    df = detect_volatility_contraction(df, ma_cascade=ma_cascade, debug = debug_mode)

    # [c]
    df = detect_low_vol_pullback(df, period = lvpb_period)
    s_has_LVPB = df['LVPB'].rolling(ATR_period).max().shift()

    if debug_mode:
        df['VCP_trending_check'] = s_trending
        df['VCP_LVPB_check'] = s_has_LVPB

    df[col_name] = s_trending & df['VCP'] & s_has_LVPB
    return df

    # df_w = df_to_weekly(df, logic = {'Open'  : 'first',
    #             'High'  : 'max', 'Low'   : 'min', 'Close' : 'last',
    #             'Adj Close': 'last', 'Volume': 'sum', 'ATR': 'mean'}
    #             )

    # vol_contracts = df_daily['ATR'][-1]/df_daily['ATR'][-n_weeks_vol * 5]
    # atr_slope, _ = np.polyfit(x = range(vol_contract_period),
    #                 y = df_['ATR'][-vol_contract_period:].tolist(), deg =1)

    # if debug_mode:
    #     print(f'{return_period} bars return: {period_return}\n{vol_contract_period} bars ATR_{ATR_period} slope: {atr_slope}')
    # # return ((period_return> min_return) & (vol_contracts < vol_contracts_threshold))
    # return ((period_return> min_return) & (atr_slope < vol_contract_threshold))


def minervini_vcp(df, atr_period, atr_threshold = 1, ignore_gap = False, ignore_volume = False,
    vcp_params = {'ma_cascade' : [100,50,25],
        'lvpb_period' : 22, 'normalize_ATR' : False}
    ):
    df = detect_vol_breakout(df, period = atr_period, threshold = atr_threshold,
            do_buy = True, add_entry_price = True,
            ignore_gap=ignore_gap, ignore_volume = ignore_volume)

    if vcp_params:
        if 'ATR_period' not in vcp_params.keys():
            vcp_params['ATR_period'] = atr_period
        df = detect_VCP(df, **vcp_params)
        df['vol_breakout'] = df['vol_breakout'] & df['VCP_setup'].shift()
        df['entry_price'] = df['entry_price'] * df['vol_breakout']
    # pbar = tqdm(df.iterrows(), desc = 'checking for VCP')
    # for idate, row in pbar:
    #     if row['vol_breakout'] and vcp_params:
    #         print(idate)
    #         is_vcp = detect_VCP(df[:idate], ATR_period = atr_period, **vcp_params)
    #         if not is_vcp:
    #             df.loc[idate, "vol_breakout"] = 0
    #             df.loc[idate, 'entry_price'] = 0
    return df

def alpha_over_beta(df):
    ''' a volatility breakout entry with a low vol setup
    ref: https://www.alphaoverbeta.net/trading-the-volatility-breakout-system/
    '''

    # check ATR cross over
    for p in [5, 14]:
        ATR_col = 'ATR_' + str(int(p))
        df = add_ATR(df, period = p, use_ema = True,  col_name = ATR_col,
                channel_dict = None, return_TR = False)

    # add 3 EMA
    for p in [5,11,22]:
        df = add_moving_average(df, period = p, type = 'ema', price_col = 'Close')

    vol_breakout = (df["ema_5"] > df["ema_11"]) & (df["ema_11"]> df["ema_22"]) & \
            (df["ATR_5"] > df["ATR_14"]) & (df["ATR_5"].shift() < df["ATR_14"].shift())
    df['vol_breakout'] = vol_breakout
    df['entry_price'] = df['Close'] * vol_breakout
    return df
