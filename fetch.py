import argparse
import cfg
import time
import json
from datetime import datetime, timedelta
import urllib.request
import math

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

parser = argparse.ArgumentParser()

parser.add_argument("-i", "--inertia", action="store_true", help="Boolean for inertia plot")
parser.add_argument("-e", "--end", help="End date, default now")
parser.add_argument("-d", "--days", help="Set duration in days")
parser.add_argument("-p", "--prices", action="store_true", help="Boolean for including price chart, can make queries slow (1 day with 15 minute data is ~15 seconds)")

args = parser.parse_args()

API_key = cfg.API_key
production = cfg.production
production_types = list(production.keys())
production_types.sort()
transfer = cfg.transfer
bidding_areas = list(transfer.keys())
bidding_areas.sort()

headers = {'x-api-key':API_key}

def query_multiple_tags(tag_dict, start, end, page=1, last_page=None):
    tags = tag_dict.keys()
    ids = [tag_dict[tag] for tag in tags]
    data = {}
    for tag in ids:
        data[tag] = [[],[]]
    base_url = 'https://data.fingrid.fi/api/data?datasets={}&startTime={}&endTime={}&pageSize=10000&page={}'
    request_url = base_url.format(','.join(ids), start, end, page)
    req = urllib.request.Request(request_url, headers=headers)

    req.get_method = lambda: 'GET'
    r = urllib.request.urlopen(req)
    response_code = r.getcode()
    if response_code != 200:
        print(f"Fetching \"{base_url}\" returned status code {response_code}")
        return
    response = r.read()
    response = json.loads(response.decode('utf-8'))
    for row in response["data"]:
        data[str(row["datasetId"])][0].append(datetime.strptime(row["startTime"], "%Y-%m-%dT%H:%M:%S.000Z"))
        data[str(row["datasetId"])][1].append(row["value"])

    if not last_page: last_page = response['pagination']['lastPage']

    if page != last_page:
        # Avoiding rate limit error 429
        time.sleep(2.1)
        to_join = query_multiple_tags(tag_dict, start, end, page=page+1, last_page=last_page)
        for key in to_join.keys():
            # Assumes that all tags are retreived on the first page and thus exist in the dict
            data[key][0] = data[key][0] + to_join[key][0]
            data[key][1] = data[key][1] + to_join[key][1]

    return data

def collect_prices(t_start, t_end):
    prices = [[], []]
    t = t_start
    # Market pricing in Finland changed to 15 min on 2025-10-01T01:00:00 local
    t_15_min_pricing = datetime.strptime("2025-09-30T23:00", "%Y-%m-%dT%H:%M")
    hours = 0
    quarters = 0
    if t < t_15_min_pricing:
        t = t - timedelta(t.minute*60 + t.second)
        hour_span = min(t_end, t_15_min_pricing) - t
        hours = hour_span.days*24 + math.ceil(hour_span.seconds/3600)
    else:
        t = t - timedelta(t.minute%15*60 + t.second)
    if t_end > t_15_min_pricing:
        quarter_span = t_end - max(t, t_15_min_pricing)
        quarters = quarter_span.days*24*4 + math.ceil(quarter_span.seconds/900)
    total_fetches = quarters + hours
    fetches = 0
    
    dt = timedelta(seconds=3600)
    url = "https://api.porssisahko.net/v2/price.json?date={}"
    for i in range(hours):
        date_string = datetime.strftime(t, "%Y-%m-%dT%H:%M:00.000Z")
        price = query_price(url.format(date_string))
        prices[0].append(t)
        prices[1].append(price)
        t = t + dt
        fetches += 1
        if fetches%8 == 0: print(f"Prices fetched: {fetches}/{total_fetches}")
    if quarters > 0:
        dt = timedelta(seconds=900)
        for i in range(quarters):
            date_string = datetime.strftime(t, "%Y-%m-%dT%H:%M:00.000Z")
            price = query_price(url.format(date_string))
            prices[0].append(t)
            prices[1].append(price)
            t = t + dt
            fetches += 1
            if fetches%8 == 0: print(f"Prices fetched: {fetches}/{total_fetches}")

    # Ugly hack to make the step plot render the last step.
    # Not as much of a problem with the 3 min data
    prices[0].append(prices[0][-1] + dt)
    prices[1].append(prices[1][-1])

    # The prices returned include VAT and are in c/kWh
    prices[1] = np.array(prices[1])/1.255
    prices[1] = prices[1]*10

    return prices


def query_price(url):
    req = urllib.request.Request(url)
    req.get_method = lambda: 'GET'
    r = urllib.request.urlopen(req)
    response_code = r.getcode()
    if response_code != 200:
       print(f"Fetching \"{url}\" returned status code {response_code}") 
       return
    response = r.read()
    response = json.loads(response.decode('utf-8'))
    return response["price"]


def align_yticks(ticks_a, ticks_b):
    delta_a = ticks_a[1] - ticks_a[0]
    delta_b = ticks_b[1] - ticks_b[0]
    array_a = np.array(ticks_a)
    array_b = np.array(ticks_b)
    a_positive = array_a[array_a > 0]
    b_positive = array_b[array_b > 0]
    a_negative = array_a[array_a < 0]
    b_negative = array_b[array_b < 0]

    if len(a_positive) < len(b_positive):
        for i in range(len(b_positive) - len(a_positive)):
            ticks_a.append(ticks_a[-1] + delta_a)
    elif len(a_positive) > len(b_positive):
        for i in range(len(a_positive) - len(b_positive)):
            ticks_b.append(ticks_b[-1] + delta_b)

    if len(a_negative) < len(b_negative):
        for i in range(len(b_negative) - len(a_negative)):
            ticks_a = [ticks_a[0] - delta_a] + ticks_a
    elif len(a_negative) > len(b_negative):
        for i in range(len(a_negative) - len(b_negative)):
            ticks_b = [ticks_b[0] - delta_b] + ticks_b

    if len(ticks_a) >= 12:
        zero_index = ticks_a.index(0)
        ticks_a = ticks_a[zero_index%2::2]
        ticks_b = ticks_b[zero_index%2::2]

    return (ticks_a, ticks_b)


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

