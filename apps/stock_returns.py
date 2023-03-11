import os, sys
import streamlit as st
import datetime
import yfinance as yf
import pandas as pd
import plotly.express as px
from businessdate import BusinessDate

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.st_utils import show_plotly, plotly_hist_draw_hline
from toolbox.yf_utils import tickers_parser, get_stocks_data
from toolbox.plotly_utils import plotly_ohlc_chart

@st.cache
def get_yf_data(tickers, start_date, end_date, interval, group_by = 'column'):
    return get_stocks_data(tickers,
        yf_download_params = {'start': start_date, 'end': end_date,
            'interval': interval, 'group_by': group_by}
        )

def compare_returns(df_returns, df_prices, chart_size = 500):
    '''
    plot multi stocks returns in ST using PX
    '''
    l_tickers = df_returns.columns.tolist()
    l_col , r_col = st.columns(2)

    # returns
    fig = px.line(df_returns, y = df_returns.columns.tolist(),
                title = f'stock returns'
                )
    show_plotly(fig, height=chart_size, st_asset = l_col)

    # return dist
    fig = px.histogram(df_returns, y = l_tickers,
        opacity = 0.8,
        title = f'returns distribution')
    show_plotly(fig, height = chart_size, st_asset = r_col)

    # cumulative returns
    fig = px.line((df_returns+1).cumprod(), y = df_returns.columns.tolist(),
            title = f'growtht of $1 invested on {df_returns.index[0]}',
            labels = {'value': f'cumulative returns'},
            # color_discrete_sequence = ["#b58900"]
            )
    show_plotly(fig, height = chart_size, st_asset = l_col)

    # compare volume
    for t in l_tickers:
        df_prices['Dollar_Traded', t] = df_prices['Volume', t] * df_prices['Adj Close', t]

    fig = px.line(df_prices['Dollar_Traded'], y = l_tickers,
            title = f'Dollar Traded',
            labels = {'value': f'Dollar Traded'},
            # color_discrete_sequence = ["#b58900"]
            )
    show_plotly(fig, height = chart_size, st_asset = r_col)

def plot_returns(df_returns, df_prices, target_ticker,
    chart_size = 500, show_ohlc = True):
    '''
    plot target_ticker returns in ST using PX
    '''
    # TODO: remove show_ohlc arg
    l_col , r_col = st.columns(2)

    # returns
    fig = px.line(df_returns, y = target_ticker,
                title = f'{target_ticker} returns',
                color_discrete_sequence = ["#b58900"],
                )
    show_plotly(fig, height=chart_size, st_asset = l_col)

    # simple price chart
    # if show_ohlc:
    df_plot = pd.DataFrame(
        {'Open': df_prices['Open'][target_ticker],
        'High': df_prices['High'][target_ticker],
        'Low': df_prices['Low'][target_ticker],
        'Close': df_prices['Close'][target_ticker],
        'Volume': df_prices['Volume'][target_ticker],
        'Date': df_prices.index
        }
    )
    #     fig = plotly_ohlc_chart(df_plot, vol_col = 'Volume', date_col = 'Date',
    #         show_legend = False, show_volume_profile = False)
    fig = plotly_ohlc_chart(df_plot, date_col = 'Date',
            show_legend = False, show_volume_profile = False,
            show_range_slider = False)
    # else:
    #     fig = px.line(df_prices['Adj Close'], y = target_ticker,
    #             color_discrete_sequence = ["#b58900"])
    show_plotly(fig, height = chart_size, title=f'price of {target_ticker}',
                st_asset = l_col)

    # return dist
    fig = px.histogram(df_returns, y = target_ticker,
        color_discrete_sequence = ["#b58900"],
        title = f'{target_ticker} returns distribution (with 2stdv lines)')
    two_stdv = df_returns[target_ticker].mean() + df_returns[target_ticker].std() * 2
    plotly_hist_draw_hline(fig, l_value_format = [{'value': v} for v in [two_stdv, -two_stdv]])
    show_plotly(fig, height = chart_size, st_asset = r_col)

    # if show_ohlc:
    #     #cumulative returns
    #     fig = px.line((df_returns+1).cumprod(), y = target_ticker,
    #             title = f'growtht of $1 invested in {target_ticker} on {df_returns.index[0]}',
    #             labels = {target_ticker: f'{target_ticker} cumulative returns'},
    #             color_discrete_sequence = ["#b58900"]
    #             )
    #     show_plotly(fig, height = chart_size)
    # else:
    # volume at price
    # https://medium.com/swlh/how-to-analyze-volume-profiles-with-python-3166bb10ff24
    idx = pd.IndexSlice
    df_vp = df_prices.loc[:, idx[['Adj Close', 'Volume'],target_ticker]]
    df_vp.columns = ['Adj Close', 'Volume']

    fig = px.histogram(df_vp, y = 'Adj Close', x = 'Volume', title = f'Volume-at-price: {target_ticker}',
            orientation = 'h', nbins = 100, color_discrete_sequence = ["#b58900"]
            )
    show_plotly(fig, height = chart_size, st_asset = r_col)

