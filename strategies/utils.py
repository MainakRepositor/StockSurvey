import os, sys, datetime
import numpy as np
import pandas as pd
import plotly.express as px
from businessdate import BusinessDate

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.data_utils import timed_lru_cache
from toolbox.yf_utils import tickers_parser, get_stocks_ohlc
from toolbox.ta_utils import market_classification, add_moving_average, add_ATR, \
                            add_MACD
from toolbox.scrape_utils import get_proxies
from strategies.macd_divergence import cluster_near_by_sign

@timed_lru_cache(seconds = 12*60**2) # Cache Stock Data for 12 hours
def get_ticker_data_with_technicals(
        ticker:str, interval:str = '1d', trade_date = datetime.date.today(),
        tenor:str = '2y', data_buffer_tenor:str = '1y',
        l_ma_periods:list = [22,11],
        atr_params = {'period': 13, 'use_ema': True, 'channel_dict' : None},
        return_all_dates = False
        ):
    ''' Get Price Data for a Ticker and add various Technical Indicators intended for
    trend following strategies backtesting/ screening
    Args:
        l_ma_periods: list of moving averages periods to add
        return_all_dates: if False, return only data from start_date
    '''
    start_date = (BusinessDate(trade_date)- tenor).to_date()
    data_start_date = (BusinessDate(start_date) - data_buffer_tenor).to_date()
    df = get_stocks_ohlc(tickers = tickers_parser(ticker),
            interval = interval,
            start_date = data_start_date,
            end_date = trade_date,
            proxies = get_proxies()
            )

    for p in l_ma_periods:
        df = add_moving_average(df, period = p, type = 'ema')
    df = add_MACD(df)
    df = add_ATR(df, **atr_params) if atr_params else df
    return df if return_all_dates else df[df.index > pd.Timestamp(start_date)]

def add_stops_trailing(df, trade_date, entry_price, init_stop, trailing_atr,
    breakeven_r = None, profit_retracement = None, date_col = None, debug_mode = False):
    ''' add trailing stop
    '''
    assert entry_price > init_stop, f'add_stop_trailing: entry_price cannot be below init_stop'
    assert 'ATR' in df.columns, f'add_stop_trailing: please add ATR to price DF first'
    l_stops, l_pos, l_max_r = [], [], []
    pos, stop, max_reward = None, None, 0
    for i, row in df.iterrows():
        idate = row[date_col].date() if date_col else i.date()
        if idate == trade_date:
            assert entry_price > row['Low'] and entry_price < row['High'], f'add_stop_trailing: entry price {entry_price} is outside of trade_date range ({row["Low"]},{row["High"]})'
            stop = l_stops[-1] = init_stop
            risk = entry_price - init_stop
            pos = True # assume on the first date stop will never be hit
        elif idate > trade_date and pos:
            max_reward = max(max_reward, row['Close'] - entry_price) # should we use 'High'?
            atr_stop = row['Close'] - row['ATR'] * trailing_atr # should we use 'High'?
            if row['Low']<= stop:   # Trade is Stopped Out
                stop = pos  = None
                max_reward = 0
            else:                   # Manage Stop & let winner run
                if breakeven_r:
                    if max_reward/risk > breakeven_r:
                        stop = max(atr_stop, stop, entry_price)
                else:
                    stop = max(stop, atr_stop)

        l_stops.append(stop)
        l_pos.append(pos)
        l_max_r.append(max_reward)

    df['stops'] = l_stops
    df['stops'] = df['stops'].shift() #stops are update end of day, so we shift it for displaying
    if debug_mode:
        df['pos'] = l_pos
        df['max_r'] = l_max_r
    return df

