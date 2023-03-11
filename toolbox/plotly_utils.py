import numpy as np
from itertools import cycle
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

def get_moving_average_col(df_columns):
    return [c for c in df_columns if '_' in c and c.split('_')[0] in ['ema', 'sma', 'vwap']]

def get_channels_col(df_columns):
    return [c for c in df_columns if 'ch:' in c]

def add_channel_trace(fig, df, ch_cols, date_col = None, rgb_tup = (255,222,0)):
    ''' Add Channel around MA using ATR
    assume channels are always in pair and uses atr only (i.e. created by add_ATR())
    Args:
        rgb_tup: if none dotted line will be drawn, otherwise channel will appear
                as colored area
    ref: https://plotly.com/python/line-charts/
    '''
    l_ch = [float(col.split('+')[-1].replace('atr',''))
            for col in ch_cols if '+' in col]
    l_ch = sorted(l_ch)[::-1] # descending
    assert len(l_ch) <= 3, f"currently only support up to 3 channels only"

    date_serie = df[date_col] if date_col else df.index

    dash_lines_dict = { # ideal for 3 channels
        'dash': 'GhostWhite',
        'dot': 'LemonChiffon', #'Ivory',
        'dashdot': 'LightGrey'
    }
    # to do color it the same color as the selected ema
    # ref: https://stackoverflow.com/questions/61353532/plotly-how-to-get-the-trace-color-attribute-in-order-to-plot-selected-marker-wi
    for i, ch in enumerate(l_ch):
        ch_hi, ch_lo = [c for c in ch_cols if str(ch) in c]
        if not rgb_tup:
            line_style, line_color = list(dash_lines_dict.items())[i]
            for ich in [ch_hi, ch_lo]:
                fig.add_trace(
                    go.Scatter(x = date_serie, y= df[ich],
                        name = ich,
                        line = {'dash': line_style, 'color': line_color, 'width': 0.5}),
                    row= 1, col= 1
                )
        else:
            fig.add_trace(go.Scatter(
                    x = date_serie.tolist() + date_serie.tolist()[::-1],
                    y = df[ch_lo].tolist() + df[ch_hi].tolist()[::-1],
                    fill = "toself",
                    fillcolor = f'rgba({rgb_tup[0]},{rgb_tup[1]},{rgb_tup[2]},{(i+1)/10.0})',
                    line_color = 'rgba(255,255,255,0)',
                    name = ch_hi
                ),
                row = 1,
                col = 1
            )

    return fig

def add_color_event_ohlc(fig, df, color, condition_col, date_col = None,
        ohlc_col_map = {'o':'Open', 'h':'High', 'l': 'Low', 'c':'Close'}
    ):
    '''color the given column (condition_col) on the ohlc trace
    Args:
        color: css color name
    '''
    df_c = df[df[condition_col] == 1]
    fig.add_trace(
        go.Candlestick( x = df_c[date_col] if date_col else df_c.index,
            open = df_c[ohlc_col_map['o']],
            high = df_c[ohlc_col_map['h']],
            low = df_c[ohlc_col_map['l']],
            close = df_c[ohlc_col_map['c']],
            name = condition_col,
            increasing_line_color = color,
            decreasing_line_color = color
            ),
        row = 1, col = 1
    )
    return fig

def add_impulse_trace(fig, df, date_col = None,
        ohlc_col_map = {'o':'Open', 'h':'High', 'l': 'Low', 'c':'Close'},
        l_rgb_css_color_name = ['red', 'green', 'DodgerBlue']
        ):
    '''add candlestick trace on top to show impulse system
    ref: https://stackoverflow.com/a/66998861/14285096
    '''
    df_green = df[df['impulse'] == 1]
    df_red = df[df['impulse'] == -1]
    df_blue = df[df['impulse'] == 0]

    l_trace_def = [
        {'name': 'long or short', 'df': df_blue, 'color': l_rgb_css_color_name[2]},
        {'name': 'long only', 'df': df_green, 'color': l_rgb_css_color_name[1]},
        {'name': 'short only', 'df': df_red, 'color': l_rgb_css_color_name[0]},
    ]
    for trace in l_trace_def:
        df = trace['df']
        fig.add_trace(
            go.Candlestick( x = df[date_col] if date_col else df.index,
                open = df[ohlc_col_map['o']],
                high = df[ohlc_col_map['h']],
                low = df[ohlc_col_map['l']],
                close = df[ohlc_col_map['c']],
                name = trace['name'],
                increasing_line_color = trace['color'],
                decreasing_line_color = trace['color']
                ),
            row = 1, col = 1
        )
    return fig

