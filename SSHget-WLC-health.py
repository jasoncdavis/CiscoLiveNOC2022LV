# SSHget-WLC-health.py
# Version: 1
# Based on SSHget-wncd-v3 - added standby system health-check
# Uses info from  optionsconfig.yaml to determine WLC environment.
# Ensure you have YAML configuration that appear as the follow...
'''
WLC:
  - host: (IP or hostname)
    alias: (friendly name/DNS)
    description: (description of WLC cluster - zone, location, purpose, etc)
    CheckSSLCert: False  # False, if you are not security conscious and using self-signed certs internally
    username: CHANGEME
    password: CHANGEME
    backup_host: (N + 1 WLC IP or hostname)
  - host: (Second cluster IP or hotname)
    alias: (friendly name/DNS)
    description: (description of WLC cluster - zone, location, purpose, etc)
    CheckSSLCert: False  # False, if you are not security conscious and using self-signed certs internally
    username: CHANGEME
    password: CHANGEME
    backup_host: (N + 1 WLC IP or hostname)
'''

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


def get_wlc_commands(wlc_params, commands):
    results = []
    #result = Connection(f'{wlc_params["username"]}@{wlc_params["host"]}',connect_kwargs={"password": wlc_params["password"]}).run(command, hide=True)
    with Connection(f'{wlc_params["username"]}@{wlc_params["host"]}',connect_kwargs={"password": wlc_params["password"]}) as conn:
        for command in commands:
            results.append(conn.run(command, hide=True).stdout)
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(results)
    return(results)


def get_wncd_proclist(incoming_results):
    regexstr = r'\s\d+\s+\d+\s+(\d+)%\s+(\d+)%\s+(\d+)%\s+.\s+\d+\s+(\S+)'
    proclist = re.findall(regexstr, incoming_results, re.S | re.M)
    #print(proclist)
    return(proclist)


def get_wncd_tags(wncd_results_in):
    wncdtags = []
    #print(wncd_results_in)
    for wncd_instance, wncd_value in enumerate(wncd_results_in):
        regexstr = r'(\S+)\s+SITE TAG\s+(\d+)'
        wncdtag = re.findall(regexstr, wncd_value, re.S | re.M)
        #print(wncdtag)
        if wncdtag == None:
            #print(wncdtags)
            wncdtags.append((wncd_instance, None, 0))
        else:
            #print(wncdtag.group(1), wncdtag.group(2))
            #print(len(wncdtag))
            if len(wncdtag) == 1:
                wncdtags.append((wncd_instance, wncdtag[0][0], int(wncdtag[0][1])))
            else:
                for count, individualtag in enumerate(wncdtag, start=1):
                    if count == 1:
                        wncdtags.append((f'{wncd_instance}', individualtag[0], int(individualtag[1])))
                    else:
                        wncdtags.append((f'{wncd_instance}-{count}', individualtag[0], int(individualtag[1])))
        #print(wncdtags)
    #print(wncdtags)
    return(wncdtags)


def get_merged_wncd_proclist(proclist, wncdtags):
    # HERE
    #print(f'proclist is: {proclist}\nwncdtags are: {wncdtags}')
    newproclist = []
    for wncdtuple in wncdtags:
        #print(wncdtuple)
        #print(wncdtuple[0])
        #tagtuple = [item for item in wncdtags if f'wncd_{item[0]}' == wncdtuple[3]]
        proctuplelist = [item for item in proclist if f'{item[3]}' == f'wncd_{wncdtuple[0]}']

        # Look to see if we're on a secondary site-tag of the wncd process
        # Create a new tuple with (wncd_instance, site_tag, cpu5sec, cpu1min, cpu5min, aps_joined)
        if len(proctuplelist) > 0:
            newproclist.append((proctuplelist[0][3], wncdtuple[1], int(proctuplelist[0][0]), int(proctuplelist[0][1]), int(proctuplelist[0][2]), wncdtuple[2]))
        else:
            newproclist.append((f'wncd_{wncdtuple[0]}', wncdtuple[1], None, None, None, wncdtuple[2]))
        '''
        print(proctuplelist)

        print(proctuplelist[0][3])
        print(wncdtuple[1])
        print(int(proctuplelist[0][0]))
        print(int(proctuplelist[0][1]))
        print(int(proctuplelist[0][2]))
        print(wncdtuple[2])
        # Create a new tuple with (wncd_instance, site_tag, cpu5sec, cpu1min, cpu5min, aps_joined)
        #newproclist.append((proctuplelist[0][3], wncdtuple[1], int(proctuplelist[0][0]), int(proctuplelist[0][1]), int(proctuplelist[0][2]), wncdtuple[2]))
        
        print((proctuplelist[0][3], wncdtuple[1], int(proctuplelist[0][0]), int(proctuplelist[0][1]), int(proctuplelist[0][2]), wncdtuple[2]))
        '''
    #print(newproclist)
    return(newproclist)


