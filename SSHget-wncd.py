# SSHget-wncd.py
# Version: 3
# Enhanced with major refactor - made more modular, retrieving credentials
#   from optionsconfig.yaml and collect site tags from WLC

#from asyncio.windows_events import NULL
from fabric import Connection
import re
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import sys, os
import threading
import time
import schedule
import sendWebexMessage
import ReadEnvironmentVars


def get_wncd_stats(wlc_params):
    command = 'show process cpu platform sorted | incl Pid|wncd'

    result = Connection(f'{wlc_params["username"]}@{wlc_params["host"]}',connect_kwargs={"password": wlc_params["password"]}).run(command, hide=True)
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'\s\d+\s+\d+\s+(\d+)%\s+(\d+)%\s+(\d+)%\s+.\s+\d+\s+(\S+)'
    #proclist = re.findall(regexstr, msg.format(result), re.S | re.M)
    proclist = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(proclist)

    wncdtags = []
    for wncd_instance in range(8):
        command2 = f'show wireless loadbalance tag affinity wncd {str(wncd_instance)}'
        result = Connection(f'{wlc_params["username"]}@{wlc_params["host"]}',connect_kwargs={"password": wlc_params["password"]}).run(command2, hide=True)
        msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
        #print(repr(msg.format(result)))
        regexstr = r'----[\r\n]+(\S+)\s.*?(\d+)'
        wncdtag = re.search(regexstr, msg.format(result), re.S | re.M)
        if wncdtag == None:
            #print(wncdtags)
            wncdtags.append((wncd_instance, None, 0))
        else:
            #print(wncdtag.group(1), wncdtag.group(2))
            wncdtags.append((wncd_instance, wncdtag.group(1), int(wncdtag.group(2))))
    #print(wncdtags)

    newproclist = []
    for wncdtuple in proclist:
        #print(wncdtuple)
        #print(wncdtuple[3])
        tagtuple = [item for item in wncdtags if f'wncd_{item[0]}' == wncdtuple[3]]
        #print(tagtuple)
        # Create a new tuple with (wncd_instance, site_tag, cpu5sec, cpu1min, cpu5min, aps_joined)
        newproclist.append((wncdtuple[3], tagtuple[0][1], int(wncdtuple[0]), int(wncdtuple[1]), int(wncdtuple[2]), tagtuple[0][2]))
    #print(newproclist)
    return(newproclist)

def convert_to_influxline(wlc, measurements):
    fluxline_measurements = ''
    for index, tuple in enumerate(measurements):
        print(tuple)
        #print(f'Got 5Sec: {tuple[2]}, 1Min: {tuple[3]}, 5Min: {tuple[4]} of {tuple[0]}')
        sitetag = 'None' if tuple[1] == None else tuple[1] 
        measurement = f'wireless-stats,metric=wncd,device={wlc},instance={tuple[0]} fiveseccpu={tuple[2]},onemincpu={tuple[3]},fivemincpu={tuple[4]},sitetag="{sitetag}",apsjoined={tuple[5]}'
        #print(measurement)
        fluxline_measurements += measurement + '\n'
    print(repr(fluxline_measurements))
    return(fluxline_measurements)


def send_to_influxdb(influxenv, payload):
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}\
/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'

    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    response = requests.request("POST", influxurl, headers=headers, data=payload)
    print(f'{response.status_code} - {response.reason} - {response.text}')
    print(f'Finished at: ' + str(time.ctime()))
    print('\nRunning a sleep loop.', end='', flush=True)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    print(f'\nRunning thread {threading.current_thread()}')
    job_thread.start()


def start_all():
    # Function that reads all target device parameters from project
    # file and calls get_wncd() for each
    devicelist = ReadEnvironmentVars.read_config_file("WLC")
    aggregatepayload = ''
    for wlc in devicelist:
        print(f"Processing WLC instance {wlc['alias']} {wlc['host']}...")
        wncdstats = get_wncd_stats(wlc)
        influx_lines = convert_to_influxline(wlc['alias'], wncdstats)
        print(influx_lines)
        aggregatepayload += influx_lines
    #print(repr(aggregatepayload))
    print(aggregatepayload)
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    send_to_influxdb(influxenv, aggregatepayload)


roomid = ReadEnvironmentVars.read_config_file('wirelessalerts_webexroomid')
sendWebexMessage.sendMessage(roomid,'Starting WNCd monitoring app...')
schedule.every(60).seconds.do(run_threaded, start_all)
print('\nRunning a sleep loop.', end='', flush=True)

try:
    while True:
        print('.', end='', flush=True)
        schedule.run_pending()
        time.sleep(10)
except KeyboardInterrupt:
    print('\nUser initiated stop - closing down process...')
    sendWebexMessage.sendMessage(roomid,'Stopping WNCd monitoring app...')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