def Main():
    with st.sidebar.expander("RT"):
        st.info(f'''
            Returns Analysis: what does your stock's return distribution look like? How fat are the tails?

            * inspired by this [blog post](https://www.codingfinance.com/post/2018-04-03-calc-returns-py/)
        ''')

    tickers = tickers_parser(st.text_input('enter stock ticker(s) [space separated]'))
    with st.sidebar.expander('settings', expanded = True):
        today = datetime.date.today()
        end_date = st.date_input('Period End Date', value = today)
        if st.checkbox('pick start date'):
            start_date = st.date_input('Period Start Date', value = today - datetime.timedelta(days = 365))
        else:
            tenor = st.text_input('Period', value = '250b')
            start_date = (BusinessDate(end_date) - tenor).to_date()
            st.info(f'period start date: {start_date}')

        l_interval = ['1d','1m', '2m','5m','15m','30m','60m','90m','1h','5d','1wk','1mo','3mo']
        interval = st.selectbox('interval', options = l_interval)
        if interval.endswith(('m','h')):
            st.warning(f'intraday data cannot extend last 60 days')

    if tickers:
        side_config = st.sidebar.expander('charts configure', expanded = False)
        with side_config:
            # show_ohlc = st.checkbox('ohlc chart', value = True)
            # b_two_col = st.checkbox('two-column view', value = True)
            chart_size = st.number_input('Chart Size', value = 500, min_value = 400, max_value = 1500)

        # if len(tickers.split())==1:
        #     st.warning(f'This function works best with more than one tickers. Some features below might not render...')

        data_dict = get_yf_data(tickers, start_date = start_date, end_date = end_date, interval = interval)
        data = data_dict['prices'].copy()
        df_return = data_dict['returns'].copy()

        with st.expander('raw data'):
            st.subheader('Price Data')
            st.write(data)
            st.subheader('Returns')
            st.write(df_return)

        l_tickers = df_return.columns.tolist()
        if len(l_tickers) != len(tickers.split(' ')):
            st.warning(f'having trouble finding the right ticker?\nCheck it out first in `DESC` :point_left:')
        single_ticker = len(l_tickers) == 1

        l_col , r_col = st.columns(2)
        with l_col:
            target_ticker = st.selectbox('Analyze', options = l_tickers if single_ticker else [''] + l_tickers)

        if target_ticker:
            with r_col:
                with st.expander(f'{target_ticker} descriptive stats'):
                    st.write(df_return[target_ticker].describe())

            if single_ticker:
                tmp_idx = pd.MultiIndex.from_tuples([(col, target_ticker) for col in data.columns], names = ['variable', 'ticker'])
                data.columns = tmp_idx

            plot_returns(df_returns = df_return, df_prices = data,
                target_ticker = target_ticker, chart_size = chart_size)
        else:
            compare_returns(df_returns = df_return, df_prices = data,
                chart_size = chart_size)

if __name__ == '__main__':
    Main()
