import requests

from pprint import pprint

response = requests.get('https://www.swapi.tech/api/starships/9/')
pprint(response.json()) 