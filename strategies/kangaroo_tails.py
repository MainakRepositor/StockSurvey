import os, sys
import numpy as np
import pandas as pd

def detect_kangaroo_tails(df, col_name = 'kangaroo_tails',
        atr_threshold: int = 2, period: int = 13, hilo_col_name_tup = ('High','Low'),
        tail_type:int = 0, debug = False
    ):
    ''' add a new column to the df when 1 indicates a kangaroo tail
    on the previous bar
    see: https://www.bwts.com.au/download/lc-charting-and-technical-analysis/41-kangaroo-tail-pattern.pdf
    Args:
        tail_type: 1 for upward pointing tails, -1 for downward pointing, 0 for both
    '''
    assert 'ATR' in df.columns, f"ATR calculation is required before this function is ran"
    hi_col, low_col = hilo_col_name_tup
    df['is_new_low'] = (df[low_col] < df[low_col].rolling(period).min().shift())
    df['is_new_hi'] = (df[hi_col] > df[hi_col].rolling(period).max().shift())
    df['pct_of_ATR'] = (df['TR'] / df['ATR'].shift())
    hilo = df[hi_col] - df[low_col] # can use TR because it includes change from prev close
    pre_req_condition = (
        (df['pct_of_ATR'].shift() > atr_threshold) & # previous bar has to be tall
        ((hilo <= df['ATR']) & (hilo.shift(2) <= df['ATR'])) &  # adjusant bodies are normal
        (~df['is_new_hi'] & ~df['is_new_low']) # today is a normal day
        )
    downtail_condition = (
        (df['Low']> df['Low'].shift()) &
        ((df['High'].shift(2) > df['High'].shift()) &
            (df['Low'].shift(2) <= df['High'].shift())
            ) & # previous high is in t-2 range
        ((df['High'] > df['High'].shift()) &
            (df['Low'] <= df['High'].shift())
            ) # previous high is in today's range
        )
    uptail_condition = (
        (df['High'].shift() > df['High']) &
        ((df['High'].shift(2) >= df['Low'].shift()) &
            (df['Low'].shift(2) < df['Low'].shift())
            ) & # previous high is in t-2 range
        ((df['High'] >= df['Low'].shift()) &
            (df['Low'] < df['Low'].shift())
            ) # previous high is in today's range
        )
    # for i, row in df.reset_index().iterrows():
    #     if i > 0:
    #         if is_new_hi[i-1] or is_new_low[i-1]:
    #             if pct_of_ATR[i-1]> atr_threshold and \
    #             pct_of_ATR[i]< atr_threshold and pct_of_ATR[i-2]< atr_threshold:
    #                 if not is_new_hi[i] and not is_new_low[i]:
    #                     df[col_name] = 1
    if not debug:
        del df['is_new_hi'], df['is_new_low'], df['pct_of_ATR']

    tail_con = (pre_req_condition & downtail_condition) if tail_type == -1 else \
                (pre_req_condition & uptail_condition)
    tail_con = (pre_req_condition & downtail_condition & uptail_condition) \
                if tail_type == 0 else tail_con
    df[col_name] = tail_con
    return df
