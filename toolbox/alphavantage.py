import os, sys, json, requests

def TickerSearch(keywords, api_key):
    url = f'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={keywords}&apikey={api_key}'
    r = requests.get(url)
    data = r.json()
    return data
