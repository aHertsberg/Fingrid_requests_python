import argparse
import cfg
import time
import json
from datetime import datetime, timedelta
import urllib.request
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

parser = argparse.ArgumentParser()

parser.add_argument("--volatiles", action="store_true", help="Boolean for plotting rapidly changing data, such as electricity storage, separately")
parser.add_argument("-e", "--end", help="End date, default now")
parser.add_argument("-d", "--days", help="Set duration in days, default 3")
parser.add_argument("--hours", help="Finer granularity duration added on top of days")
parser.add_argument("-p", "--prices", action="store_true", help="Boolean for including price chart")

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
        print(f"Fetching \"{request_url}\" returned status code {response_code}")
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
    price_index = generate_index(t_start, t_end)
    
    try:
        prices = pd.read_csv("price_data.csv", index_col=0, parse_dates=True)
    except FileNotFoundError:
        print("No cache found")
        prices = pd.DataFrame(columns=['Time','Price'])
        prices = prices.set_index('Time')

    missing_indices = price_index.difference(prices.index.intersection(price_index))
    total_fetches = len(missing_indices)
    fetches = 0
    
    if len(missing_indices) > 0: print(f"Querying missing indices, starting with t={missing_indices[0]}")
    url = "https://api.porssisahko.net/v2/price.json?date={}"
    for index in missing_indices:
        date_string = datetime.strftime(index, "%Y-%m-%dT%H:%M:00.000Z")
        price = query_price(url.format(date_string))
        # The prices returned include VAT and are in c/kWh
        price = round(price/1.255*10, 2)
        prices.loc[index] = [price,]
        fetches += 1
        if fetches%8 == 0: print(f"Prices fetched: {fetches}/{total_fetches}")
    prices = prices.sort_index()
    if len(missing_indices) > 0 : prices.to_csv("price_data.csv")
    # Ugly hack to make the step plot render the last step.
    # Not as much of a problem with the 3 min data
    last = prices.index[-1]
    dt = last - prices.index[-2]
    prices.loc[last + dt] = prices.loc[last]

    return prices

def generate_index(start, end):
    index = []
    # Market pricing in Finland changed to 15 min on 2025-10-01T01:00:00 local
    t_15_min_pricing = datetime.strptime("2025-09-30T23:00", "%Y-%m-%dT%H:%M")
    hours = 0
    quarters = 0
    t = start
    if t < t_15_min_pricing:
        t = t - timedelta(seconds=t.minute*60 + t.second)
        hour_span = min(end, t_15_min_pricing) - t
        hours = hour_span.days*24 + math.ceil(hour_span.seconds/3600)
    else:
        t = t - timedelta(seconds=t.minute%15*60 + t.second)
    if end > t_15_min_pricing:
        quarter_span = end - max(t, t_15_min_pricing)
        quarters = quarter_span.days*24*4 + math.ceil(quarter_span.seconds/900)

    dt = timedelta(seconds=3600)
    for i in range(hours):
        index.append(t)
        t = t + dt

    if quarters > 0:
        dt = timedelta(seconds=900)
        for i in range(quarters):
            index.append(t)
            t = t+dt
    return pd.Index(index)
   


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


t_now = pd.Timestamp("now")
if args.end:
    end = pd.Timestamp(args.end)
else:
    end = t_now

if args.days:
    start = end - timedelta(days=int(args.days))
    start = start.floor(freq='d')
else:
    start = end - timedelta(days=3)
    start = start.floor(freq='d')

if args.hours:
    start = start + timedelta(seconds=int(args.hours)*3600)

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
ax.legend(loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=2, fancybox=True)
ax.grid()
ax.set_ylabel("[MW]")

ax = ax_2
ax.set_facecolor('xkcd:powder blue')
ax.set_xlim((start, min(end, datetime.utcnow())))
bottom, top = ax.get_ylim()
ax.set_ylim(bottom, top+500)
ax.legend(loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=3, fancybox=True)
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
plt.title('Transfer from Finland')
ax.set_xlim((start, min(end, datetime.utcnow())))
ax.legend(loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=3, fancybox=True)
ax.grid()
ax.set_ylabel("[MW]")
ax.fmt_xdata = mdates.DateFormatter('%H:%M')

ax_4 = plt.subplot(414)
ax = ax_4
time.sleep(2)
dh = cfg.district_heating
data = query_multiple_tags(dh, start_string, end_string)
for tag in dh.keys():
    tag_id = dh[tag]
    timestamps = data[tag_id][0]
    values = data[tag_id][1]
    ax.step(timestamps, values, label=tag, where="post")


