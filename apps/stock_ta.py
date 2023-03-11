import os, sys, json, datetime
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from businessdate import BusinessDate

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.st_auth import run_if_auth
from toolbox.st_utils import show_plotly, plotly_hist_draw_hline
# from toolbox.scrape_utils import get_proxies
from toolbox.yf_utils import tickers_parser, get_stocks_ohlc, valid_stock, get_stock_info
from toolbox.plotly_utils import plotly_ohlc_chart, get_moving_average_col, \
                            add_Scatter, add_Scatter_Event, add_color_event_ohlc
from toolbox.ta_utils import add_moving_average, add_MACD, add_AD, add_OBV, add_RSI, \
                            add_ADX, add_Impulse, add_ATR, add_avg_penetration, \
                            market_classification, efficiency_ratio
from strategies.utils import add_stops_trailing
from strategies.macd_divergence import detect_macd_divergence
from strategies.kangaroo_tails import detect_kangaroo_tails
from strategies.vol_breakout import detect_vol_breakout, detect_volatility_contraction, \
                                detect_low_vol_pullback, detect_VCP
from strategies.buy_and_hold import daily_buy_and_hold, value_surfing

def get_stock_info_container(stock_info_obj, st_asset = st.sidebar):
    container_obj = st_asset.expander(f'''
                    {stock_info_obj['price']['symbol']} : {stock_info_obj['price']['longName']}
                    ''', expanded = True)
    str_links = f'[:link:]({stock_info_obj["assetProfile"]["website"]}) ' \
                if 'website' in stock_info_obj["assetProfile"].keys() else ''
    str_links += f'[:newspaper:](https://www.reuters.com/companies/{stock_info_obj["price"]["symbol"]}/news)' \
                if stock_info_obj['price']['symbol'].endswith(('.HK', '.TO')) else ''
    container_obj.write(str_links)
    if 'shortRatio' in stock_info_obj['defaultKeyStatistics'].keys():
        container_obj.write(f'''
            [days to cover](https://finance.yahoo.com/news/short-ratio-stock-sentiment-indicator-210007353.html): `{stock_info_obj["defaultKeyStatistics"]["shortRatio"]}`
        ''')
    return container_obj

def add_div_col(df_price, df_div, div_col_name = 'ex-dividend'):
    # assume both df has date index
    if len(df_div) > 0:
        ex_div_dates = df_div.index.tolist()
        df_price[div_col_name] = [d in ex_div_dates for d in df_price.index.tolist()]
    return df_price

def add_event_col(df_price, df_events, event_col_name, ignore_time = True):
    ''' add an event column based on df_events to df_price assuming that both df has a date index
    Args:
        ignore_time: remove time in df_events (see: https://stackoverflow.com/questions/24786209/dropping-time-from-datetime-m8-in-pandas)
    '''

    if len(df_events)>0:
        event_dates = df_events.index.normalize().tolist()
        df_price[event_col_name] = [d in event_dates for d in df_price.index.tolist()]
    return df_price

