import requests
import hashlib
import hmac
import time

# Your API Key and Secret, read from binance_credentials.txt
with open('binance_credentials.txt') as f:
    API_KEY = f.readline().strip()
    API_SECRET = f.readline().strip()

# Endpoint URL
base_url = 'http://54.248.0.145:62299'
endpoint = '/api/v3/allOrders'

# Parameters
symbol = 'BTCUSDT'
timestamp = int(time.time() * 1000)
params = f'symbol={symbol}&timestamp={timestamp}'

# Signature
signature = hmac.new(API_SECRET.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

# Complete URL
url = f"{base_url}{endpoint}?{params}&signature={signature}"

# Headers
headers = {
    'X-MBX-APIKEY': API_KEY
}

# Make the request
response = requests.get(url, headers=headers, verify=False)

# Parse the response
if response.status_code == 200:
    orders = response.json()
    print("Orders:", orders)
else:
    print("Error:", response.content)