if args.prices:
    prices = collect_prices(start, end)
    ax_prices = ax_4.twinx()
    ax_prices.step(prices.index, prices['Price'], c='k', label='Electricity wholesale price', where="post")
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

    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax_prices.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=1, fancybox=True)

else: ax.legend(loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=1, fancybox=True)

ax.set_facecolor('xkcd:powder blue')
plt.title('District heating boilers and electricity price')
ax.set_xlim((start, min(end, datetime.utcnow())))
ax.grid()
ax.set_ylabel("[MW]")
ax.fmt_xdata = mdates.DateFormatter('%H:%M')
fig.subplots_adjust(hspace=.5)

plt.savefig('Production_{}.png'.format(datetime.strftime(end, '%Y%m%d')))


fig = plt.figure('frequency', dpi=100, figsize=(16,18))
if args.volatiles:

    ax_1 = plt.subplot(313)
    time.sleep(2)
    storage = cfg.storage
    data = query_multiple_tags(storage, start_string, end_string)

    for tag in storage.keys():
        tag_id = storage[tag]
        timestamps = data[tag_id][0]
        values = data[tag_id][1]
        if tag_id == '398':
            values = np.array(values)*-1
        ax_1.step(timestamps, values, label=tag, where="post")

    ax_1.legend(loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=1, fancybox=True)
    ax_1.set_facecolor('xkcd:powder blue')
    plt.title('Storage loads in Finland')
    ax_1.set_xlim((start, min(end, datetime.utcnow())))
    ax_1.grid()
    ax_1.set_ylabel("[MW]")
    ax_1.fmt_xdata = mdates.DateFormatter('%H:%M')
    fig.subplots_adjust(hspace=.5)


    ax_2 = plt.subplot(311)
    time.sleep(2)
    inertia = cfg.inertia
    data = query_multiple_tags(inertia, start_string, end_string)

    for tag in inertia.keys():
        tag_id = inertia[tag]
        timestamps = data[tag_id][0]
        if tag_id == '260':
            values = np.array(data[tag_id][1])/3.6 # conversion from GWs to MWh
            ax_2.step(timestamps, values, label=tag, where="post")
        else:
            values = data[tag_id][1]
            ax_freq = ax_2.twinx()
            ax_freq.step(timestamps, values, label=tag, c='k', where="post")
            ax_freq.set_ylabel("[Hz]")

            # Tick alignment
            ylim = ax_2.get_ylim()
            inertia_ticks = ax_2.get_yticks()

            ylim = ax_freq.get_ylim()
            freq_ticks = ax_freq.get_yticks()

            inertia_ticks, freq_ticks = align_yticks(list(inertia_ticks), list(freq_ticks))
            ax_2.set_yticks(inertia_ticks)
            ax_freq.set_yticks(freq_ticks)

            lines, labels = ax_2.get_legend_handles_labels()
            lines2, labels2 = ax_freq.get_legend_handles_labels()
            ax_2.legend(lines + lines2, labels + labels2, loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=2, fancybox=True)



    ax_2.set_facecolor('xkcd:powder blue')
    plt.title('Inertia and frequency information of the Nordic grid')
    ax_2.set_xlim((start, min(end, datetime.utcnow())))
    ax_2.grid()
    ax_2.set_ylabel("[MWh]")
    ax_2.fmt_xdata = mdates.DateFormatter('%H:%M')
    fig.subplots_adjust(hspace=.5)

    ax_3 = plt.subplot(312)
    time.sleep(2)
    afrr = cfg.afrr
    data = query_multiple_tags(afrr, start_string, end_string)

    for tag in afrr.keys():
        tag_id = afrr[tag]
        timestamps = data[tag_id][0]
        values = data[tag_id][1]
        ax_3.step(timestamps, values, label=tag, where="post")

    ax_3.legend(loc='lower left', bbox_to_anchor=(.025, 1.0), ncol=2, fancybox=True)
    ax_3.set_facecolor('xkcd:powder blue')
    plt.title('Storage load')
    ax_3.set_xlim((start, min(end, datetime.utcnow())))
    ax_3.grid()
    ax_3.set_ylabel("[€/MWh]")
    plt.title('aFRR marginal prices')
    ax_3.fmt_xdata = mdates.DateFormatter('%H:%M')
    fig.subplots_adjust(hspace=.5)
    plt.savefig('Frequency_{}.png'.format(datetime.strftime(end, '%Y%m%d')))


