import streamlit as st
import os, sys


from apps.stock_desc import Main as Desc
from apps.stock_returns import Main as RT
from apps.stock_ta import Main as GP
from apps.stock_ATR import Main as ATR





def Main():
	st.set_page_config(
		layout = 'wide',
		page_title = 'Stocklit',
		page_icon = 'asset/app_logo_gold.png',
		initial_sidebar_state = 'expanded'
		)
	
	app_dict = {
		"DESC": Desc,
		"GP": GP,
		"RT": RT,
		"ATR": ATR
		}

	app_sw = st.sidebar.selectbox('select app', options = [''] + list(app_dict.keys()))
	if app_sw:
		app_func = app_dict[app_sw]
		app_func()

if __name__ == '__main__':
	Main()
