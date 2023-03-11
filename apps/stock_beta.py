import os, sys, json
import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.express as px
from businessdate import BusinessDate

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.st_utils import show_plotly, plotly_hist_draw_hline
from toolbox.yf_utils import tickers_parser, get_stocks_data
from toolbox.data_utils import JsonLookUp
from apps.stock_members import get_index_tickers

@st.cache
def get_yf_data(tickers, start_date, end_date, interval, group_by = 'column'):
    return get_stocks_data(tickers,
        yf_download_params = {'start': start_date, 'end': end_date,
            'interval': interval, 'group_by': group_by}
        )

def get_betas(df_returns, benchmark_col):
    '''
    return a dictionary of the stats used for beta calcuation
    Args:
        df_returns: dataframe of returns including returns for the benchmark
    '''
    l_tickers = [col for col in df_returns.columns if col != benchmark_col]
    results = [{
        'ticker': t,
        'sigma': np.std(df_returns[t]),
        'correl': np.corrcoef(df_returns[benchmark_col], df_returns[t])[0,1],
        'exp_excess_return': (df_returns[t] - df_returns[benchmark_col]).mean(),
        'sd_excess_return': (df_returns[t] - df_returns[benchmark_col]).std(),
        'cumulative_return': (df_returns[t] + 1).cumprod().iloc[-1] - 1
        }
        for t in l_tickers
    ]
    benchmark_sigma = np.std(df_returns[benchmark_col])
    for r in results:
        r['beta'] = (r['sigma']/ benchmark_sigma) * r['correl']
        r['sharpe_int'] = r['exp_excess_return']/ r['sd_excess_return']
        r['sharpe_norm'] = r['sharpe_int'] * np.sqrt(len(df_returns))
        r['exp_excess_return_pct'] = r['exp_excess_return'] * 100
    return results

def Main():
    with st.sidebar.expander("BETA"):
        st.info(f'''
            Beta Analysis vs Benchmark Security
        ''')

    default_tickers = get_index_tickers(
                        st_asset = st.sidebar.expander('Load an Index', expanded = True)
                        )
    tickers = tickers_parser(
                st.text_input('enter stock ticker(s) [space separated]',
                    value = default_tickers)
                )
    with st.sidebar.expander('settings', expanded = False):
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

    if tickers:
        side_config = st.sidebar.expander('charts configure', expanded = False)
        with side_config:
            show_ohlc = st.checkbox('ohlc chart', value = True)
            # b_two_col = st.checkbox('two-column view', value = True)
            chart_size = st.number_input('Chart Size', value = 500, min_value = 400, max_value = 1500)


        data_dict = get_yf_data(tickers, start_date = start_date, end_date = end_date, interval = interval)
        df_returns = data_dict['returns'].copy()

        with st.expander('view returns data'):
            st.subheader('Returns')
            st.write(df_returns)

        l_tickers = df_returns.columns.tolist()
        if len(l_tickers) != len(tickers.split(' ')):
            st.warning(f'having trouble finding the right ticker?\nCheck it out first in `DESC` :point_left:')

        l_col, r_col = st.columns(2)
        with l_col:
            benchmark_ticker = st.selectbox('benchmark security', options = tickers.split())
            beta_json = get_betas(df_returns, benchmark_col = benchmark_ticker.upper())
            # TODO: add dividend yield?
            beta_df = pd.DataFrame.from_dict(beta_json)
        with r_col:
            plot_var_options = [col for col in beta_df.columns if col not in ['ticker']]
            y_var = st.selectbox('y-axis variable', options = plot_var_options)
            x_var = st.selectbox('x-axis variable', options = plot_var_options)

        with st.expander('Betas Calcuation'):
            st.write(beta_df)

        fig = px.scatter(beta_df, x = x_var, y = y_var, color = 'ticker')
        fig.update_layout(showlegend = False)
        show_plotly(fig)

        #TODO: individual stock shows beta vs return over time

if __name__ == '__main__':
    Main()
