# SSHget-switch-stats.py

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


def get_sw_object_manager(device):
    roomid = ReadEnvironmentVars.read_config_file('switchalerts_webexroomid')

    command = 'show platform software object-manager switch active F0 statistics'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=10) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    #msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'(Pending-(issue|acknowledgement): (\d+))'
    re_result = re.findall(regexstr, result.stdout)
    for match in re_result:
        if int(match[2]) > 10:
            sendWebexMessage.sendMessage(roomid, f'Got Object-Manager stat over 10 on {device["alias"]} / {device["host"]}\n```ios{result.stdout}')

    regexstr = r'Error-objects: (\d+)'
    re_result = re.search(regexstr, result.stdout)
    if int(re_result.group(1)) > 10:
        sendWebexMessage.sendMessage(roomid, f'Got Object-Manager stat over 10 on {device["alias"]} / {device["host"]}\n```ios{result.stdout}')
    #print(re_result)

    command = 'show platform software object-manager switch standby F0 statistics'
    with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]}) as conn:
        result = conn.run(command, hide=True)
    #msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    if re.findall(r'The process for the command is not responding or is otherwise unavailable', result.stdout):
        #print('No standby support')
        pass
    else:
        regexstr = r'(Pending-(issue|acknowledgement): (\d+))'
        re_result = re.findall(regexstr, result.stdout)
        for match in re_result:
            if int(match[2]) > 10:
                sendWebexMessage.sendMessage(roomid, f'Got Object-Manager stat over 10 on {device["alias"]} / {device["host"]}\n```ios{result.stdout}')

        regexstr = r'Error-objects: (\d+)'
        #re_result = re.findall(regexstr, result.stdout)
        re_result = re.search(regexstr, result.stdout)
        #print(result.stdout)
        #print(re_result.group(1))
        if re_result:
            if int(re_result.group(1)) > 10:
                sendWebexMessage.sendMessage(roomid, f'Got Object-Manager stat over 10 on {device["alias"]} / {device["host"]}\n```ios{result.stdout}')


def get_sw_cpu_queue_stats(device):
    roomid = ReadEnvironmentVars.read_config_file('switchalerts_webexroomid')

    command = 'show platform hardware fed switch active qos queue stats internal cpu policer'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'\d+\s+\d+\s+([\w\s]+?)\s+Yes\s+\d+\s+\d+\s+(\d+)\s+(\d+)'
    re_result = re.findall(regexstr, result.stdout)
    for match in re_result:
        if int(match[2]) > 3000:
            print(f'{device["alias"]} / {device["host"]} had CPU Queue Stat {match[0]} drops over 0')
            sendWebexMessage.sendMessage(roomid, f'{device["alias"]} / {device["host"]} had CPU Queue Stat {match[0]} drops over 0 at {match[2]}')
            command = 'clear platform hardware fed switch active qos statistics internal cpu policer'
            try:
                with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
                    result = conn.run(command, hide=True)
                print(result)
                #clear platform hardware fed switch active qos statistics internal cpu policer
            except TimeoutError:
                print(f'   {device["alias"]} Timed out')
                return('FAILED')


    regexstr = r'^(2[0|1])\s+\d+\s+\d+\s+(\d+)\s+(\d+)'
    re_result = re.findall(regexstr, result.stdout, re.S | re.M)
    #print(re_result)
    for match in re_result:
        if int(match[1]) > 0 or int(match[2]) > 0:
            print(f'{device["alias"]} / {device["host"]} had CPU Queue Second Level Policer Statistics greater than 0 on Policer Index {match[0]}')
            sendWebexMessage.sendMessage(roomid, f'{device["alias"]} / {device["host"]} had CPU Queue Second Level Policer Statistics greater than 0 on Policer Index {match[0]}')


def get_sw_asic_exceptions(device):
    roomid = ReadEnvironmentVars.read_config_file('switchalerts_webexroomid')

    command = 'sh plat hard fed sw active fwd-asic drops exceptions | ex 0[ ]+0[ ]+0[ ]+'
    try:
        with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]},connect_timeout=15) as conn:
            result = conn.run(command, hide=True)
    except TimeoutError:
        print(f'   {device["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'(\d)\s\s(\d)\s\s(\w+)\s+\d+\s+(\d+)\s+(\d+)'
    re_result = re.findall(regexstr, result.stdout)
    #print(re_result)
    measurements = ''
    for asiccore in re_result:
        measurement = f'switching-asic-exceptions,device={device["alias"]},asic={asiccore[0]},core={asiccore[1]},name={asiccore[2]} \
current={asiccore[3]},delta={asiccore[4]}\n'
        #print(measurement)
        measurements += measurement
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
        WHERE (device_group='IDF' OR device_group='DIST' OR device_group='CORE') AND hostname not like '%SPARE%';
    '''
    print(SQL)
    idf_switches = SelectFromMySQL.selectsql(mysqlenv, SQL)
    #print(f'IDF Switches: {idf_switches}')
    failed_devices = []
    startlooptime = datetime.datetime.now()
    for device in idf_switches:
        #print(device)
        device = {'host': f'{device[1]}', 'alias': f'{device[0]}', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}', 'location': f'{device[5]}'}
        #print(device)
        print(f"Processing Device instance {device['alias']} {device['host']} at {device['location']}...")
        print('   Working Switch Object Manager checks')
        result = get_sw_object_manager(device)
        if result == 'FAILED':
            print('  Skipping other checks because of initial connectivity problems')
            failed_devices.append(device['alias'])
        else:
            print('   Working Switch CPU Queue checks')
            result = get_sw_cpu_queue_stats(device)
            if result == 'FAILED':
                failed_devices.append(device['alias'])
            
            print('   Working Switch ASIC Exception checks')
            result = get_sw_asic_exceptions(device)
            if result == 'FAILED':
                failed_devices.append(device['alias'])
            else:
                #print(result)
                send_to_influxdb(influxenv, result)

    unique_failed_devices = []
    for device in failed_devices:
        if device not in unique_failed_devices:
            unique_failed_devices.append(device)

    print(f'\nDevices failing this run:\n{unique_failed_devices}')
    print(f'Loop time took: {datetime.datetime.now() - startlooptime}')


## MAIN
roomid = ReadEnvironmentVars.read_config_file('switchalerts_webexroomid')
sendWebexMessage.sendMessage(roomid,'Starting SSH-switch monitoring process...')
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