def convert_to_influxline(wlc, measurements):
    fluxline_measurements = ''
    for index, tuple in enumerate(measurements):
        #print(tuple)
        #print(f'Got 5Sec: {tuple[2]}, 1Min: {tuple[3]}, 5Min: {tuple[4]} of {tuple[0]}')
        sitetag = 'None' if tuple[1] == None else tuple[1]
        # Check to see if this is a 'short' entry with no CPU and only AP join counts 
        # [eg. secondary site-tag on wncd process
        if tuple[2] == None:
            measurement = f'wireless-stats,metric=wncd,device={wlc},instance={tuple[0]} sitetag="{sitetag}",apsjoined={tuple[5]}'
        else:
            measurement = f'wireless-stats,metric=wncd,device={wlc},instance={tuple[0]} fiveseccpu={tuple[2]},onemincpu={tuple[3]},fivemincpu={tuple[4]},sitetag="{sitetag}",apsjoined={tuple[5]}'
        #print(measurement)
        fluxline_measurements += measurement + '\n'
    #print(fluxline_measurements)
    return(fluxline_measurements)


def send_to_influxdb(influxenv, payload):
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'

    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    response = requests.request("POST", influxurl, headers=headers, data=payload)
    print(f'{response.status_code} - {response.reason} - {response.text}')
    print(f'Finished at: ' + str(time.ctime()))


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    print(f'\nRunning thread {threading.current_thread()}')
    job_thread.start()


