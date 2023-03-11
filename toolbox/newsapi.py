# account: jho.yvr+newsapi@gmail.com
api_key = '94728df306c14086ad303cc26ddf3eab'
import requests, json

base_url = 'https://newsapi.org/v2/'
params_ini = {
    'apiKey': api_key
}

def GetJson(url, params):
    data = requests.get(url, params = params)
    if data.status_code == 200:
        return json.loads(data.text)
    else:
        return None

def getheadlines( query_params, bVerbose = False):
    url = base_url + 'top-headlines?'
    query_params['apiKey'] = api_key
    if bVerbose:
        print(f'Query endpoint: {url} with these params \n {query_params}')
    return GetJson(url, query_params)

def get_headlines_sources(query_params, bVerbose = False):
    url = base_url + 'top-headlines/sources?'
    query_params['apiKey'] = api_key
    if bVerbose:
        print(f'Query endpoint: {url} with these params \n {query_params}')
    return GetJson(url, query_params)

def getSearch( search_term , optdict = None):
    url = base_url + 'everything?'
    params = params_ini
    params['q'] = search_term
    if optdict != None:
        for key in optdict:
            params[key]= optdict[key]

    print(f'Searching for {search_term} with these params \n{params}')

    return GetJson(url, params)

def printResults( json_data):
    if json_data is None:
        print("Can't load headlines")
    else:
        print("Getting you headlines from NewsAPI.org!!!\n\n")
        for i in json_data['articles']:
            pdata = [i['source']['name'], i['title'], i['url'], i['publishedAt']]
            print(" | ".join(pdata) + "\n")
        print("\n\n---End of Headlines---\n")

def printHeadlines(country = None):
    params_dict = {
        'q': 'special dividend',
        'pageSize': 10
    }
    if country != None:
        params_dict['country'] = country
    data = getheadlines(params_dict)
    printResults(data)

def printSearch( q ):
    params_dict = {
        'pageSize': 10,
        'sortBy': 'publishedAt'
    }
    data = getSearch( q, params_dict)
    printResults(data)

printHeadlines()
printSearch('+"special dividend"')
