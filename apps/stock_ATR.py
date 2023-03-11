import os, sys, json, datetime
import streamlit as st
import pandas as pd
import plotly.express as px
from businessdate import BusinessDate

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.st_utils import show_plotly
from toolbox.yf_utils import tickers_parser, get_dfs_by_tickers
from toolbox.plotly_utils import plotly_ohlc_chart
from toolbox.ta_utils import add_ATR, add_KER
from toolbox.hkex_utils import get_lot_size
from apps.stock_returns import get_yf_data

def get_ATR_calc(df, period, use_ema, atr_multiplier = 2, var = 1000, price_col = 'Adj Close'):
    '''
    return a dictionary of various ATR calcuations
    Args:
        df: dataframe of prices from yfinance for a Single Stock
        var: Value At Risk
    '''
    data = add_ATR(df,  period = period, use_ema = use_ema, channel_dict = None)
    ATR = data['ATR'][-1]
    price = data[price_col][-1]
    shares = int(var / (atr_multiplier * ATR)) # Basically always rounding down)
    return {'ATR': ATR,
        price_col : price,
        'ATR%Price': ATR/ price,
        'num_shares': shares,
        'position_size': shares * price
        }

def get_charts_configs(st_asset):
    with st_asset:
        n_bins = int(st.number_input('number of bins (histogram)', value = 100))
        barmode = st.selectbox('barmode (histogram)', options = ['overlay','stack','relative','group'])
    return {
        'n_bins': n_bins, 'barmode': barmode
    }

def visualize_features(df_dict, chart_configs, atr_period, start_date, use_ema = True):
    '''
    Args:
        df_dict: dictionary of {ticker: df, ...}
    '''
    l_tickers = list(df_dict.keys())
    is_single = len(l_tickers) == 1

    # Add KER
    df_dict = {t: add_KER(df, atr_period)[df.index > pd.Timestamp(start_date)] for t,df in df_dict.items()}
    norm_atr = st.checkbox('normalize ATR', value = True)

    if is_single: # Special Handling for Single Ticker
        tickers = None
        df_dict[l_tickers[0]]['ATR'] = df_dict[l_tickers[0]]['ATR']/ df_dict[l_tickers[0]]['Close'] \
                        if norm_atr else df_dict[l_tickers[0]]['ATR']
        atr_periods = st.text_input('more ATR periods to test (comma separated)')
        atr_periods = [int(i) for i in atr_periods.split(',')] if atr_periods else None
        if atr_periods:
            for p in atr_periods:
                df = df_dict[l_tickers[0]]
                df_dict[l_tickers[0]] = add_ATR(df, period = p, normalize = norm_atr,
                    use_ema = use_ema, channel_dict = None, col_name = f'ATR_{p}')
        # MA of ATR
        # str_ma_period = st.text_input('moving averages period (comma-separated for multiple periods)')
        # if str_ma_period:
        #     t = df_p.columns[0]
        #     for p in str_ma_period.split(','):
        #         df_p[f'{p}bars_MA'] = df_p[t].rolling(int(p)).mean().shift()

        # ATR Time-Series
        df_p = df_dict[l_tickers[0]]
        df_p = df_p[[c for c in df_p.columns if 'ATR' in c]]
        fig = px.line( df_p,  y =  df_p.columns,
                    labels = {'x': 'Date', 'y': 'ATR'},
                    title = f'Historical Average True Range ({atr_period} bars)'
                )
        show_plotly(fig)
    else:
        # View ATR time series of all given stocks
        atr_dict = {
            ticker : (df['ATR']/df['Close']).dropna().to_dict() \
                    if norm_atr else df['ATR'].dropna().to_dict()
            for ticker, df in df_dict.items()
            }
        df_p = pd.DataFrame.from_dict(atr_dict)

        # tickers Selection
        tickers = st.multiselect(f'ticker', options = [''] + list(df_dict.keys()))

        # ATR Time-Series
        fig = px.line( df_p,  y = tickers if tickers else df_p.columns,
                    labels = {'x': 'Date', 'y': 'ATR'},
                    title = f'Historical Average True Range ({atr_period} bars)'
                )
        show_plotly(fig) #, height = chart_size, title = f"Price chart({interval}) for {l_tickers[0]}")

    # ATR Histogram
    fig = px.histogram(df_p, x = tickers if tickers else df_p.columns,
            barmode = chart_configs['barmode'],
            title = f'Average True Range ({atr_period} bars) Distribution',
            nbins = chart_configs['n_bins'])
    show_plotly(fig)

    # KER Time-Series
    KER_dict = { ticker : df['KER'].dropna().to_dict()
            for ticker, df in df_dict.items()
        }
    df_p = pd.DataFrame.from_dict(KER_dict)

    fig = px.line( df_p,  y = tickers if tickers else df_p.columns,
                labels = {'x': 'Date', 'y': 'KER'},
                title = f'Historical efficiency ratio ({atr_period} bars)'
            )
    show_plotly(fig)
    # KER histogram
    fig = px.histogram(df_p, x = tickers if tickers else df_p.columns,
            barmode = chart_configs['barmode'],
            title = f'Efficiency Ratio ({atr_period} bars) Distribution',
            nbins = chart_configs['n_bins'])
    show_plotly(fig)

    # Volume
    if is_single:
        str_ma_period = st.text_input('Volume moving averages period (comma-separated for multiple periods)')
        df_p = df_dict[l_tickers[0]]
        if str_ma_period:
            t = df_p.columns[0]
            for p in str_ma_period.split(','):
                df_p[f'Volume_{p}bars_MA'] = df_p["Volume"].rolling(int(p)).mean().shift()
        df_p = df_p[[c for c in df_p.columns if 'Volume' in c]]
    else:
        volume_dict = {ticker: df['Volume'].dropna().to_dict()
                        for ticker,df in df_dict.items()}
        df_p = pd.DataFrame.from_dict(volume_dict)

    volume_scatter = px.line( df_p,  y = tickers if tickers else df_p.columns,
                labels = {'x': 'Date', 'y': 'Volume'},
                title = f'volume scatter plot'
            )
    volume_hist = px.histogram(df_p, x = tickers if tickers else df_p.columns,
            barmode = chart_configs['barmode'],
            title = f'Volume Distribution',
            nbins = chart_configs['n_bins'])
    show_plotly(volume_scatter)
    show_plotly(volume_hist)