def start_all():
    # Function that reads all target device parameters from project
    # file and calls get_wncd() for each
    devicelist = ReadEnvironmentVars.read_config_file("WLC")
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")

    aggregatepayload = ''
    for wlc in devicelist:
        print(f'Processing WLC instance {wlc["alias"]} {wlc["host"]}...')
        primary_commands = [
            'show process cpu platform | incl Pid|wncd',
            'show wireless loadbalance tag affinity wncd 0',
            'show wireless loadbalance tag affinity wncd 1',
            'show wireless loadbalance tag affinity wncd 2',
            'show wireless loadbalance tag affinity wncd 3',
            'show wireless loadbalance tag affinity wncd 4',
            'show wireless loadbalance tag affinity wncd 5',
            'show wireless loadbalance tag affinity wncd 6',
            'show wireless loadbalance tag affinity wncd 7',
            'show redundancy'
        ]
        # Results should come back as a list, then can be sent for further processing
        primary_results = get_wlc_commands(wlc, primary_commands)
        #primary_results = ['\r\n\r\n   Pid    PPid    5Sec    1Min    5Min  Status        Size  Name                  \r\n 21184   21174     26%     27%     27%  S           710288  wncd_6                \r\n 19976   19967     21%     22%     21%  S          1116356  wncd_1                \r\n 20145   20136     15%     15%     16%  S           651660  wncd_2                \r\n 19784   19765     11%     10%      9%  S           684216  wncd_0                \r\n 20383   20365      7%      8%      8%  R           949692  wncd_3                \r\n 20650   20635      5%      4%      5%  S           657204  wncd_4                \r\n 21327   21308      2%      3%      3%  S           574524  wncd_7                \r\n 20948   20929      0%     34%     33%  R           642348  wncd_5                \r\n', '\r\nLoad for five secs: 3%/0%; one minute: 5%; five minutes: 6%\r\nTime source is NTP, 08:11:56.123 PDT Tue Jun 14 2022\r\n\r\nRedundant System Information :\r\n------------------------------\r\n       Available system uptime = 4 days, 11 hours, 11 minutes\r\nSwitchovers system experienced = 0\r\n              Standby failures = 0\r\n        Last switchover reason = none\r\n\r\n                 Hardware Mode = Duplex\r\n    Configured Redundancy Mode = sso\r\n     Operating Redundancy Mode = sso\r\n              Maintenance Mode = Disabled\r\n                Communications = Up\r\n\r\nCurrent Processor Information :\r\n-------------------------------\r\n               Active Location = slot 1\r\n        Current Software state = ACTIVE\r\n       Uptime in current state = 4 days, 11 hours, 10 minutes\r\n                 Image Version = Cisco IOS Software [Bengaluru], C9800 Software (C9800_IOSXE-K9), Version 17.6.3, RELEASE SOFTWARE (fc4)\r\nTechnical Support: http://www.cisco.com/techsupport\r\nCopyright (c) 1986-2022 by Cisco Systems, Inc.\r\nCompiled Wed 30-Mar-22 23:12 by mcpre\r\n                          BOOT = bootflash:packages.conf,12;\r\n                   CONFIG_FILE = \r\n        Configuration register = 0x2102\r\n               Recovery mode   = Not Applicable\r\n\r\nPeer Processor Information :\r\n----------------------------\r\n              Standby Location = slot 2\r\n        Current Software state = STANDBY HOT \r\n       Uptime in current state = 4 days, 11 hours, 7 minutes\r\n                 Image Version = Cisco IOS Software [Bengaluru], C9800 Software (C9800_IOSXE-K9), Version 17.6.3, RELEASE SOFTWARE (fc4)\r\nTechnical Support: http://www.cisco.com/techsupport\r\nCopyright (c) 1986-2022 by Cisco Systems, Inc.\r\nCompiled Wed 30-Mar-22 23:12 by mcpre\r\n                          BOOT = bootflash:packages.conf,12;\r\n                   CONFIG_FILE = \r\n        Configuration register = 0x2102\r\n\r\n']
        #print(primary_results)
        proclist_results = get_wncd_proclist(primary_results[0])
        #print(proclist_results)

        wncd_tags = get_wncd_tags(primary_results[1:9])
        #print(wncd_tags)
        merged_tags = get_merged_wncd_proclist(proclist_results, wncd_tags)
        #print(f'Merged tags: {merged_tags}')
        influx_lines = convert_to_influxline(wlc["alias"], merged_tags)
        #print(influx_lines)
        aggregatepayload += influx_lines
        
        #check_wlc_standby()
        #print(f'   = Processing WLC Standby {wlc["backup_alias"]} {wlc["backup_host"]}...')
        standby_commands = [
            'show redundancy'
        ]
        #secondary_results = get_wlc_commands(primary_commands)
        # Send for secondary processing

        '''wncdstats = get_wncd_stats(wlc)
        influx_lines = convert_to_influxline(wlc['alias'], wncdstats)
        print(influx_lines)
        aggregatepayload += influx_lines'''
    #print(repr(aggregatepayload))
    print(aggregatepayload)
    send_to_influxdb(influxenv, aggregatepayload)


print(f'Starting {__file__}')
start_all()
roomid = ReadEnvironmentVars.read_config_file('wirelessalerts_webexroomid')
#sendWebexMessage.sendMessage(roomid,'Starting WNCd monitoring app...')
schedule.every(60).seconds.do(run_threaded, start_all)
print('\nRunning a sleep loop.', end='', flush=True)

try:
    while True:
        print('.', end='', flush=True)
        schedule.run_pending()
        time.sleep(10)
except KeyboardInterrupt:
    print('\nUser initiated stop - closing down process...')
    #sendWebexMessage.sendMessage(roomid,'Stopping WNCd monitoring app...')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
