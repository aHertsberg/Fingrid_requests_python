import json
from datetime import datetime, timedelta
import requests
import matplotlib
import numpy as np
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import cfg
import sys
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("-i", "--inertia", help="Boolean for inertia plot")
parser.add_argument("-e", "--end", help="End date, default now")
parser.add_argument("-d", "--days", help="Set duration in days")

args = parser.parse_args()

API_key = cfg.API_key
production = cfg.production
production_types = list(production.keys())
production_types.sort()
transfer = cfg.transfer
bidding_areas = list(transfer.keys())
bidding_areas.sort()

url = 'https://api.fingrid.fi/v1/variable/{}/events/json'
headers = {'x-api-key':API_key, 'Accept':'application/json'}

if args.end:
    end = datetime.strptime(args.end, '%Y-%m-%d')
else:
    end = datetime.now()

if args.days:
    start = end - timedelta(days=int(args.days))
else:
    start = end - timedelta(days=3)

# assumes UTC+3
payload = {'start_time':'{}:00+0300'.format(datetime.strftime(start, '%Y-%m-%dT%H:%M')), 'end_time':'{}:00+0300'.format(datetime.strftime(end, '%Y-%m-%dT%H:%M'))}

fig = plt.figure('production', dpi=100, figsize=(16,16))
prod_dict = {}

total_power = 0
ax_1 = plt.subplot(311)
ax_2 = plt.subplot(312)
for prod_type in production_types:
    if 'Total power' in prod_type:
        ax = ax_1
    else:
        ax = ax_2
    values = []
    timestamps = []
    r = requests.get(url.format(production[prod_type]), headers=headers, params=payload)
    for e in r.json():
        values.append(float(e['value']))
        timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))


    if 'Total power' in prod_type:
        prod_type = prod_type.split()[2]
        prod_type.capitalize()
    else:
        #Apparently Fingrid's start and end times are the same if queried with native resolution
        resolution = timedelta(minutes=3)
        # GWh for readability
        E = round(sum(values)*resolution.seconds/3600/1000, 2)
        prod_dict[prod_type] = E
        total_power += E

    ax.plot(timestamps, values, label=prod_type)

print('Absolute production GWh:')
print(prod_dict)
ratio_dict = {}
for key in prod_dict.keys():
    ratio_dict[key] = round(prod_dict[key]/total_power*100, 1)
print('Percentage of total power produced in Finland')
print(ratio_dict)

ax = ax_1
ax.grid(b=True)
plt.title('Total power consumption and production in Finland')
plt.legend(loc='upper center', bbox_to_anchor=(.2, 1.00), ncol=2, fancybox=True)

ax = ax_2
bottom, top = ax.get_ylim()
ax.set_ylim(bottom, top+500)
ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.20), ncol=4, fancybox=True)
ax.grid(b=True)
ax.fmt_xdata = mdates.DateFormatter('%H:%M')


ax_3 = plt.subplot(313)
for bidding_area in bidding_areas:
    ax = ax_3
    values = []
    timestamps = []
    r = requests.get(url.format(transfer[bidding_area]), headers=headers, params=payload)
    for e in r.json():
        values.append(float(e['value'])*-1)
        timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))

    ax.plot(timestamps, values, label=bidding_area)

ax.legend(loc='upper center', bbox_to_anchor=(.2, 1.20), ncol=3, fancybox=True)
ax.grid(b=True)
ax.fmt_xdata = mdates.DateFormatter('%H:%M')
plt.title('Transfer to Finland')
fig.subplots_adjust(hspace=.5)
plt.savefig('Production_{}.png'.format(datetime.strftime(end, '%Y%m%d')))

if args.inertia:
    inertia = cfg.inertia
    inertial_params = list(inertia.keys())
    plt.figure('inertia', dpi=100, figsize=(16,8))
    for param in inertial_params:
        values = []
        timestamps = []
        r = requests.get(url.format(inertia[param]), headers=headers, params=payload)

        for e in r.json():
            values.append(float(e['value']))
            timestamps.append(datetime.strptime(e['start_time'], '%Y-%m-%dT%H:%M:%S+0000'))
        if param == 'Grid inertia':
            values = np.array(values)
            # conversion from GWs to MWh
            values = values/3.6
            param += ' [MWh]'
        else:
            param += ' [Hz]'
        plt.plot(timestamps, values, label=param)

    plt.legend(fancybox=True)
    plt.grid(b=True)
    plt.fmt_xdata = mdates.DateFormatter('%H:%M')
    plt.title('Inertial information of the Nordic grid')
    plt.savefig('Inertia_{}.png'.format(datetime.strftime(end, '%Y%m%d')))








