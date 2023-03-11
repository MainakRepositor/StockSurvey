import os, sys, random
import yfinance as yf
from yahooquery import Ticker
import pandas as pd
from tqdm import tqdm
from businessdate import BusinessDate

# TODO: for caching yfinance results
# this is an open issue for the Ticker method: https://github.com/ranaroussi/yfinance/issues/677
import requests_cache
SESH = requests_cache.CachedSession('yfinance.cache')
SESH.headers['User-agent'] = 'my-program/1.0'

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.scrape_utils import update_session_proxy

def valid_stock(stock_obj):
    '''
    Check if a stock_obj created by yf.Ticker has data
    '''
    try:
        # return 'symbol' in stock_obj.info.keys()

        # since version 0.2.6 some attributes in info were removed
        # see https://github.com/ranaroussi/yfinance/issues/1349
        # print(stock_obj.fast_info)
        return 'lastPrice' in stock_obj.fast_info.keys()
    except:
        return False

def tickers_parser(tickers, return_list = False, max_items = None):
    '''
    parse a string of space separated tickers with special handling for HK tickers
    Args:
        return_list: return a list object if true else a space separated string
        max_items: maximum number of items to return if given otherwise return all
    '''
    if tickers:
        l_tickers = tickers.split()
        l_tickers = [ ticker.split('.')[0].zfill(4) + '.HK' if '.HK' in ticker.upper() else ticker
            for ticker in l_tickers ]

        l_tickers = l_tickers[:max_items] if max_items else l_tickers
        l_tickers = [t.upper() for t in l_tickers]

        return l_tickers if return_list else " ".join(l_tickers)
    else:
        return None

def get_stocks_data(tickers, session = SESH,
        yf_download_params = {"period": '1y', "group_by": "column" , "interval": "1d"}
        ):
    '''
    Return data using yf.download method
    See this issue with rate limiter: https://github.com/ranaroussi/yfinance/issues/602
    Args:
        yf_download_params: passed straight to yf.download, see https://github.com/ranaroussi/yfinance
    '''
    if yf_download_params['interval'] == '1wk':
        print(f'converting daily prices to weekly with internal method df_to_weekly() for {tickers}')
        yf_download_params['interval'] == '1d'
        df_daily = yf.download(tickers = tickers, **yf_download_params)
        prices_df = df_to_weekly(df_daily = df_daily) if len(df_daily)>0 else df_daily
    else:
        prices_df = yf.download(tickers = tickers, **yf_download_params)

    prices_df.index = prices_df.index.tz_localize(None)
    returns_df = prices_df['Adj Close'].pct_change()[1:]
    if len(tickers.split())> 1:
        col_with_returns = [col for col in returns_df.columns
                            if returns_df[col].isna().sum() < len(returns_df)
                            ]
        returns_df = returns_df[col_with_returns].dropna()
    else:
        returns_df = pd.DataFrame({tickers :returns_df}, index = returns_df.index)

    return {
        'prices': prices_df,
        'returns': returns_df
    }

def get_stocks_ohlc(tickers, session = SESH, interval = '1d',
    start_date = None, end_date = None, proxies = None):
    ''' Get Max OHLC (includes most current bar) for the given stocks
    '''
    interval_rule_dict = {'1wk': 'W', '1mo':'M'}
    assert interval in ['1d'] + list(interval_rule_dict.keys()), f'get_stocks_ohlc: interval must be either 1d or one of {interval_rule_dict.keys()}'
    session = update_session_proxy(session, proxy = random.choice(proxies)) \
            if proxies else session
    prices_df = yf.download(tickers = tickers, #session = session,
                    period = 'max', interval = '1d', group_by = 'ticker',
                    progress = False
                    )
    # Date Adjustment
    if prices_df.index.inferred_type == "datetime64":
        prices_df.index = prices_df.index.tz_localize(None)
    start_date = (BusinessDate(start_date) - '1d').to_date() if start_date else None
    end_date = (BusinessDate(end_date) + '1d').to_date() if end_date else None
    prices_df = prices_df[prices_df.index > pd.Timestamp(start_date)] \
                if start_date else prices_df
    prices_df = prices_df[prices_df.index < pd.Timestamp(end_date)] \
                if end_date else prices_df
    # Interval Adjustment
    if interval in interval_rule_dict.keys():
        try:
            prices_df = df_aggregate(prices_df, rule =interval_rule_dict[interval])
        except:
            raise RuntimeError(f'get_stocks_ohlc: daily to weekly conversion error for {tickers}')
    return prices_df