data = query_multiple_tags(production, start_string, end_string)

fig = plt.figure('production', dpi=100, figsize=(16,24))
prod_dict = {}
total_power = 0
ax_1 = plt.subplot(411)
ax_2 = plt.subplot(412)

for prod_type in production_types:
    prod_id = production[prod_type]
    if 'Total power' in prod_type:
        ax = ax_1
    else:
        ax = ax_2
    timestamps = data[prod_id][0]
    values = data[prod_id][1]

    if 'Total power' in prod_type:
        prod_type = prod_type.split()[2]
        prod_type.capitalize()
        if 'production' in prod_type:
            resolution = timedelta(minutes=3)
            total_power = round(sum(values)*resolution.seconds/3600/1000, 2)
    elif prod_type == 'Solar, forecasted':
        # Unfortunately solar is only forecasted at 1 h granularity, so for now 
        # it will be to be treated separately.
        resolution = timedelta(minutes=60)
        E = round(sum(values)*resolution.seconds/3600/1000, 2)
        # Removing extrapolated future production
        if timestamps[-1] > t_now - resolution:
            E -= values[-1]*(1 - (t_now-timestamps[-1])/resolution)
        prod_dict[prod_type] = E
        # preferential treatment, but I can't resist. Perhaps hydro should get 
        # be assigned the colour blue :thinking:
        ax.step(timestamps, values, where='post', label=prod_type, c='xkcd:goldenrod')
        continue
    else:
        # Apparently Fingrid's start and end times are the same if queried with 
        # native resolution.
        resolution = timedelta(minutes=3)
        # GWh for readability
        E = round(sum(values)*resolution.seconds/3600/1000, 2)
        prod_dict[prod_type] = E

    if prod_type != 'Solar, forecasted':
        ax.step(timestamps, values, label=prod_type, where="post")

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
ax.set_ylabel("[MW]")

ax = ax_2
ax.set_facecolor('xkcd:powder blue')
ax.set_xlim((start, min(end, datetime.utcnow())))
bottom, top = ax.get_ylim()
ax.set_ylim(bottom, top+500)
ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.15), ncol=3, fancybox=True)
ax.grid()
ax.set_ylabel("[MW]")
ax.fmt_xdata = mdates.DateFormatter('%H:%M')


ax_3 = plt.subplot(413)
ax = ax_3
time.sleep(2) # Might otherwise hit the rate limit from the previous queries
data = query_multiple_tags(transfer, start_string, end_string)
for bidding_area in bidding_areas:
    area_id = transfer[bidding_area]
    timestamps = data[area_id][0]
    values = data[area_id][1]

    ax.step(timestamps, values, label=bidding_area, where="post")

ax.set_facecolor('xkcd:powder blue')
plt.title('Transfer to Finland')
ax.set_xlim((start, min(end, datetime.utcnow())))
ax.legend(loc='upper center', bbox_to_anchor=(.2, 1.20), ncol=3, fancybox=True)
ax.grid()
ax.set_ylabel("[MW]")
ax.fmt_xdata = mdates.DateFormatter('%H:%M')

ax_4 = plt.subplot(414)
ax = ax_4
time.sleep(2)
curiosity = cfg.curiosity
data = query_multiple_tags(curiosity, start_string, end_string)
for tag in curiosity.keys():
    tag_id = curiosity[tag]
    timestamps = data[tag_id][0]
    values = data[tag_id][1]
    if tag_id == '398':
        values = np.array(values)*-1

    ax.step(timestamps, values, label=tag, where="post")


if args.prices:
    prices = collect_prices(start, end)
    ax_prices = ax_4.twinx()
    ax_prices.step(prices[0], prices[1], c='k', label='Electricity wholesale price', where="post")
    ax_prices.set_ylabel("[eur/MWh]")

    # Tick alignment
    ylim = ax.get_ylim()
    ax.set_ylim([min(0, min(ylim)), max(0, max(ylim))])
    power_ticks = ax.get_yticks()

    ylim = ax_prices.get_ylim()
    ax_prices.set_ylim([min(0, min(ylim)), max(0, max(ylim))])
    price_ticks = ax_prices.get_yticks()

    power_ticks, price_ticks = align_yticks(list(power_ticks), list(price_ticks))
    ax.set_yticks(power_ticks)
    ax_prices.set_yticks(price_ticks)


ax.set_facecolor('xkcd:powder blue')
plt.title('Some separated producers and consumers')
ax.set_xlim((start, min(end, datetime.utcnow())))
ax.legend(loc='upper center', bbox_to_anchor=(.2, 1.25), ncol=1, fancybox=True)
ax.grid()
ax.set_ylabel("[MW]")
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
        # todo switch to urllib
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
        plt.step(timestamps, values, label=param)

    plt.legend(fancybox=True)
    plt.grid(b=True)
    plt.fmt_xdata = mdates.DateFormatter('%H:%M')
    plt.title('Inertial information of the Nordic grid')
    plt.savefig('Inertia_{}.png'.format(datetime.strftime(end, '%Y%m%d')))








