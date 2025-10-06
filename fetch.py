import time
import pdb
import json
from datetime import datetime, timedelta
import urllib.request, json
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

headers = {'x-api-key':API_key}

t_now = datetime.utcnow()
if args.end:
    end = datetime.strptime(args.end, '%Y-%m-%d')
else:
    end = t_now

if args.days:
    start = end - timedelta(days=int(args.days))
else:
    start = end - timedelta(days=3)

start_string = datetime.strftime(start, '%Y-%m-%dT%H:%M')
end_string = datetime.strftime(end, '%Y-%m-%dT%H:%M')
base_url = 'https://data.fingrid.fi/api/datasets/{}/data?startTime={}&endTime={}&pageSize=20000'

fig = plt.figure('production', dpi=100, figsize=(16,16))
prod_dict = {}

total_power = 0
ax_1 = plt.subplot(311)
ax_2 = plt.subplot(312)
for prod_type in production_types:
    print(prod_type)
    if 'Total power' in prod_type:
        ax = ax_1
    else:
        ax = ax_2
    values = []
    timestamps = []
    request_url = base_url.format(production[prod_type], start_string, end_string)
    req = urllib.request.Request(request_url, headers=headers)

    req.get_method = lambda: 'GET'
    response = urllib.request.urlopen(req)
    response_code = response.getcode()
    if response_code != 200:
        print(f"Fetching \"{prod_type}\" returned status code {response_code}")
        time.sleep(2.1)
        continue
    response_data = response.read()
    response_dict = json.loads(response_data.decode('utf-8'))

    for e in response_dict["data"]:
        timestamp = datetime.strptime(e['startTime'], '%Y-%m-%dT%H:%M:%S.000Z')
        if timestamp < t_now:
            values.append(float(e['value']))
            timestamps.append(timestamp)

    if 'Total power' in prod_type:
        prod_type = prod_type.split()[2]
        prod_type.capitalize()
    elif prod_type == 'Solar, forecasted':
        # Unfortunately solar is only forecasted at 1 h granularity, so for now 
        # it will be to be treated separately.
        resolution = timedelta(minutes=60)
        E = round(sum(values)*resolution.seconds/3600/1000, 2)
        # Removing extrapolated future production
        if timestamps[-1] > t_now - resolution:
            E -= values[-1]*(1 - (t_now-timestamps[-1])/resolution)
        prod_dict[prod_type] = E
        total_power += E
        # preferential treatment, but I can't resist. Perhaps hydro should get 
        # be assigned the colour blue :thinking:
        ax.step(timestamps, values, where='post', label=prod_type, c='xkcd:goldenrod')
        time.sleep(2.1)
        continue
    else:
        # Apparently Fingrid's start and end times are the same if queried with 
        # native resolution.
        resolution = timedelta(minutes=3)
        # GWh for readability
        E = round(sum(values)*resolution.seconds/3600/1000, 2)
        prod_dict[prod_type] = E
        total_power += E

    if prod_type != 'Solar, forecasted':
        ax.plot(timestamps, values, label=prod_type)
    time.sleep(2.1)

print('Absolute production GWh:')
print(prod_dict)
ratio_dict = {}
for key in prod_dict.keys():
    ratio_dict[key] = round(prod_dict[key]/total_power*100, 1)
print('Percentage of total power produced in Finland')
print(ratio_dict)

ax = ax_1
ax.set_facecolor('xkcd:powder blue')
ax.set_title('Total power consumption and production in Finland')
ax.set_xlim((start, min(end, datetime.utcnow())))
ax.legend(loc='upper center', bbox_to_anchor=(.15, 1.12), ncol=2, fancybox=True)
ax.grid()

ax = ax_2
ax.set_facecolor('xkcd:powder blue')
ax.set_xlim((start, min(end, datetime.utcnow())))
bottom, top = ax.get_ylim()
ax.set_ylim(bottom, top+500)
ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.15), ncol=3, fancybox=True)
ax.grid()
ax.fmt_xdata = mdates.DateFormatter('%H:%M')


ax_3 = plt.subplot(313)
for bidding_area in bidding_areas:
    ax = ax_3
    values = []
    timestamps = []

    request_url = base_url.format(transfer[bidding_area], start_string, end_string)
    req = urllib.request.Request(request_url, headers=headers)

    req.get_method = lambda: 'GET'
    response = urllib.request.urlopen(req)
    response_code = response.getcode()
    if response_code != 200:
        print(f"Fetching \"{prod_type}\" returned status code {response_code}")
        time.sleep(2.1)
        continue
    response_data = response.read()
    response_dict = json.loads(response_data.decode('utf-8'))

    for e in response_dict["data"]:
        timestamp = datetime.strptime(e['startTime'], '%Y-%m-%dT%H:%M:%S.000Z')
        values.append(float(e['value']))
        timestamps.append(timestamp)

    ax.plot(timestamps, values, label=bidding_area)
    time.sleep(2.1)

ax.set_facecolor('xkcd:powder blue')
plt.title('Transfer to Finland')
ax.set_xlim((start, min(end, datetime.utcnow())))
ax.legend(loc='upper center', bbox_to_anchor=(.2, 1.20), ncol=3, fancybox=True)
ax.grid()
ax.fmt_xdata = mdates.DateFormatter('%H:%M')
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








