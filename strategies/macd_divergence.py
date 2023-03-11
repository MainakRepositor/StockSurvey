import os, sys
import numpy as np
import pandas as pd

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.yf_utils import df_to_weekly
from toolbox.ta_utils import add_avg_penetration, add_MACD, add_Impulse, \
                            add_moving_average

def cluster_near_by_sign(data, n= 1):
    ''' cluster neigboring points by sign
    ref: https://stackoverflow.com/a/33812257/14285096
    '''
    from itertools import groupby
    all_clusters = [list(v) for k, v in groupby(data, lambda x: x<0)]
    return all_clusters[-n:] if n else all_clusters

def detect_macd_divergence(df, period:int = 66, threshold:float = 1, debug = False):
    ''' Detect MACD Divergence
    Args:
        period = number of bars (should be around 3M)
        threshold = current price less than previous low * threshold
    '''
    macd_h = 'MACD_histogram'
    assert macd_h in df.columns, f"Please run add_MACD() first"
    do_impulse = 'impulse' in df.columns
    # Computation of recent period is the problem here
    # recent_period = int(period/3) # power of 5? maybe 1/3 better?

    # Bullish Divergence
    current_clusters_size = df[macd_h].rolling(period).apply(
                            lambda x: len(cluster_near_by_sign(x, n =1)[0])
                            ).shift()
    lows_ll = df['Low'].tolist()
    period_lows = [lows_ll[i-period: i] if i>= period else []
                        for i, v in enumerate(lows_ll)
                        ]
    recent_low = [ min(lows[-size:]) if size and len(lows)>0 else np.nan
        for lows, size in zip( period_lows,
            current_clusters_size.fillna(0).astype('int').tolist()
            )
        ]

    # is_new_low = ((df['Low'].rolling(period).min().shift()/df['Low']) >= threshold)
    # is_new_low = ((df['Low'].rolling(period).min().shift()/recent_low) >= threshold)

    # using recent_low is better than just lowing at Low in that it capture false downside breakouts
    is_new_low = ((df['Low'].rolling(period).min().shift()/recent_low) >= threshold)
    is_macd_low = (df[macd_h] < df[macd_h].rolling(period).min().shift())
    # recent_macd_low = df[macd_h].rolling(recent_period).min().shift()
    recent_macd_low = df[macd_h].rolling(period).apply(
                        lambda x: min(cluster_near_by_sign(x, n =1)[0])
                        ).shift()
    recent_macd_low_is_low = (recent_macd_low <= df[macd_h].rolling(period).min().shift())
    recent_macd_low_over_threshold = (
        recent_macd_low/ df[macd_h].rolling(period).min().shift() >= threshold
    )

    # number_of_macdH_clusters removed the need for this
    # recent_macd_high = df[macd_h].rolling(recent_period).max().shift()
    number_of_macdH_clusters = df[macd_h].rolling(period).apply(
                                lambda x: len(cluster_near_by_sign(x, n = None))
                                ).shift()
    impulse_check = (df['impulse'] != -1) if do_impulse else True

    df['MACD_Divergence'] = (is_new_low & ~is_macd_low &
                            (df[macd_h]< 0) &
                            ~recent_macd_low_is_low &
                            ~recent_macd_low_over_threshold &
                            # (recent_macd_high >= 0) &
                            (number_of_macdH_clusters >= 2 ) &
                            impulse_check
                            )
    if debug:
        df[f'{period}_bars_low'] = df['Low'].rolling(period).min().shift()
        df['recent_cluster_size'] = current_clusters_size
        df['recent_low'] = recent_low
        df['is_new_low'] = is_new_low
        df['MACDh_period_low'] = df[macd_h].rolling(period).min().shift()
        df['MACDh_recent_low'] = recent_macd_low
        df['MACDh_recent_low_over_thresh'] = recent_macd_low_over_threshold
        df['MACDh_is_new_low'] = is_macd_low
        df['MACDh_culsters_count'] = number_of_macdH_clusters
        df['MACDh_impulse_check'] =impulse_check
    return df

def add_strategy_buy(df, safezone_coef = 1, strategy_thresh = 0.95, strategy_period = 66,
         verbose = False, add_impulse = True, triple_screen = False, double_prefection = False
        ):
    ''' Elder's MACD Bullish Divergence on the Triple Screen System,
        returns a df with the "MACD_Divergence" column indicating the entry and
        "buy_safezone"  as the fair value column
    Args:
        df: daily prices
        triple_screen: ensure impulse on weekly and daily agrees
        double_prefection: Bullish Divergence on both Weekly and Daily chart
        strategy_thresh: how low must recent low be compared to period's low
        strategy_period: totally time-frame of the divergence (daily chart: ~3m, weekly chart: ~9m)
        safezone_coef: only enter when price dip below this level of ATR relative to EMA
        add_impluse: should ALWAYS be true
    '''
    # TODO: check that the required TA columns are in df
    for c in ['ema_11', 'ema_22', 'MACD_histogram']:
        assert c in df.columns, f'Technical Indicator column {c} missing. Please add it first.'
    # TODO: check that df has daily prices
    if double_prefection:
        assert triple_screen, f"double_prefection requires triple_screen to be on as well"

    df = add_avg_penetration(df.copy(), fair_col= 'ema_11', num_of_bars= 30, ignore_zero= True, coef= safezone_coef)
    df = add_Impulse(df, ema_name = 'ema_22') if add_impulse else df
    df = detect_macd_divergence(df, period = strategy_period, threshold = strategy_thresh )

    pbar = tqdm(df.iterrows(), desc = "checking weekly chart for confirmation") if verbose else df.iterrows()
    for idate, row in pbar:
        if row['MACD_Divergence'] and triple_screen:
            # Check the Weekly Chart
            df_w = df_to_weekly(df[['Open','High','Low','Close', 'Adj Close','Volume']][:idate])
            df_w = add_moving_average(df_w, period = 26, type = 'ema')
            df_w = add_MACD(df_w)
            df_w = add_Impulse(df_w, ema_name = 'ema_26') if add_impulse else df_w

            weekly_impulse_check = df_w['impulse'][-1] >= 0
            df.loc[idate, 'MACD_Divergence'] = row['MACD_Divergence'] == weekly_impulse_check

            if double_prefection:
                # for MACD Divergence on the Intermediate Chart a 9m strategy Period looks the best
                df_w = detect_macd_divergence(df_w,
                            period = int(strategy_period*3/5), threshold= strategy_thresh
                            )
                df.loc[idate, 'MACD_Divergence'] = df_w['MACD_Divergence'][-1] == row['MACD_Divergence']

    if verbose:
        print(f'number of BD days: {len(df[df["MACD_Divergence"]])}')
        print(f'number of BD days below {safezone_coef}x average penetration: {len(df[df["MACD_Divergence"] & (df["Low"]<df["buy_safezone"])])}')
    return df