def get_dfs_by_tickers(df):
    '''
    return a dictionary of {ticker:df,...}
    '''
    assert isinstance(df.columns, pd.MultiIndex), "this function only works with DF with MultiIndex Columns"
    data_col = set([c[0] for c in df.columns])
    tickers = set([c[1] for c in df.columns])

    l_DFs = [df[[(c,t) for c in data_col]] for t in tickers]
    for df in l_DFs:
        df.columns = df.columns.droplevel(1)
    return {t:df for t, df in zip(tickers, l_DFs)}

def get_stocks_obj(tickers, session = SESH, tqdm_func = tqdm):
    tickers_obj = yf.Tickers(tickers)
    return tickers_obj.tickers
    # return [yf.Ticker(t)
    #     for t in tqdm_func(tickers.split(), desc = "Creating Ticker Object")
    #     ]

def get_stock_info(ticker, l_modules = ['assetProfile', 'price', 'summaryDetail', 'summaryProfile', 'defaultKeyStatistics']):
    ''' get stock info using yahooquery
    '''
    assert valid_stock(yf.Ticker(ticker)), f'{ticker} does not seem to be a valid stock ticker'
    data = Ticker(ticker).get_modules(" ".join(l_modules)) if l_modules else Ticker(ticker).all_modules
    return data[ticker]

def get_stock_financials(ticker, type, b_transpose = True):
    ''' get stock financials using [yahooquery](https://yahooquery.dpguthrie.com/guide/ticker/financials/)
    '''
    assert valid_stock(yf.Ticker(ticker)), f'{ticker} does not seem to be a valid stock ticker'
    yq_ticker = Ticker(ticker)
    financials_func_dict = {'balance_sheet': yq_ticker.balance_sheet,
        'income_statement': yq_ticker.income_statement ,
        'cashflow': yq_ticker.cash_flow
        }
    assert type in list(financials_func_dict.keys()) + ['earnings'], f'unknown type: {type}'
    if type == 'earnings':
        return yq_ticker.earnings[ticker]
    else:
        df = financials_func_dict[type]()
        df['asOfDate'] = df['asOfDate'].dt.strftime('%Y-%m-%d')
        df = df.set_index('asOfDate').T if b_transpose else df
        return df

def get_stocks_info(tickers, tqdm_func = tqdm):
    '''
    returns a list of dictionary for each ticker
    '''
    tickers_obj = get_stocks_obj(tickers)
    # print(tickers_obj)
    # tickers_obj : dict {'ticker': yfinance.Ticker object,...}

    # TODO: add try-except & retry
    results = [ {k: v for k, v in t.info.items()}
        for t in tqdm_func(tickers_obj.values(), desc = "Getting stocks info")
    ]
    return results

def df_aggregate(df_daily, rule = 'W', date_col = None,
        logic = {'Open'  : 'first',
         'High'  : 'max',
         'Low'   : 'min',
         'Close' : 'last', 'Adj Close': 'last',
         'Volume': 'sum'}
    ):
    '''
    take a daily DF and aggregating it for longer time frame
    see: https://stackoverflow.com/a/34598511/14285096
    or https://towardsdatascience.com/using-the-pandas-resample-function-a231144194c4
    '''
    assert rule in ['M','W'], f'df_aggregate: only weekly, W, and monthly, M offset available for now'
    if len(df_daily) >0:
        from pandas.tseries.frequencies import to_offset
        df = df_daily.copy()
        if date_col:
            df.set_index(date_col, inplace = True)
        df = df.resample(rule).apply(logic)
        df.index -= to_offset('6D') if rule == 'W' else \
                    pd.offsets.MonthBegin(1)
        return df
    else:
        return df_daily

def df_to_weekly(df_daily, date_col = None,
        logic = {'Open'  : 'first',
         'High'  : 'max',
         'Low'   : 'min',
         'Close' : 'last', 'Adj Close': 'last',
         'Volume': 'sum'}
    ):
    '''
    take a daily DF and convert it to weekly DF
    see: https://stackoverflow.com/a/34598511/14285096
    '''
    if len(df_daily) >0:
        from pandas.tseries.frequencies import to_offset
        df = df_daily.copy()
        if date_col:
            df.set_index(date_col, inplace = True)
        # df = df.resample('W',
        #         loffset = pd.offsets.timedelta(days = -6) # put the labels to Monday
        #         ).apply(logic)
        df = df.resample('W').apply(logic)
        df.index -= to_offset('6D')
        return df
    else:
        return df_daily