def backtest(df, signal_col, fair_value_col, ticker = None,
             stop_atr_ratio = 1, rr_ratio = 3, breakeven_stop_r = None,
             trailing_stop_atr = None, profit_retracement = None,
             return_open_trade = False
            ):
    ''' very simple strategy of buying below fair value when signal column equals 1
    exits when low < entry * stop_atr_ratio OR high > entry + ((entry - stop) * rr_ratio)
    Args:
        rr_ratio: Risk to Reward target
        breakeven_stop_r: move stop to breakeven when Reward is above this threshold
        trailing_stop_atr: trailing stop as % of r that only moves into the trades favour
        profit_retracement: % of profit to set trailing stop to after profit target is reached
    '''
    assert 'ATR' in df.columns, f'need to run add_ATR() on df first'
    # if trailing_stop_r:
    #     assert trailing_stop_r < rr_ratio, f'trailing_stop_r must be less than rr_ratio'
    if profit_retracement:
        assert profit_retracement < 1 and profit_retracement>0, f'profit retracement must be between 0 and 1'
    if breakeven_stop_r:
        assert breakeven_stop_r > 0

    l_trades = []
    pos = None

    for i, row in df.iterrows():
        if pos:
            if row['High'] <= pos['stop'] or row['Open'] <= pos['stop']: # Stop Loss on a Gap Down
                pos['reward'] = row['Open'] - pos['entry']
            elif row['Low'] <= pos['stop']: # Stop Loss
                pos['reward'] = pos['stop'] - pos['entry']
            elif row['High'] >= pos['exit']: # Take Profit
                if profit_retracement: # switch to retracement exit
                    pos['exit'] += 3 * row['ATR']
                    continue
                pos['reward'] = pos['exit'] - pos['entry']
            else: # Hold on to position
                pos['reward'] = row['High']- pos['entry']
                pos['MAE'] = min([row['Low'] - pos['entry'], pos['MAE']])

                # TODO: add check for Exit Column; then break
                # manage stops
                if breakeven_stop_r:
                    pos['stop'] = pos['entry'] \
                        if pos['reward']/pos['risk'] > breakeven_stop_r else pos['stop']

                if profit_retracement: # Profit Retracment Exit
                    pos['stop'] = max([
                            row['High'] - pos['reward'] * profit_retracement,
                            pos['stop']
                        ]) if pos['reward']/pos['risk'] > rr_ratio else pos['stop']

                if trailing_stop_atr:
                    if breakeven_stop_r:
                        if pos['reward']/pos['risk'] < breakeven_stop_r:
                            continue
                    pos['stop'] = max([
                            pos['stop'], row['High'] - trailing_stop_atr * row['ATR']
                        ])
                # log the changes in stops
                if pos['stops'][-1] != pos['stop']:
                    pos['stops'].append(pos['stop'])
                continue # Hold

            days_delta = i - pos['date']
            pos['num_days'] = days_delta.days
            pos['r_multiplier'] = pos['reward']/pos['risk']
            pos['MAE'] /= pos['risk']
            pos['end_date'] = i
            pos['market_classification_3m'] = market_classification(df[:i],66)
            l_trades += [pos]
            pos = None
        elif row[signal_col] and row['Low']< row[fair_value_col]:
            # Open Trade
            pos = {
                'entry': row[fair_value_col],
                'stop': row[fair_value_col] - row['ATR'] * stop_atr_ratio,
                'risk': row['ATR'] * stop_atr_ratio,
                'reward': 0, 'MAE': 0
            }
            pos['exit'] = pos['entry'] + rr_ratio * (pos['entry'] - pos['stop'])
            pos = {k:round(v,2) for k,v in pos.items()}
            pos['stops'] = [pos['stop']]
            pos['date'] = i
            if ticker:
                pos['ticker'] = ticker

    # currently opened position
    if pos and return_open_trade:
        l_trades += [pos]
    return l_trades

def analysis_bt(l_trades, n_trading_days = None,
        verbose = False, trading_day_per_year = 250
        ):
    ''' a really simple summery of a list of trades returning a JSON object
    '''
    wins = [t for t in l_trades if t['reward']> 0]
    expectancy = np.mean([t['r_multiplier'] for t in l_trades])
    holding_period = np.mean([t['num_days'] for t in l_trades])

    df = pd.DataFrame.from_dict(l_trades).sort_values(by=["date"])
    df['profitable'] = df['reward'] > 0
    l_loss_strikes = [ sum(rs)
            for rs in cluster_near_by_sign(df['r_multiplier'], n = None)
            if rs[0]<0
        ]

    results = {
        'trade_count': len(l_trades),
        'win_rate': len(wins)/ len(l_trades),
        'expectancy': expectancy,
        'avg_holding_period': holding_period,
        'avg_MAE_win': np.mean([t['MAE'] for t in l_trades if t['reward']> 0]) ,
        'avg_MAE_lost': np.mean([t['MAE'] for t in l_trades if t['reward']<= 0]),
        'max_drawdown': min(l_loss_strikes)
    }

    if verbose:
        print(results)

    if n_trading_days:
        results['trades_per_day'] = results['trade_count']/ n_trading_days
        results['expectunity'] = results['expectancy'] * results['trades_per_day'] * trading_day_per_year
    results['df'] = df
    return results
