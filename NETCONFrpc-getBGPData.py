# version 2 - much more modular and pulls device info from optionconfig.yaml
# 2022-05-21

from unicodedata import name
from ncclient import manager
import xml.etree.ElementTree as ET
import sys
import re
import threading
import time
import schedule
import requests
import ReadEnvironmentVars


def strip_ns(xml_string):
    return re.sub('xmlns="[^"]+"', '', xml_string)


def get_bgp_stats(device):
    bgpoper_filter = '''
    <filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
      <bgp-state-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp-oper">
        <neighbors>
          <neighbor>
            <afi-safi/>
            <vrf-name>default</vrf-name>
            <neighbor-id/>
            <description/>
            <prefix-activity>
              <received>
                <current-prefixes/>
                <total-prefixes/>
              </received>
            </prefix-activity>
          </neighbor>
        </neighbors>
      </bgp-state-data>
    </filter>
    '''

    with manager.connect(host=device['host'], port=830, username=device['username'], password=device['password'], hostkey_verify=False) as ncsession:
        ncreply = ncsession.get(bgpoper_filter).data_xml
        ncreply_nons = strip_ns(ncreply)
        xmldata = ET.fromstring(ncreply_nons).findall(".//neighbor")

    return(xmldata)


def convert_xml(devicename, xmldata):
    # Convert XML data from NETCONF interface form into Influx writeline
    measurement = ''
    for neighbor in xmldata:
        measurement += (f'Cisco-IOS-XE-bgp-oper:custom,device={devicename},'
        f'afi-safi={neighbor.find("afi-safi").text},'
        f'vrf-name={neighbor.find("vrf-name").text},'
        f'neighbor-id={neighbor.find("neighbor-id").text} '
        f'description={neighbor.find("description").text},'
        f'current-prefixes={neighbor.find("prefix-activity/received/current-prefixes").text},'
        f'total-prefixes={neighbor.find("prefix-activity/received/total-prefixes").text}\n')

        #print(repr(measurement))
    return(measurement)


def send_to_influxdb(influxenv, payload):
      # Send data to InfluxDB
    print(f'Pushing influx the following payload\n{payload}')
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}\
/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'
    #print(influxurl)
    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    response = requests.request("POST", influxurl, headers=headers, data=payload)
    print(f'{response.status_code} - {response.reason} - {response.text}')
    print(f'Finished at: ' + str(time.ctime()))


def start_all():
    # Function that reads all target device parameters from project
    # file and calls get_interfaces() for each
    devicelist = ReadEnvironmentVars.read_config_file("InterfaceDevices")
    aggregatelist = []
    deviceresults = []
    for device in devicelist:
        print(f"Processing Device instance {device['alias']} {device['host']}...")
        xmldata = get_bgp_stats(device)
        this_device_prefixes = convert_xml(device['alias'], xmldata)
        nlines = this_device_prefixes.count('\n')
        aggregatelist.append(this_device_prefixes)
        print(f"  Got {nlines} neighbors data from {device['alias']} {device['host']}...")
    measurements = '\n'.join(str(int) for int in aggregatelist)
    print(measurements)
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    send_to_influx(influxenv, measurements)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

schedule.every(120).seconds.do(run_threaded, start_all)

while True:
    schedule.run_pending()
    time.sleep(1)