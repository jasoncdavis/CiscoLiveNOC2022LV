# SSHget-switch-stats.py

# Obtains WLC redundancy info (via CLI *sigh*) and puts into InfluxDB
# Version: 1

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


def get_influx_stats(influxenv):
    command = 'sudo du -s /var/lib/influxdb/engine/data'
    try:
        result = Connection(f'{influxenv["SSHusername"]}@{influxenv["host"]}',connect_kwargs={"password": influxenv["SSHpassword"]},connect_timeout=15).run(command, hide=True)
    except TimeoutError:
        print(f'   {influxenv["alias"]} Timed out')
        return('FAILED')
    
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'(\d+)\s+'
    re_result = re.findall(regexstr, result.stdout)
    #print(re_result[0])
    measurement = f'tig-stats,server={influxenv["alias"]} \
dbfilespace={re_result[0]}\n'
    print(measurement)
    return(measurement)


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

    startlooptime = datetime.datetime.now()
    stats=get_influx_stats(influxenv)
    send_to_influxdb(influxenv,stats)    


## MAIN
#roomid = ReadEnvironmentVars.read_config_file('switchalerts_webexroomid')
#sendWebexMessage.sendMessage(roomid,'Starting SSH-switch monitoring process...')
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
    sendWebexMessage.sendMessage(roomid,'Stopping SSH-tig monitoring process...')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
