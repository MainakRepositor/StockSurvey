import os, sys, json
import requests

def iex_get(symbol, endpoint, token, debug_mode = False,
            base_url = 'https://cloud.iexapis.com/stable',
            domain = 'stock', params = None):
    payload = {
        'token': token
    }
    if params:
        for k,v in params.items():
            payload[k] = v

    url = f'{base_url}/{domain}'
    url = f'{url}/{symbol}/{endpoint}' if symbol else url
    r = requests.get(url, params = payload)

    if debug_mode:
        print(f'\nurl: {r.url}')
        print(f'\nheaders:{r.headers}')
        print(f'\nstatus_code: {r.status_code}')
        if r.status_code != requests.codes.ok:
            print(f'\nexception type: {r.raise_for_status()}')

    data = r.json()
    return data

def get_usage(secret_key, quota_type = 'messages'):
    return iex_get(symbol = None, endpoint = None, token= secret_key,
                   domain = f'account/usage/{quota_type}', debug_mode = False)

def get_metadata(secret_key):
    return iex_get(symbol = None, endpoint = None, token= secret_key,
                   domain = f'account/metadata', debug_mode = False)