def add_ADX_trace(fig, df, ref_row, ref_col = 1, date_col = None,
    line_color_map = {'ADX':'Yellow' , '+DMI': 'DarkOliveGreen', '-DMI': 'DarkRed'}
    ):
    date_serie = df[date_col] if date_col else df.index
    for k, v in line_color_map.items():
        fig.append_trace(go.Scatter(x = date_serie, y = df[k], name = k, line = {'color': v}),
            row = ref_row, col = ref_col)
    return fig

def add_MACD_trace(fig, df, ref_row, ref_col = 1, date_col = None, draw_signal_line = True):
    for c in ['MACD', 'MACD_histogram', 'MACD_signal']:
        assert c in df.columns, f"required column {c} is missing from input df"

    date_serie = df[date_col] if date_col else df.index

    if draw_signal_line:
        fig.add_trace(go.Scatter(x = df.index, y = df['MACD_signal'], name = 'MACD_signal', line = {'color': 'DarkGrey'}),
            row = ref_row, col = ref_col)
        fig.add_trace(go.Scatter(x = df.index, y = df['MACD'], name = 'MACD', line = {'color': 'Gold'}),
            row = ref_row, col = ref_col)
        fig.add_trace(go.Scatter(x = df.index, y = [0 for i in df.index], name = 'MACD_0', line = {'color': 'Grey'}),
            row = ref_row, col = ref_col)

        # can't put histogram on because requires secondary_y in spec during make_subplots()
        # fig.add_trace(go.Bar(x = date_serie, y = df['MACD_histogram'], name = 'MACD_histogram'),
        #     row = ref_row, col = 1, secondary_y = True)

        # applying ranges to yaxis makes the signal line plot look sad
        # fig.update_yaxes(range=[df['MACD_histogram'].min(), df['MACD_histogram'].max()],
        #     row= ref_row, col=1)
    else:
        fig.append_trace(go.Bar(x = date_serie, y = df['MACD_histogram'], name = 'MACD_histogram'),
            row = ref_row, col = ref_col)
    return fig

def add_Scatter(fig, df, target_col, date_col = None, line_color = None):
    date_serie = df[date_col] if date_col else df.index
    fig.append_trace(
        go.Scatter(x = date_serie, y = df[target_col], name = target_col,
                    line = {'color': line_color} if line_color else None),
        row = 1, col = 1
    )
    return fig

def add_Scatter_Event(fig, df, target_col, anchor_col,
        textposition = 'top center', fontsize = None, marker_symbol = None,
        event_label = None, date_col = None):
    ''' add non-zero points in target_col as events to the main chart
    '''
    df_ = df[df[target_col]!=0].copy()
    date_serie = df_[date_col] if date_col else df_.index

    if event_label: # ensure it is the right size
        event_label = event_label if type(event_label) == list else \
                    [event_label for i in range(len(date_serie))]

    # for marker styling see: https://plotly.com/python/marker-style/

    fig.append_trace(
        go.Scatter( x = date_serie, y = df_[anchor_col],
            mode = 'markers+text',
            name = target_col,
            marker_symbol = marker_symbol,
            textposition = textposition,
            textfont_size = fontsize,
            text = event_label if event_label else df_[target_col]
        ),
        row =1, col = 1
    )
    return fig

def add_volume_profile(fig, df, vol_col, price_col, show_legend = False,
        color = 'Ivory', opacity = 0.6):
    '''add volume profile to candlestick chart
    add a go.Bar trace for volume-at-price
    ref: https://stackoverflow.com/questions/58517234/using-a-charting-library-to-overlay-volume-profile-on-a-candlestick-chart-in-pyt
    '''
    # TODO: bug fix, volume profile will disable volume on row 2
    df_vp = df[[price_col, vol_col]].groupby(price_col).sum()
    fig.update_layout(
        xaxis2 = go.layout.XAxis(side = 'top',
                    range = [0,max(df_vp[vol_col])], overlaying = 'x', anchor = 'y',
                    rangeslider = go.layout.xaxis.Rangeslider(visible = False),
                    showticklabels = False),
        # yaxis2 = go.layout.YAxis(side = 'left',
        #             range = [df[price_col].min(), df[price_col].max()],
        #             overlaying = 'y')
        )
    fig.add_trace(
        go.Bar(y = df_vp.index, x = df_vp[vol_col], orientation = 'h',
            name = 'volume profile', showlegend = show_legend,
            xaxis = 'x2', yaxis = 'y',
            marker_color = color, opacity = opacity),
        #secondary_x = True,
        row = 1, col = 1)
    # fig.data[1].update(xaxis = 'x2')
    return fig

