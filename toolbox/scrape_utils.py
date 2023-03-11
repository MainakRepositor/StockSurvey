import os, sys, time
from tqdm import tqdm

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.data_utils import JsonReader, timed_lru_cache

def get_proxy(debug_mode = False):
    ''' return a random proxy from pubproxy.com (max 2 requests/sec, 30 per day)
    '''
    try:
        results = JsonReader("http://pubproxy.com/api/proxy")
        proxy = f'{results["data"][0]["type"]}://{results["data"][0]["ipPort"]}'
        if debug_mode:
            print(f'found proxy: {proxy}')
        return proxy
    except:
        return None

@timed_lru_cache(seconds = 24*60**2) # cache for 24-hours
def get_proxies(n=10, seconds_delay = 1):
    proxies = []
    for i in tqdm(range(n), desc = 'getting proxies'):
        p = get_proxy()
        proxies.append(p)
        time.sleep(seconds_delay)
    proxies = [p for p in proxies if p]
    print(f'got {len(proxies)} of {n} requested proxies')
    return proxies

def update_session_proxy(session, proxy):
    type, address = proxy.split('://')
    session.proxies = {type: address}
    return session
