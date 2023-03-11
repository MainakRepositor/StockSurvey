import os, sys, re, requests
import pandas as pd
import numpy as np
import datetime as dt
from openpyxl import load_workbook
from io import BytesIO
from urllib.request import urlopen

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.data_utils import timed_lru_cache, get_floats, str_to_date

@timed_lru_cache(seconds = 8*60**2) # Cache data for 8 hours
def get_hkex_securities_df(xlsx_url = 'https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx',
		convert_stock_code = True):
	'''return a df of HK lot sizes for all HK stocks
	Args:
		xlsx_url: url of the HKEX's list of securities
		convert_stock_code: convert stock code to yfinance tickers
	'''
	print(f'hkex_utils: initializing data from {xlsx_url}')
	wb_file_obj = urlopen(xlsx_url).read()
	wb = load_workbook(filename = BytesIO(wb_file_obj))
	ws = wb['ListOfSecurities']
	ws.delete_rows(0,2)
	data = ws.values
	df = pd.DataFrame(data, columns = next(data)[0:])
	df = df.dropna(how = 'all')
	if convert_stock_code:
		df['Stock Code'] = df['Stock Code'].apply( lambda x : str(int(x)).zfill(4) + '.HK')
	return df

def get_lot_size(ticker, df_sec = get_hkex_securities_df()):
	lot_size = df_sec[df_sec['Stock Code'] == ticker.upper()]['Board Lot']
	if len(lot_size) > 0:
		lot_size = lot_size.tolist()[0]
		# comma handling
		# TODO: the proper way https://www.delftstack.com/howto/python/how-to-convert-string-to-float-or-int/#commas-as-thousand-seperator-in-us-or-uk
		return int(lot_size.replace(',',''))
	else:
		return None

def parse_particular(str_particular,
		fx_dict = {'$':1, 'USD': 7.77, 'RMB': 1.2, 'HKD': 1},
		debug = True
	):
	'''return a number from the Dividend Particular string
	'''
	if 'Div' in str_particular:
		match_patterns = [
			"HKD\s\d*\.{0,1}\d+\s{0,1}(cts|ct)",
			"HKD\s\d*\.{0,1}\d+",
			"USD\s\d*\.{0,1}\d+\s{0,1}(cts|ct)",
			"USD\s\d*\.{0,1}\d+",
			"RMB\s\d*\.{0,1}\d+\s{0,1}(cts|ct)",
			"RMB\s\d*\.{0,1}\d+",
			"\d*\.{0,1}\d+\scts",
			"\$\d*\.{0,1}\d+"
		]

		for p in match_patterns:
			m = re.search(p, str_particular)
			if m:
				m = m.group()
				# Convert ct or cts to decimal
				if ('cts' in m) or ('ct' in m):
					m = m.replace('cts','').replace('cts','')
					m = m.replace(get_floats(m)[0],
							str(get_floats(m, as_float = True)[0]/100)
							)
					# m = m.replace(get_floats(m)[0] + " cts" , str(get_floats(m, as_float = True)[0]/100))

				# apply FX conversion
				for k, v in fx_dict.items():
					if k in m:
						m = get_floats(m, as_float = True)[0] * v
						break
				break
	else:
		m = None
	return m

@timed_lru_cache(seconds = 12*60**2) # Cache data for 12 hours
def scrap_hk_stock_div(ticker, parse_func = parse_particular, ex_date_after = '1/1/2000',
	   	scrap_url = 'http://www.etnet.com.hk/www/eng/stocks/realtime/quote_dividend.php?'
	  ):
	''' return a DF of dividends parse from the scrap_url
	Args:
		parse_func: function to parse the string in the Particular column
		fx_rate: to convert foregin dividend amount to HKD
	'''
	assert '.HK' in ticker.upper(), "HK Stocks only"

	hk_code = int(ticker.upper().replace('.HK',''))
	url = scrap_url + "code=" + str(hk_code)
	html = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}).text
	tables = pd.read_html(html, header = 0)
	df = tables[0]

	if parse_func:
		df['Div'] = df['Particular'].apply(parse_func)

	# df['Ex-date'] = pd.to_datetime(df['Ex-date'],format = "%d/%m/%Y")
	df['Ex-date'] = df['Ex-date'].apply(
						lambda x: dt.datetime.strptime(x, "%d/%m/%Y") \
						if str_to_date(x) else x)
	if ex_date_after:
		keep_cond = df['Ex-date'].apply(lambda x: str_to_date(x)> str_to_date(ex_date_after) if str_to_date(x) else False)
		df = df[keep_cond]
	# reorder columns
	ex_date_col = df['Ex-date']
	div_col = df['Div']
	df = df.drop(columns= ['Ex-date','Div'])
	df.insert(loc = 1, column = 'Ex-date', value = ex_date_col)
	df.insert(loc = 2, column = 'Div', value = div_col)
	return df

@timed_lru_cache(seconds = 8*60**2) # Cache data for 8 hours
def get_hangseng_constituent_df(xls_url = 'https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/other_materials/HSSI_LISTe.xls',
		convert_stock_code = True, debug_mode = False):
	'''return a df of hang seng index constituents
	Args:
		xls_url: url of the hang seng index constituents xls file; see https://www.hsi.com.hk/eng/indexes/all-indexes/sizeindexes
		convert_stock_code: convert stock code to yfinance tickers
	'''
	print(f'hkex_utils: initializing data from {xls_url}')
	df = pd.read_excel(xls_url, sheet_name = 'ConstituentList', header = 3, index_col = 0, usecols = "A:D" )
	df = df.dropna(how = 'any')
	if debug_mode:
		print(f'--- dataframe found:\n{df}')
	if convert_stock_code:
		df['Symbol'] = df['Code'].apply( lambda x : str(int(x)).zfill(4) + '.HK')
	return df