def plotly_ohlc_chart(df, vol_col = None, date_col = None, show_volume_profile = False,
        ohlc_col_map = {'o':'Open', 'h':'High', 'l': 'Low', 'c':'Close'},
        show_legend = True, show_range_slider = True,
        tup_rsi_hilo = (70,30), b_fill_channel = False
    ):
    '''
    return a fig object with a ohlc plot
    reference this stackoverflow solution: https://stackoverflow.com/a/65997291/14285096
    Args:
        show_range_slider: only applies if vol_col is None
        tup_rsi_hilo: two numbers representing horizontal lines to be drew on the RSI subplot
        b_fill_channel: fill channels with color instead of having dash line
    '''
    date_serie = df[date_col] if date_col else df.index
    auto_subplot_col = ['MACD_histogram', 'MACD', 'A/D', 'OBV', 'RSI', 'ADX', 'ATR']
    if vol_col:
        row_count = 2
        for c in auto_subplot_col:
            row_count += 1 if c in df.columns else 0

        row_heights = [0.7] + [0.2 for i in range(row_count-1)]

        # Create figure with secondary y-axis
        fig = make_subplots(rows = row_count, cols = 1, shared_xaxes= True,
                vertical_spacing= 0.03,
                subplot_titles = ['OHLC','Volume'] if not show_legend else None,
                row_heights = row_heights)

        # include candlestick with rangeselector
        fig.add_trace(go.Candlestick(x= date_serie,
                        open= df[ohlc_col_map['o']],
                        high= df[ohlc_col_map['h']],
                        low= df[ohlc_col_map['l']],
                        close= df[ohlc_col_map['c']],
                        name = 'OHLC', showlegend = show_legend),
                        row = 1, col =1
                        )

        if show_volume_profile:
            fig = add_volume_profile(fig, df, vol_col = vol_col,
                    price_col = ohlc_col_map['c'], show_legend = show_legend)

        # include a go.Bar trace for volumes
        fig.add_trace(go.Bar(x= date_serie, y= df[vol_col],
                        name = 'volume', showlegend = show_legend),
                       row = 2, col = 1)
        fig.update(layout_xaxis_rangeslider_visible=False)
    else:
        fig = go.Figure(data= go.Candlestick(x = date_serie,
                            open= df[ohlc_col_map['o']],
                            high= df[ohlc_col_map['h']],
                            low= df[ohlc_col_map['l']],
                            close= df[ohlc_col_map['c']])
                        )
        if not show_range_slider:
            fig.update_layout(xaxis_rangeslider_visible=False)

    # indicators to add to the OHLC
    if 'impulse' in df.columns:
        fig = add_impulse_trace(fig, df, ohlc_col_map = ohlc_col_map, date_col = date_col)

    ch_cols = get_channels_col(df.columns)
    if len(ch_cols)> 0:
        fig = add_channel_trace(fig, df, ch_cols = ch_cols, date_col = date_col,
                rgb_tup = (231,107,243) if b_fill_channel else None)

    ma_cols = get_moving_average_col(df.columns)
    if len(ma_cols)> 0:
        for ma in ma_cols:
            fig.add_trace(go.Scatter(x = date_serie, y = df[ma], name = ma),
                    row = 1, col = 1
                    )

    # Check for indicators for subplots
    ref_row = 2 if vol_col else 1
    for c in auto_subplot_col:
        if c in df.columns:
            ref_row += 1
            if c == 'RSI':
                fig.append_trace(go.Scatter(x = date_serie, y = df['RSI'], name = 'RSI'),
                    row = ref_row, col = 1)
                fig.add_hline(y = tup_rsi_hilo[1], line_dash = 'dot',
                    row = ref_row, col = 1)
                fig.add_hline(y = tup_rsi_hilo[0], line_dash = 'dot',
                    row = ref_row, col = 1)
            elif c == 'ADX':
                fig = add_ADX_trace(fig, df, ref_row = ref_row, date_col = date_col)
            elif c == 'MACD_histogram':
                fig = add_MACD_trace(fig, df, ref_row = ref_row, date_col = date_col, draw_signal_line = False)
            elif c == 'MACD':
                fig = add_MACD_trace(fig, df, ref_row = ref_row, date_col = date_col, draw_signal_line = True)
            else: # very simple scatter plot
                fig.append_trace(go.Scatter(x = date_serie, y = df[c], name = c),
                    row = ref_row, col = 1)

    #TODO: hide range outside trading hours: https://stackoverflow.com/a/65632833/14285096
    return fig
