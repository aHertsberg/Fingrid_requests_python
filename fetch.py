import json
from datetime import datetime, timedelta
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cfg


print(cfg.API_key)
API_key = cfg.API_key

headers = {'x-api-key':API_key, 'Accept':'application/json'}
var_IDs = [198,]
var_IDs = map(str, var_IDs)
payload = {'start_time':'2018-07-18T08:00:00+0300', 'end_time':'2018-07-18T12:00:00+0300'}
url = 'https://api.fingrid.fi/v1/variable/{}/events/json'

frequencies = []
timestamps = []
for var in var_IDs:
    r = requests.get(url.format(var), headers=headers, params=payload)
    for e in r.json():
        print(e)

        frequencies.append(float(e['value']))
        timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))

plt.figure()
plt.plot(timestamps, frequencies)
plt.grid(b=True)
plt.savefig('figurename.png')
