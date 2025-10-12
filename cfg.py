import os
API_key = os.environ['FINGRID_API_KEY']

production = {'Total power production in Finland':'192', \
        'Combined heat and power':'201', 'Nuclear': '188', 'Wind':'181', \
        'Hydro':'191', 'Other':'205', 'Industrial CHP':'202', \
        'Total power consumption in Finland':'193', 'Solar, forecasted':'248'}


transfer = {'AX-SE3':'90', 'EE':'180', 'NO':'187', 'RUS':'195', \
        'SE1':'87', 'SE3':'89'}

inertia = {'Grid inertia':'260', 'Grid frequency':'177'}

district_heating = {'Electric district heating boilers': '371'}

storage = {'Electricity storage: discharging':'398', \
             'Electricity storage: charging':'399'}