@run_if_auth
def show_beta_features(data, atr_period, interval,
    l_events_to_color , l_col_to_scatter, st_asset = None):
    ''' show ST interface and update l_events_to_color and l_col_to_scatter
    '''
    st_asset = st_asset if st_asset else st.expander('beta features')
    with st_asset:
        l_col, m_col, r_col = st.columns(3)
        with m_col:
            st.write('#### Low Volatility Pullbacks')
            lvpb_period = st.number_input('Low Volatility Pullbacks Period', value = 22)
            data = detect_low_vol_pullback(data, period = lvpb_period, col_name = 'LVPB',
                    price_col = 'Close') if st.checkbox('show Low Volatility Pullbacks') else data
            l_events_to_color.append({'column': 'LVPB', 'color': 'LightPink'})

            st.write(f'#### Vol Breakout')
            vol_buysell = st.checkbox('Show Buy Signals', value = True)
            vol_threshold = st.number_input('Vol Breakout Threshold (% of ATR)', value = 1.0)
            ignore_gap = st.checkbox('ignore gap', value = False)
            data = detect_vol_breakout(data, period = atr_period, ignore_gap = ignore_gap,
                    threshold = vol_threshold, ignore_volume = False,
                    do_buy = vol_buysell) if st.checkbox(f'Show {atr_period} bars Vol Breakout') else data
            l_events_to_color.append({'column': 'vol_breakout', 'color': 'Aquamarine' if vol_buysell else 'HotPink'})

        with l_col:
            st.write('#### Volatility Consolidation')
            VCP_MAs = st.text_input("Cascading ATR Periods (commas-separated)",
                    value = '22,11') if st.checkbox('Detect Volatilitly Contraction') else None
            VCP_MAs = [int(p) for p in VCP_MAs.split(',')] if VCP_MAs else None
            data = detect_volatility_contraction(data, atr_periods = VCP_MAs,
                    period = st.number_input('Look-back period', value = 100, min_value = 1),
                    threshold = st.number_input('ATR threshold (looking for ATR below this percentile in the look-back period)',  value = 0.05),
                    col_name = 'VCP', debug = True) if VCP_MAs else data
            l_events_to_color.append({'column': 'VCP', 'color': 'LightSkyBlue'})
            # data = detect_VCP(data, ma_cascade = VCP_MAs,
            #         lvpb_period = lvpb_period, ATR_period = atr_period,
            #         col_name = 'VCP_setup', debug_mode = True) if VCP_MAs else data
            # beta_events_to_plot.append('VCP_setup')
        with r_col:
            st.write(f'#### Visualize Stops')
            trade_date = st.date_input('trade date')
            td_close = data[data.index.date == trade_date]['Close'][0] if trade_date != datetime.date.today() else 0
            entry_price = st.number_input('entry price', value = td_close)
            init_stop = st.number_input('initial stop')
            if all([trade_date, entry_price, init_stop]):
                data = add_stops_trailing(data, trade_date = trade_date,
                            entry_price = entry_price, init_stop = init_stop,
                            trailing_atr = st.number_input('trailing stop ATR multiplier', value = 2),
                            breakeven_r = st.number_input('breakeven R', value = 0),
                            debug_mode = True
                            )
                l_col_to_scatter.append({'column': 'stops', 'color': 'BlueViolet'})

        with r_col:
            avail_strategy = ['', 'value_surfing']
            avail_strategy += ['buy_and_hold'] if interval == '1d' else []
            vis_strategy = st.selectbox('Visualize Strategy',options = avail_strategy)
            if vis_strategy == 'buy_and_hold':
                st.write(f'#### Buy-and-Hold')
                data = daily_buy_and_hold(data,
                        atr_stop = st.number_input('ATR Stop', value =3),
                        req_pos_macd = st.checkbox('Requires Positive MACD', help = "refers to MACD line (MACD Hist is Always required to be positive)")
                        )
                l_events_to_color.append({'column': 'trading_window', 'color': 'PeachPuff'})
                l_events_to_color.append({'column': 'position', 'color': 'LightSteelBlue'})
                # l_col_to_scatter.append({'column':'stop', 'color': 'BlueViolet'})
            elif vis_strategy == 'value_surfing':
                st.write(f'#### Value Surfing :ocean:')
                data = value_surfing(data,
                        stop_ATR = st.number_input('ATR Stop', value =1.0, help = 'relative to fast EMA; 0 will set stop to slow EMA'),
                        exit_ATR = st.number_input('Exit ATR', value =3.0, help = 'relative to fast EMA'),
                        ma_period_fast = st.number_input('Fast EMA', value = 11),
                        ma_period_slow = st.number_input('Slow EMA', value = 22),
                        min_atr_wide = st.number_input('Minimum Value Zone Width', value = 0.5, help = 'as multiple of ATR'),
                        )
                l_events_to_color.append({'column': 'position', 'color': 'LightSteelBlue'})
                # l_col_to_scatter.append({'column':'stop', 'color': 'BlueViolet'})