def Main():
    with st.sidebar.expander("ATR"):
        st.info(f'''
            [Average True Range](https://www.thebalance.com/how-average-true-range-atr-can-improve-trading-4154923):
            Compare risk across multiple stocks and determine your [position sizing](https://therobusttrader.com/how-to-use-atr-in-position-sizing/)
        ''')

    tickers = tickers_parser(st.text_input('enter stock ticker(s) [space separated]'), max_items = None)
    with st.sidebar.expander('timeframe', expanded = False):
        today = datetime.date.today()
        end_date = st.date_input('Period End Date', value = today)
        if st.checkbox('pick start date'):
            start_date = st.date_input('Period Start Date', value = today - datetime.timedelta(days = 365))
        else:
            tenor = st.text_input('Period', value = '250b')
            start_date = (BusinessDate(end_date) - tenor).to_date()
            st.info(f'period start date: {start_date}')

        # TODO: allow manual handling of data_start_date
        data_start_date = (BusinessDate(start_date) - "1y").to_date()
        l_interval = ['1d','1m', '5m','1h','1wk']
        interval = st.selectbox('interval', options = l_interval)
        if interval.endswith(('m','h')):
            st.warning(f'intraday data cannot extend last 60 days')

    if tickers:
        with st.sidebar.expander('ATR Configs', expanded = True):
            use_ema = st.checkbox('use exponential moving aveage')
            atr_period = st.number_input('ATR Period (number of bars)', value = 22)
            atr_multiplier = st.number_input('ATR multiplier (stop-loss size)', value = 2, step = 1)
            var = st.number_input('Value To Risk (max drawdown on one position)', value = 1000)

        data_dict = get_yf_data(tickers, start_date = data_start_date, end_date = end_date, interval = interval)
        data = data_dict['prices'].copy()
        df_return = data_dict['returns'].copy()

        with st.expander('raw data'):
            st.subheader('Price Data')
            st.write(data)

        l_tickers = df_return.columns.tolist()
        if len(l_tickers) != len(tickers.split(' ')):
            st.warning(f'having trouble finding the right ticker?\nCheck it out first in `DESC` :point_left:')

        # l_DFs is a list of [ {ticker: df}, ...]
        df_dict = { l_tickers[0]: data} if len(l_tickers) ==1 else \
                get_dfs_by_tickers(data)
        results = [ {**{'ticker': t},
                    **get_ATR_calc(df, period = atr_period,
                        use_ema = use_ema, atr_multiplier = atr_multiplier,
                        var = var, price_col = 'Adj Close'
                        )}
            for t, df in df_dict.items() ]

        # add HK lot size
        for r in results:
            if ".HK" in r['ticker']:
                r['lot_size'] = get_lot_size(r['ticker'])

        with st.expander(f'ATR Results', expanded = True):
            st.write(pd.DataFrame(results))

        with st.expander('Visualize ATR'):
            chart_configs = get_charts_configs(
                                st_asset = st.sidebar.expander("Chart Configs")
                                )
            visualize_features(df_dict, chart_configs = chart_configs, atr_period = atr_period, start_date = start_date)


if __name__ == '__main__':
    Main()
