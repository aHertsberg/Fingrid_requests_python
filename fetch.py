import json
from datetime import datetime, timedelta
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import cfg


API_key = cfg.API_key
production = cfg.production
production_types = list(production.keys())
production_types.sort()
transfer = cfg.transfer
bidding_areas = list(transfer.keys())
bidding_areas.sort()

url = 'https://api.fingrid.fi/v1/variable/{}/events/json'
headers = {'x-api-key':API_key, 'Accept':'application/json'}

end = datetime.now()
start = end - timedelta(days=1)

# assumes UTC+3
payload = {'start_time':'{}:00+0300'.format(datetime.strftime(start, '%Y-%m-%dT%H:%M')), 'end_time':'{}:00+0300'.format(datetime.strftime(end, '%Y-%m-%dT%H:%M'))}

plt.figure('production', dpi=100, figsize=(16,8))

for prod_type in production_types:
    if 'Total power production' in prod_type:
        ax = plt.subplot(212)
    else:
        ax = plt.subplot(211)
    values = []
    timestamps = []
    r = requests.get(url.format(production[prod_type]), headers=headers, params=payload)
    for e in r.json():
        values.append(float(e['value']))
        timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))

    ax.plot(timestamps, values, label=prod_type)


ax = plt.subplot(211)
ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.20), ncol=4, fancybox=True)
ax.grid(b=True)
ax.fmt_xdata = mdates.DateFormatter('%H:%M')

ax = plt.subplot(212)
ax.grid(b=True)
plt.title('Total power production in Finland')
plt.savefig('Production.png')


plt.figure('transfer', dpi=100, figsize=(16,8))
for bidding_area in bidding_areas:
    ax = plt.subplot(111)
    values = []
    timestamps = []
    r = requests.get(url.format(transfer[bidding_area]), headers=headers, params=payload)
    for e in r.json():
        values.append(float(e['value']))
        timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))

    ax.plot(timestamps, values, label=bidding_area)

ax.legend(loc='upper center', bbox_to_anchor=(.2, 1.05), ncol=3, fancybox=True)
ax.grid(b=True)
ax.fmt_xdata = mdates.DateFormatter('%H:%M')
plt.title('Transfer from Finland')
plt.savefig('Transfer.png')