def Main():
    with st.sidebar.expander("GP"):
        st.info(f'''
            Graph Prices (open-high-low-close)

            * inspired by this [blog post](https://towardsdatascience.com/creating-a-finance-web-app-in-3-minutes-8273d56a39f8)
                and this [youtube video](https://youtu.be/OhvQN_yIgCo)
            * plots by Plotly with thanks to this [kaggle notebook](https://www.kaggle.com/mtszkw/technical-indicators-for-trading-stocks)
        ''')

    tickers = tickers_parser(st.text_input('enter stock ticker'), max_items = 1)
    with st.sidebar.expander('timeframe', expanded = True):
        today = datetime.date.today()
        end_date = st.date_input('Period End Date', value = today)
        if st.checkbox('pick start date'):
            start_date = st.date_input('Period Start Date', value = today - datetime.timedelta(days = 365))
        else:
            tenor = st.text_input('Period', value = '6m')
            start_date = (BusinessDate(end_date) - tenor).to_date()
            st.info(f'period start date: {start_date}')

        # TODO: allow manual handling of data_start_date
        # l_interval = ['1d','1wk','1m', '2m','5m','15m','30m','60m','90m','1h','5d','1mo','3mo']
        interval = st.selectbox('interval', options = ['1d', '1wk', '1mo'])
        is_intraday = interval.endswith(('m','h'))
        data_start_date = start_date if is_intraday else \
                        (BusinessDate(start_date) - "1y").to_date()
        if is_intraday:
            st.warning(f'''
                intraday data cannot extend last 60 days\n
                also, some features below might not work properly
                ''')

    if tickers:
        stock_obj = yf.Ticker(tickers)
        if not valid_stock(stock_obj):
            st.error(f'''
            {tickers} is an invalid ticker.\n
            Having trouble finding the right ticker?\n
            Check it out first in `DESC` :point_left:
            ''')
            return None
        stock_info_obj = get_stock_info(tickers)

        side_config = st.sidebar.expander('charts configure', expanded = False)
        with side_config:
            show_df = st.checkbox('show price dataframe', value = False)
            chart_size = st.number_input('Chart Size', value = 1200, min_value = 400, max_value = 1500, step = 50)

        side_stock_info = get_stock_info_container(stock_info_obj, st_asset= st.sidebar)

        data = get_stocks_ohlc(tickers,
                start_date = data_start_date, end_date = end_date,
                interval = interval,)
                # proxies = get_proxies())

        with st.expander('Indicators'):
            l_col, m_col , r_col = st.columns(3)
            with l_col:
                st.write('#### the moving averages')
                ma_type = st.selectbox('moving average type', options = ['', 'ema', 'sma', 'vwap'])
                periods = st.text_input('moving average periods (comma separated)', value = '22,11')
                if ma_type:
                    for p in periods.split(','):
                        data = add_moving_average(data, period = int(p), type = ma_type)
                st.write('#### volume-based indicators')
                # do_volume_profile = st.checkbox('Volume Profile')
                data = add_AD(data) if st.checkbox('Show Advance/ Decline') else data
                data = add_OBV(data)  if st.checkbox('Show On Balance Volume') else data
            with m_col:
                st.write('#### MACD')
                do_MACD = st.checkbox('Show MACD?', value = True)
                fast = st.number_input('fast', value = 12)
                slow = st.number_input('slow', value = 26)
                signal = st.number_input('signal', value = 9)
                if do_MACD:
                    data = add_MACD(data, fast = fast, slow = slow, signal = signal )
            with r_col:
                st.write('#### oscillator')
                do_RSI = st.checkbox('RSI')
                data = add_RSI(data, n = st.number_input('RSI period', value = 13)) if do_RSI else data
                tup_RSI_hilo = st.text_input('RSI chart high and low line (comma separated):', value = '70,30').split(',') \
                                if do_RSI else None
                tup_RSI_hilo = [int(i) for i in tup_RSI_hilo] if tup_RSI_hilo else None
                if do_RSI:
                    data_over_hilo_pct = sum(
                        ((data['RSI']> tup_RSI_hilo[0]) | (data['RSI']< tup_RSI_hilo[1])) & (data.index > pd.Timestamp(start_date))
                        ) / len(data[data.index > pd.Timestamp(start_date)])
                    st.info(f"""
                    {round(data_over_hilo_pct * 100, 2)}% within hilo\n
                    5% of peaks and valley should be within hilo
                    """)

                st.write('#### True Range Related')
                atr_period = int(st.number_input('Average True Range Period', value = 13))
                atr_ema = st.checkbox('use EMA for ATR', value = True)
                show_ATR = st.checkbox('show ATR?', value = False)
                if ma_type:
                    st.write('##### ATR Channels')
                    atr_ma_name = st.selectbox('select moving average for ATR channel',
                                    options = [''] + get_moving_average_col(data.columns))
                    atr_channels = st.text_input('Channel Lines (comma separated)', value = "1,2,3") \
                                    if atr_ma_name else None
                    fill_channels = st.checkbox('Fill Channels with color', value = False) \
                                    if atr_ma_name else None
                else:
                    atr_ma_name = None

                data = add_ATR(data, period = atr_period, use_ema = atr_ema,
                            channel_dict = {atr_ma_name: [float(c) for c in atr_channels.split(',')]} \
                                if atr_ma_name else None
                            )

                st.write(f'##### Directional System')
                do_ADX = st.checkbox('Show ADX')
                data = add_ADX(data, period = st.number_input("ADX period", value = 13)) \
                        if do_ADX else data

        with st.expander('advanced settings'):
            l_col, m_col , r_col = st.columns(3)
            with l_col:
                st.write('#### Market Type Classification')
                mkt_class_period = int(st.number_input('peroid (match your trading time domain)', value = 66))
                mkt_class = market_classification(data, period = mkt_class_period,
                                debug = False) if mkt_class_period else None
                if mkt_class:
                    side_stock_info.write(f'market is `{mkt_class}` for the last **{mkt_class_period} bars**')
                    side_stock_info.write(f'[kaufman efficiency_ratio](https://strategyquant.com/codebase/kaufmans-efficiency-ratio-ker/) ({mkt_class_period} bars): `{round(efficiency_ratio(data, period = mkt_class_period),2)}`')
                st.write('#### Events')
                do_div = st.checkbox('show ex-dividend dates')
                if do_div:
                    data = add_div_col(df_price = data, df_div = stock_obj.dividends)
                    side_stock_info.write(
                        stock_obj.dividends[stock_obj.dividends.index > pd.Timestamp(start_date)]
                        )
                do_earnings = st.checkbox('show earning dates')
                if do_earnings and isinstance(stock_obj.calendar, pd.DataFrame):
                    data = add_event_col(df_price = data,
                                df_events = stock_obj.calendar.T.set_index('Earnings Date'),
                                event_col_name= "earnings")
                    side_stock_info.write(stock_obj.calendar.T)

                if do_MACD and ma_type:
                    st.write("#### Elder's Impulse System")
                    impulse_ema = st.selectbox('select moving average for impulse',
                                    options = [''] + get_moving_average_col(data.columns))
                    data = add_Impulse(data, ema_name = impulse_ema) if impulse_ema else data

            avg_pen_data = None
            with m_col:
                if ma_type:
                    st.write("#### Average Penetration for Entry/ SafeZone")
                    fair_col = st.selectbox('compute average penetration below',
                                    options = [''] + get_moving_average_col(data.columns))
                    avg_pen_data = add_avg_penetration(df = data, fair_col = fair_col,
                                        num_of_bars = st.number_input('period (e.g. 4-6 weeks)', value = 30), # 4-6 weeks
                                        use_ema = st.checkbox('use EMA for penetration', value = False),
                                        ignore_zero = st.checkbox('ignore days without penetration', value = True),
                                        coef = st.number_input(
                                            'SafeZone Coefficient (stops should be set at least 1x Average Penetration)',
                                            value = 1.0, step = 0.1),
                                        get_df = True, debug = True
                                    ) if fair_col else None
            with r_col:
                if do_MACD:
                    st.write('#### MACD Bullish Divergence')
                    if st.checkbox('Show Divergence'):
                        data = detect_macd_divergence(data,
                                period = st.number_input('within number of bars (should be around 3 months)', value = 66),
                                threshold = st.number_input('current low threshold (% of previous major low)', value = 0.95),
                                debug = True
                                )
                st.write(f'#### Detect Kangaroo Tails')
                tail_type = st.selectbox('Tail Type',
                                options = ['', 0, 1, -1])
                data = detect_kangaroo_tails(data,
                        atr_threshold = st.number_input('ATR Threshold', value = 2.0),
                        period = st.number_input('period', value = 22), tail_type = tail_type) \
                        if tail_type else data

        beta_events_to_plot, l_events_to_color, l_col_to_scatter = [], [], []
        show_beta_features(data = data, l_events_to_color=l_events_to_color,
            l_col_to_scatter = l_col_to_scatter,
            atr_period = atr_period, interval = interval)

        if show_df:
            with st.expander(f'raw data (last updated: {data.index[-1].strftime("%c")})'):
                st.write(data)

        if isinstance(avg_pen_data, pd.DataFrame):
            with st.expander('Buy Entry (SafeZone)'):
                avg_pen_dict = {
                    'average penetration': avg_pen_data['avg_lp'][-1],
                    'ATR': avg_pen_data['ATR'][-1],
                    'penetration stdv': avg_pen_data['std_lp'][-1],
                    'number of penetrations within period': avg_pen_data['count_lp'][-1],
                    'last': avg_pen_data['Close'][-1],
                    'expected ema T+1': avg_pen_data[fair_col][-1] + (avg_pen_data[fair_col][-1] - avg_pen_data[fair_col][-2])
                    }
                avg_pen_dict = {k:round(v,2) for k,v in avg_pen_dict.items()}
                avg_pen_dict['buy target T+1'] = avg_pen_dict['expected ema T+1'] - avg_pen_dict['average penetration']
                st.write(avg_pen_dict)
                plot_avg_pen = st.checkbox('plot buy SafeZone and show average penetration df')
                plot_target_buy = False # st.checkbox('plot target buy T+1')
                # if plot_avg_pen:
                #     st.write(avg_pen_data)

        if not(show_ATR) and 'ATR' in data.columns:
            del data['ATR']

        #TODO: fix tz issue for interval < 1d
        # see: https://stackoverflow.com/questions/16628819/convert-pandas-timezone-aware-datetimeindex-to-naive-timestamp-but-in-certain-t
        fig = plotly_ohlc_chart(
                df = data if is_intraday else data[data.index > pd.Timestamp(start_date)],
                vol_col = 'Volume',
                tup_rsi_hilo = tup_RSI_hilo,
                b_fill_channel = fill_channels if atr_ma_name else None
                ) #, show_volume_profile = do_volume_profile)
        # SafeZone
        if isinstance(avg_pen_data, pd.DataFrame):
            fig = add_Scatter(fig, df = avg_pen_data[avg_pen_data.index > pd.Timestamp(start_date)], target_col = 'buy_safezone') \
                if plot_avg_pen else fig
            if plot_target_buy:
                fig.add_hline(y = avg_pen_dict['buy target T+1'] , line_dash = 'dot', row =1, col = 1)
        # Events
        for d in ['MACD_Divergence', 'kangaroo_tails', 'ex-dividend', 'earnings'] + beta_events_to_plot:
            if d in data.columns:
                fig = add_Scatter_Event(fig, data[data.index > pd.Timestamp(start_date)],
                        target_col = d,
                        anchor_col = 'Low', textposition = 'bottom center', fontsize = 8,
                        marker_symbol = 'triangle-up', event_label = d[0])
        # Color Events
        for d in l_events_to_color:
            fig = add_color_event_ohlc(fig, data[data.index > pd.Timestamp(start_date)],
                        condition_col = d['column'], color = d['color']
                        ) if d['column'] in data.columns else fig
        # Scatter Columns
        for c in l_col_to_scatter:
            fig = add_Scatter(fig, data[data.index > pd.Timestamp(start_date)],
                    target_col = c['column'], line_color = c['color'])

        show_plotly(fig, height = chart_size,
            title = f"Price chart({interval}) for {tickers} : {stock_info_obj['price']['longName']}")

if __name__ == '__main__':
    Main()
