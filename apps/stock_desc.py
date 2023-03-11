import os, sys
import streamlit as st
import yfinance as yf
# from yahooquery import Ticker
import pandas as pd
import plotly.express as px

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.yf_utils import valid_stock, tickers_parser, get_stock_info, get_stock_financials
from toolbox.plotly_utils import plotly_ohlc_chart

def Main():
    ticker = tickers_parser(st.text_input('enter a stock ticker'), max_items = 1)
    with st.sidebar.expander("DESC"):
        st.info(f'''
            Description: get general information about the company, upcoming events, etc.
        ''')

    if ticker:
        # ticker = ticker.split('.')[0].zfill(4) + '.HK' if '.HK' in ticker.upper() else ticker
        side_config = st.sidebar.expander('configure', expanded = True)
        with side_config:
            show_ohlc = st.checkbox('ohlc chart', value = True)
            show_volume = st.checkbox('show volume', value = True)
            b_two_col = st.checkbox('two-column view', value = True)
            chart_size = st.number_input('Chart Size', value = 500, min_value = 400, max_value = 1500)

        if b_two_col:
            col1, col2 = st.columns((2,1))
        else:
            col1 = col2 = st.container()

        stock = yf.Ticker(ticker)
        if not valid_stock(stock):
            st.error(f'Cannot find `{ticker}`')
            return None

        #TODO:
        # 1. show key keys info
        # 2. add twitter & NewsAPI
        # 4. Download price DF

        with col1:
            # migrate stock info to use yahooquery
            stock_info = get_stock_info(ticker)
            # yq_stock = Ticker(ticker)

            with st.expander(f'Stock Info for {stock_info["price"]["longName"]}'):
                if st.checkbox('show info JSON'):
                    st.write(stock_info)
                str_desc = f'[:link:]({stock_info["assetProfile"]["website"]}) ' \
                            if 'website' in stock_info['assetProfile'].keys() else ''
                str_desc += stock_info["assetProfile"]["longBusinessSummary"] \
                            if "longBusinessSummary" in stock_info["assetProfile"].keys() else ":warning: Business Summary not available"
                st.write(f'{str_desc}')

            df_all = stock.history(period = "max")
            with side_config:
                number_td = st.number_input("Number of trading days", value = min(250, len(df_all)),
                                min_value = 5, max_value = len(df_all))
            df_all = df_all.tail(number_td)

            with st.expander('Price Chart', expanded = True):
                if show_ohlc:
                    fig = plotly_ohlc_chart(df = df_all, vol_col = 'Volume' if show_volume else None)
                else:
                    fig = px.line(df_all, y = 'Close',
                        color_discrete_sequence = ["#b58900"])
                        # color_discrete_sequence = ['yellow'])
                fig.update_layout(height = chart_size,
                    title = f'{ticker.upper()} last {number_td} trading days- ohlc chart',
                    template = 'plotly_dark')
                st.plotly_chart(fig, use_container_width = True, height = chart_size)

            with st.expander('Historical Prices'):
                st.dataframe(df_all)

            

        with col2:
            # show actions (dividends, splits)
            with st.expander("Corporate Actions"):
                st.dataframe(stock.actions)

            # show dividends
            with st.expander("Dividends"):
                st.dataframe(stock.dividends)

            # show splits
            with st.expander("Splits"):
                st.dataframe(stock.splits)

            # show major holders
            with st.expander("Major Holders"):
                st.dataframe(stock.major_holders)

            # show institutional holders
            with st.expander("Institutional Holders"):
                st.dataframe(stock.institutional_holders)

            # TODO: get these sections from yahooquery
            # show sustainability
            # with st.expander("Sustainability"):
            #     # this is a df issue on ST side:
            #     # https://discuss.streamlit.io/t/after-upgrade-to-the-latest-version-now-this-error-id-showing-up-arrowinvalid/15794/24
            #     # print(type(stock.sustainability))
            #     df_ = stock.sustainability
            #     if isinstance(df_, pd.DataFrame):
            #         df_['Value'] = df_['Value'].astype(str)
            #         st.write(df_)

            # show analysts recommendations
            # with st.expander("Analysts Recommendations"):
            #     # TODO:
            #     # 1. set "Firm" as index
            #     # 2. turn datetime index as a col
            #     st.dataframe(stock.recommendations)

            # show next event (earnings, etc)
            # with st.expander("Calendar"):
            #     if isinstance(stock.calendar, pd.DataFrame):
            #         st.dataframe(stock.calendar.T)

            # show ISIN code - *experimental*
            # with st.expander("ISIN (experimental)"):
            # ISIN = International Securities Identification Number
                # print(stock.isin)
                # print(type(stock.isin))
                # st.write(f"{stock.isin}")


if __name__ == '__main__':
    Main()
