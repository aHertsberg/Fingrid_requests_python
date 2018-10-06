import json
from datetime import datetime, timedelta
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import cfg


API_key = cfg.API_key

headers = {'x-api-key':API_key, 'Accept':'application/json'}
variable_dict = cfg.var_IDs
variable_names = variable_dict.keys()
url = 'https://api.fingrid.fi/v1/variable/{}/events/json'

now = datetime.now()
start = now - timedelta(days=1)
payload = {'start_time':'{}:00+0300'.format(datetime.strftime(start, '%Y-%m-%dT%H:%M')), 'end_time':'{}:00+0300'.format(datetime.strftime(now, '%Y-%m-%dT%H:%M'))}

frequencies = []
timestamps = []


plt.figure('production', dpi=100, figsize=(16,8))
for variable in variable_names:
    if 'Total power production' in variable:
        ax = plt.subplot(212)
    else:
        ax = plt.subplot(211)
    values = []
    timestamps = []
    r = requests.get(url.format(variable_dict[variable]), headers=headers, params=payload)
    for e in r.json():
        values.append(float(e['value']))
        timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))

    ax.plot(timestamps, values, label=variable)

ax = plt.subplot(211)
ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.20), ncol=4, fancybox=True)
ax.grid(b=True)
ax.fmt_xdata = mdates.DateFormatter('%H:%M')

ax = plt.subplot(212)
ax.grid(b=True)
plt.title('Power production in Finland')
plt.savefig('Production.png')
