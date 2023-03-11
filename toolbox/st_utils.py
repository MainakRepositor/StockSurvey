import os, sys, json, datetime
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from businessdate import BusinessDate
import streamlit_pydantic as sp

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.data_utils import is_json

def st_write_dict(data):
    for k, v in data.items():
        st.subheader(k)
        st.write(v)

def show_logo(st_asset = st.sidebar, use_column_width = False, width = 100, str_color = "gold"):
    logo_url = f'asset/app_logo_{str_color}.png'
    _, ccol, _ = st_asset.columns(3)
    ccol.image(logo_url, width = width, use_column_width = use_column_width)

def show_plotly(fig, height = None, title = None, template = 'plotly_dark', st_asset = st):
    params = {'height': height, 'title': title, 'template': template}
    params = {k:v for k,v in params.items() if v}

    fig.update_layout(params)
    st_asset.plotly_chart(fig, use_container_width = True, height = height)

def plotly_hist_draw_hline(fig, l_value_format):
    '''
    added a horizontial line in place
    Args:
        l_value_format: list of dictionary of the shape
            {value: 123, line_format: Optional[{'color': '#b58900', 'dash': 'dot', 'width': 1}]}

    ref: https://github.com/plotly/plotly_express/issues/143
    a simpler method here: https://plotly.com/python/horizontal-vertical-shapes/
    '''
    default_line_format = {'color': 'light grey', 'dash': 'dot', 'width': 1}
    l_shapes = []
    for shape in l_value_format:
        shape_dict = {'type': 'line',
                'yref': 'y', 'y0': shape['value'], 'y1': shape['value'],
                'xref': 'paper', 'x0': 0, 'x1': 1,
                'line': shape['line_format'] if 'line_format' in shape.keys() else default_line_format
            }
        # if line_format_params:
        #     shape_dict['line'] = line_format_params
        l_shapes.append(shape_dict)

    fig.update_layout(
        shapes = l_shapes
        )

def get_timeframe_params(st_asset , data_buffer_tenor = '1y', default_tenor = '250b',
        l_interval_options = ['1d','1m', '2m','5m','15m','30m','60m','90m','1h','5d','1wk','1mo','3mo']
    ):
    ''' get user inputs and return timeframe params in dictionary {'start_date':..., 'end_date':..., 'data_start_date':...,'interval':...,'tenor':...}
    '''
    with st_asset:
        today = datetime.date.today()
        end_date = st.date_input('Period End Date', value = today)
        tenor = None
        if st.checkbox('pick start date'):
            start_date = st.date_input('Period Start Date', value = today - datetime.timedelta(days = 365))
        else:
            tenor = st.text_input('Period', value = default_tenor)
            start_date = (BusinessDate(end_date) - tenor).to_date()
            st.info(f'period start date: {start_date}')
        data_start_date = (BusinessDate(start_date) - data_buffer_tenor).to_date()
        interval = st.selectbox('interval', options = l_interval_options)

    return {
        'start_date': start_date, 'end_date': end_date,
        'data_start_date': data_start_date, 'interval': interval,
        'tenor': tenor
    }

def get_json_edit(in_json, str_msg = 'Please edit your JSON object', text_area_height = 500,
	json_dumps_kargs = {'indent': 4, 'sort_keys': True}):
	out_json = st.text_area(
		str_msg, height = text_area_height,
		value = json.dumps(in_json, **json_dumps_kargs)
	)
	return json.loads(out_json) if is_json(out_json) else None

def get_sp_data(form_key, data_model, st_asset, submit_label = 'Submit',
    do_cache = False, **kwargs):
    ''' Create a form in ST using streamlit_pydantic and
        return the resulting data object in dictionary form
    '''
    if do_cache:
        cache_key = f'{form_key}_cache'
        with st_asset.form(key = form_key):
            st.markdown(f'#### {form_key} params')
            input_data = sp.pydantic_input(key = form_key,  model = data_model, **kwargs)
            submitted = st.form_submit_button(label = submit_label if submit_label else 'Submit')
        if submitted:
            data = input_data
            st.session_state[cache_key] = data
        else:
            data = st.session_state[cache_key] if cache_key in st.session_state else None
    else:
        with st_asset:
            data = sp.pydantic_form(key = form_key, model = data_model,
                    submit_label = submit_label, **kwargs)
    return data

def add_clear_cache_button(st_asset):
    if st_asset.button('Clear cached results'):
        st.legacy_caching.clear_cache()
        st_asset.success("Cleared Cached Results")
