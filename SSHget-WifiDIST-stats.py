# SSHget-WifiDIST-stats.py

# Obtains WLC redundancy info (via CLI *sigh*) and puts into InfluxDB
# Version: 2 TBU

from fabric import Connection
import re
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import sys, os
import threading
import time
import datetime
import schedule
import sendWebexMessage
import ReadEnvironmentVars
import SelectFromMySQL


def get_adjacency_tables(device):
    command = 'show system internal adjmgr internal info | i "Current v[46] entries"'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
        #result = Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15).run(command, hide=True)
    except TimeoutError:
        #print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'in AM : (\d+)'
    #re.search(r'in AM : (\d+)', searchText, re.S | re.M)
    re_result = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(re_result)
    measurements = f'DIST-stats,stat=adjmgr,device={device["alias"]} ipv4entries={re_result[0]},ipv6entries={re_result[1]}\n'
    #print(measurements)
    return(measurements)


def get_ipv6_neighbors(device):
    command = 'show ipv6 neighbor summ | inc Total'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))
    regexstr = r'Total\s+:\s+(\d+)'
    #re.search(r'in AM : (\d+)', searchText, re.S | re.M)
    re_result = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(re_result)
    measurements = f'DIST-stats,stat=ipv6neighbor,device={device["alias"]} total={re_result[0]}\n'
    #print(measurements)
    return(measurements)


def get_arp_entries(device):
    command = 'show ip arp summ | inc Total'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))
    regexstr = r'Total\s+:\s+(\d+)'
    re_result = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(re_result)
    measurements = f'DIST-stats,stat=arp,device={device["alias"]} total={re_result[0]}\n'
    #print(measurements)
    return(measurements)


def get_MAC_entries(device):
    command = 'show mac address-table count | incl Dynamic'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))
    regexstr = r'Count:\s+(\d+)'
    re_result = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(re_result)
    measurements = f'DIST-stats,stat=mac,device={device["alias"]} total={re_result[0]}\n'
    #print(measurements)
    return(measurements)


def get_forwarding_tcam(device):
    command = 'show hardware capacity forwarding | i "1[ ]+[01][ ]+[0-9]+[ ]+[0-9]+[ ]+[0-9]+[ ]+[0-9]+[ ]+[0-9]+[ ]+[0-9]+"'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))
    regexstr = r'^\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
    re_result = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(re_result)
    measurements = ''
    for instance in re_result:
        measurements += f'DIST-stats,stat=forwardingtcam,device={device["alias"]},module={instance[0]},instance={instance[1]} total={instance[2]},used={instance[3]},multicast={instance[4]},unicast={instance[5]}\n'
    #print(measurements)
    return(measurements)

def get_forwarding_tcam_usage(device):
    command = 'show hardware capacity forwarding'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    measurements = ''
    for asic in [0,1]:
        regexstr = fr'TCAM usage statistics for instance :({asic})\n(.*?)---\n(?:TCAM|\nAdjac)'
        asic_record_result = re.findall(regexstr, result.stdout, re.S | re.M)
        #print(asic_record_result[0][1])
        regexstr = r'''^\s\s(IPV[46]\s(?:unicast|multicast|LinkLocal))\s+(\d+)\s+(\d+)\s+(\d+)'''
        re_result = re.findall(regexstr, asic_record_result[0][1], re.S | re.M)
        #print(re_result)
        for metric in re_result:
            metrictype = metric[0].replace(' ', '\ ')
            #print(f'{metric}')
            #print(f'{metrictype}')
            measurements += f'''DIST-stats,stat=forwardingtcamusage,device={device["alias"]},asic={asic},type={metrictype} logical={metric[1]},physical={metric[2]},totalpercent={metric[3]}\n'''
    #print(measurements)
    return(measurements)


def send_to_influxdb(influxenv, payload):
    #print(f'Pushing influx the following payload\n{payload}')
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}\
/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'
    #print(influxurl)
    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv['influxtoken'],
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
    startlooptime = datetime.datetime.now()

    credentials = ReadEnvironmentVars.read_config_file("AAA-default")
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    mysqlenv = ReadEnvironmentVars.read_config_file("MySQL")

    ## Get IDF Switch list from MySQL Inventory table
    SQL = '''SELECT hostname, mgmt_ip_address, device_type, device_group, model, location 
        FROM devnet_dashboards.inventory
        WHERE device_group='DIST-NXOS';
    '''
    #print(SQL)
    idf_switches = SelectFromMySQL.selectsql(mysqlenv, SQL)
    #print(f'IDF Switches: {idf_switches}')
    failed_devices = []
    startlooptime = datetime.datetime.now()
    agg_measurements = []
    for device in idf_switches:
        #print(device)
        device = {'host': f'{device[1]}', 'alias': f'{device[0]}', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}', 'location': f'{device[5]}'}
        #print(device)
        print(f"Processing Device instance {device['alias']} {device['host']} at {device['location']}...")
        print('   Working Adjacency table entries IPv4 and IPv6')
        result = get_adjacency_tables(device)
        agg_measurements.append(result)

        print('   Working IPv6 neighbors entries')
        result = get_ipv6_neighbors(device)
        agg_measurements.append(result)

        print('   Working ARP entries')
        result = get_arp_entries(device)
        agg_measurements.append(result)

        print('   Working MAC Table count entries')
        result = get_MAC_entries(device)
        agg_measurements.append(result)

        print('   Working Forwarding TCAM entries')
        result = get_forwarding_tcam(device)
        agg_measurements.append(result)

        print('   Working Forwarding TCAM usage entries')
        result = get_forwarding_tcam_usage(device)
        agg_measurements.append(result)

    measurements_payload = ''
    #print(agg_measurements[0])
    for measurement in agg_measurements:
        measurements_payload += measurement
    print(measurements_payload)

    send_to_influxdb(influxenv, measurements_payload)

    print(f'Loop time took: {datetime.datetime.now() - startlooptime}')


## MAIN
roomid = ReadEnvironmentVars.read_config_file('switchalerts_webexroomid')
#sendWebexMessage.sendMessage(roomid,'Starting SSH-WiFi DIST monitoring process...')
start_all()

schedule.every(300).seconds.do(run_threaded, start_all)
print('\nRunning a sleep loop.', end='', flush=True)

try:
    while True:
        print('.', end='', flush=True)
        schedule.run_pending()
        time.sleep(10)
except KeyboardInterrupt:
    print('\nUser initiated stop - closing down process...')
    sendWebexMessage.sendMessage(roomid,'Stopping SSH-switch monitoring process...')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
