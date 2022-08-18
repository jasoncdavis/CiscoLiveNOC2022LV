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

def get_interface_stats(device):
    interface_filter = '''
    <filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
        <interfaces xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-interfaces-oper">
            <interface>
                <name/>
                <interface-type/>
                <admin-status/>
                <oper-status/>
                <last-change/>
                <speed/>
                <v4-protocol-stats>
                    <in-pkts/>
                    <in-octets/>
                    <out-pkts/>
                    <out-octets/>
                </v4-protocol-stats>
                <v6-protocol-stats>
                    <in-pkts/>
                    <in-octets/>
                    <out-pkts/>
                    <out-octets/>
                </v6-protocol-stats>
            </interface>
        </interfaces>
    </filter>
    '''

    with manager.connect(host=device['host'], port=830, username=device['username'], password=device['password'], hostkey_verify=False) as ncsession:
        ncreply = ncsession.get(interface_filter).data_xml
        ncreply_nons = strip_ns(ncreply)
        xmldata = ET.fromstring(ncreply_nons).findall(".//interface")

    return(xmldata)

def convert_xml(devicename, xmldata):
    # Convert XML data from NETCONF interface form into Influx writeline
    measurement = ''
    for interface in xmldata:
        measurement += (f'interface-ipv4v6,device={devicename},'
        f'interface={interface.find("name").text} '
        f'interface-type=\"{interface.find("interface-type").text}\",'
        f'admin-status=\"{interface.find("admin-status").text}\",'
        f'oper-status=\"{interface.find("oper-status").text}\",'
        f'last-change=\"{interface.find("last-change").text}\",'
        f'speed={interface.find("speed").text},'
        f'ipv4-in-pkts={interface.find("v4-protocol-stats/in-pkts").text},'
        f'ipv4-in-octets={interface.find("v4-protocol-stats/in-octets").text},'
        f'ipv4-out-pkts={interface.find("v4-protocol-stats/out-pkts").text},'
        f'ipv4-out-octets={interface.find("v4-protocol-stats/out-octets").text},'
        f'ipv6-in-pkts={interface.find("v6-protocol-stats/in-pkts").text},'
        f'ipv6-in-octets={interface.find("v6-protocol-stats/in-octets").text},'
        f'ipv6-out-pkts={interface.find("v6-protocol-stats/out-pkts").text},'
        f'ipv6-out-octets={interface.find("v6-protocol-stats/out-octets").text}\n')

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
        xmldata = get_interface_stats(device)
        this_device_ints = convert_xml(device['alias'], xmldata)
        nlines = this_device_ints.count('\n')
        aggregatelist.append(this_device_ints)
        print(f"  Got {nlines} interfaces from {device['alias']} {device['host']}...")
    measurements = '\n'.join(str(int) for int in aggregatelist)
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    send_to_influxdb(influxenv, measurements)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

schedule.every(10).seconds.do(run_threaded, start_all)

while True:
    schedule.run_pending()
    time.sleep(1)