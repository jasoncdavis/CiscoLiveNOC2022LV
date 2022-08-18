import requests
import ReadEnvironmentVars
import json
import sys, os
import InsertUpdateMySQLfull
import time
import schedule, threading
from datetime import datetime


def put_wireless_stats_in_influx(influxenv, payload):
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:\
{influxenv["port"]}/api/v2/write?bucket={influxenv["influxbucket"]}&\
org={influxenv["influxorg"]}&precision=s'

    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    print('Sending wireless client data to Influx')
    response = requests.request("POST", influxurl, headers=headers, data=payload)
    print(f'{response.status_code} - {response.reason} - {response.text}')

def runjob():
    influxenv = ReadEnvironmentVars.read_config_file('InfluxDB')
    merakienv = ReadEnvironmentVars.read_config_file('Meraki')

    url = f'{merakienv["baseURL"]}/networks/{merakienv["networkId"]}/wireless/clientCountHistory?timespan={merakienv["timespan"]}&resolution={merakienv["resolution"]}'

    payload={}
    headers = {
    'X-Cisco-Meraki-API-Key': merakienv['APIkey']
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    #print(response.text)
    clientdata = json.loads(response.text)
    print(clientdata)

    '''measurement = f'wirelessclientcounts,controller={entryjson["controller"]} \
    80211ax5-count={entryjson["80211ax5-count"]},\
    80211ax2-count={entryjson["80211ax2-count"]},\
    80211ac-count={entryjson["80211ac-count"]},\
    80211n5-count={entryjson["80211n5-count"]},\
    80211n24-count={entryjson["80211n24-count"]},\
    80211a-count={entryjson["80211a-count"]},\
    80211g-count={entryjson["80211g-count"]},\
    80211b-count={entryjson["80211b-count"]}'
    '''

    measurement = f'wirelessclientcounts,controller=Meraki total-count={clientdata[0]["clientCount"]}'
    print(measurement)

    put_wireless_stats_in_influx(influxenv, measurement)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    start = datetime.now()
    print(f'\nRunning thread at {start.strftime("%H:%M:%S")}')
    job_thread.start()


## MAIN
if __name__ == "__main__":
    start = datetime.now()
    print(f'Started task at {start.strftime("%H:%M:%S")}')

    runjob()

    schedule.every(300).seconds.do(run_threaded, runjob)
    print('\nRunning a sleep loop.', end='', flush=True)

    try:
        while True:
            print('.', end='', flush=True)
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        print('\nUser initiated stop - closing down process...')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)