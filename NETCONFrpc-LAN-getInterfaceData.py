# version 2 - much more modular and pulls device info from optionconfig.yaml
# 2022-05-21

from datetime import datetime
from ncclient import manager
from ncclient.transport.errors import AuthenticationError, SSHError, SessionCloseError

import xml.etree.ElementTree as ET
import sys
import re
import threading
import time
import schedule
import requests
import ReadEnvironmentVars
import SelectFromMySQL


def strip_ns(xml_string):
    return re.sub(' xmlns="[^"]+"', '', xml_string)

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
                <statistics>
                    <in-octets/>
                    <in-discards-64/>
                    <in-errors-64/>
                    <out-octets-64/>
                    <out-discards/>
                    <out-errors/>
                    <in-crc-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
    '''

    #print(device)
    try:
        with manager.connect(host=device['host'], port=830, username=device['username'], password=device['password'], hostkey_verify=False, timeout=10) as ncsession:
            ncreply = ncsession.get(interface_filter).data_xml
            ncreply_nons = strip_ns(ncreply)
            xmldata = ET.fromstring(ncreply_nons).findall(".//interface")

            return(xmldata)
    except (SSHError, SessionCloseError):
            return('FAILED')

    

def get_cpu_stats(device):
    rpcnc_filter = '''
    <filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
        <cpu-usage xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-process-cpu-oper">
        <cpu-utilization>
          <one-minute/>
          <five-minutes/>
        </cpu-utilization>
      </cpu-usage>
    </filter>
    '''

    #print(device)
    with manager.connect(host=device['host'], port=830, username=device['username'], password=device['password'], hostkey_verify=False) as ncsession:
        ncreply = ncsession.get(rpcnc_filter).data_xml
        ncreply_nons = strip_ns(ncreply)
        #print(ncreply_nons)
        xmldata = ET.fromstring(ncreply_nons).findall(".//cpu-utilization")
        
    #print(ET.tostring(xmldata[0], encoding='utf8').decode('utf8'))
    return(xmldata)

def get_mem_stats(device):
    rpcnc_filter = '''
    <filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
        <memory-statistics xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-memory-oper">
        <memory-statistic>
          <name>Processor</name>
          <total-memory/>
          <used-memory/>
          <free-memory/>
        </memory-statistic>
      </memory-statistics>
    </filter>
    '''

    #print(device)
    with manager.connect(host=device['host'], port=830, username=device['username'], password=device['password'], hostkey_verify=False) as ncsession:
        ncreply = ncsession.get(rpcnc_filter).data_xml
        ncreply_nons = strip_ns(ncreply)
        #print(ncreply_nons)
        xmldata = ET.fromstring(ncreply_nons).findall(".//memory-statistic")
        
    #print(ET.tostring(xmldata[0], encoding='utf8').decode('utf8'))
    return(xmldata)


def convert_interface_xml(devicename, xmldata):
    # Convert XML data from NETCONF interface form into Influx writeline
    measurement = ''
    for interface in xmldata:
        #print(ET.tostring(interface))
        measurement += (f'LAN-interfaces,device={devicename},'
        f'interface={interface.find("name").text} '
        f'interface-type=\"{interface.find("interface-type").text}\",'
        f'admin-status=\"{interface.find("admin-status").text}\",'
        f'oper-status=\"{interface.find("oper-status").text}\",'
        f'last-change=\"{interface.find("last-change").text}\",'
        f'speed={interface.find("speed").text},'
        f'stats-in-octets={interface.find("statistics/in-octets").text},'
        f'stats-in-crc-errors={interface.find("statistics/in-crc-errors").text},'
        f'stats-in-discards={interface.find("statistics/in-discards-64").text},'
        f'stats-in-errors={interface.find("statistics/in-errors-64").text},'
        f'stats-out-octets={interface.find("statistics/out-octets-64").text},'
        f'stats-out-discards={interface.find("statistics/out-discards").text},'
        f'stats-out-errors={interface.find("statistics/out-errors").text}\n')

        #print(repr(measurement))
    return(measurement)


def convert_cpu_xml(devicename, xmldata):
    # Convert XML data from NETCONF interface form into Influx writeline
    #print(ET.tostring(xmldata[0], encoding='utf8').decode('utf8'))

    measurement = (f'LAN-cpu,device={devicename} '
        f'one-min={xmldata[0].find("one-minute").text},'
        f'five-min={xmldata[0].find("five-minutes").text}\n')

    #print(repr(measurement))
    return(measurement)


def convert_mem_xml(devicename, xmldata):
    # Convert XML data from NETCONF interface form into Influx writeline
    #print(ET.tostring(xmldata[0], encoding='utf8').decode('utf8'))

    measurement = (f'LAN-mem,device={devicename},type={xmldata[0].find("name").text} '
        f'total-memory={xmldata[0].find("total-memory").text},'
        f'used-memory={xmldata[0].find("used-memory").text},'
        f'free-memory={xmldata[0].find("free-memory").text}\n')

    #print(repr(measurement))
    return(measurement)


def send_to_influx(influxenv, measurements):
    # Send data to InfluxDB
    #print(measurements)
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}\
/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'
    
    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv['influxtoken'],
    'Content-Type': 'text/plain'
    }

    response = requests.request("POST", influxurl, headers=headers, data=measurements)
    print(f'  Results: {response.status_code} - {response.text}')
    print(f'Finished at: {str(time.ctime())}\n')


def start_all():
    # Function that reads all target device parameters from project
    # file and calls get_interfaces() for each
    devicelist = ReadEnvironmentVars.read_config_file("InterfaceDevices")
    credentials = ReadEnvironmentVars.read_config_file("AAA-default")
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    mysqlenv = ReadEnvironmentVars.read_config_file("MySQL")

    #print(credentials)
    #print(devicelist)
    devicelist = [{'alias': 'MBL1-NOC-DIST', 'host': '10.11.0.244', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}'},\
        {'alias': 'MBL1-NOC-IDF-2', 'host': '10.110.1.11', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}'},\
        {'alias': 'MB0-CR05-IDF', 'host': '10.101.0.10', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}'},\
        {'alias': 'MB0-CR38-IDF', 'host': '10.101.0.11', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}'},\
        {'alias': 'MB0-CR43-IDF', 'host': '10.101.0.12', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}'}]

    ## Get IDF Switch list from MySQL Inventory table
    SQL = '''SELECT hostname, mgmt_ip_address, device_type, device_group, model, location 
        FROM devnet_dashboards.inventory
        WHERE (device_group='IDF' OR device_group='DIST' OR device_group='CORE') AND hostname not like '%SPARE%';
    '''
    idf_switches = SelectFromMySQL.selectsql(mysqlenv, SQL)
    #print(f'IDF Switches: {idf_switches}')

    failed_devices = []
    startlooptime = datetime.now()
    for device in idf_switches:
        #print(device)
        device = {'host': f'{device[1]}', 'alias': f'{device[0]}', 'username': f'{credentials["username"]}',\
        'password': f'{credentials["password"]}', 'location': f'{device[5]}'}
        #print(device)
        print(f"Processing Device instance {device['alias']} {device['host']} at {device['location']}...")
        
        int_xml = get_interface_stats(device)
        if int_xml == 'FAILED':
            failed_devices.append(device['alias'])
            print(f'Could not connect to {device["alias"]}\n')
        else:
            this_device_ints = convert_interface_xml(device['alias'], int_xml)

            cpu_xml = get_cpu_stats(device)
            this_device_cpu = convert_cpu_xml(device['alias'], cpu_xml)

            mem_xml = get_mem_stats(device)
            this_device_mem = convert_mem_xml(device['alias'], mem_xml)
            #print(this_device_ints + this_device_cpu + this_device_mem)

            send_to_influx(influxenv, this_device_ints + this_device_cpu + this_device_mem)
    print(f'Failed Devices on this run:\n{failed_devices}')
    print(datetime.now() - startlooptime)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()


## MAIN
start_all()
schedule.every(300).seconds.do(run_threaded, start_all)

while True:
    schedule.run_pending()
    time.sleep(15)