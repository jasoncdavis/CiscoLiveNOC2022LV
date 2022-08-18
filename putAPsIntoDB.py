#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@filename: putAPsIntoDB.py
"""

"""Collects and puts the Wireless Access Point inventory into the
project MySQL database.

#                                                                      #
Obtains the Wireless LAN Controller (WLC) instances from the 
environment profile, optionsconfig.yaml.  Extracts the wireless AP 
parameters from getWirelessAPData.py and formats into appropriate
table schema.

Required inputs/variables:
    None

Can run as module to other Script? YES

Outputs:
    Puts wireless AP inventory into MySQL tables, inventory and
    WirelessAPs
    
Version log:
v1      2022-0515   Initial Release as part of CiscoLive NOC development

"""

__filename__ = 'putAPsIntoDB.py'
__version__ = '1'
__author__ = 'Jason Davis - jadavis@cisco.com'
__license__ = "Cisco Sample Code License, Version 1.1 - https://developer.cisco.com/site/license/cisco-sample-code-license/"


import xml.etree.ElementTree as ET
import sys, os
import re
import time
from datetime import datetime
import ReadEnvironmentVars
import getWirelessAPData
import json
import InsertUpdateMySQL
import sendWebexMessage
import schedule, threading


def extract_device_properties(controller, aps):
    """Extract devices properties from JSON string
    
    Reads device inventory as JSON, extracts the fields needed to add as inventory into MySQL
    
    :param server: dictionary containing settings of the WLC being polled [eg. host, username, password,  etc.]
    :param deviceinventory: string of JSON text representing WLC APs in a list
    :returns: list of dictionary entries representing client parameters
    """
    aplist=[]
    aps_json = json.loads(aps)
    for ap in aps_json["wireless-aps"]:
        SerialNumber = ap['wtp-serial-num']
        RadioMACAddress = ap['wtp-mac']
        EthernetMACAddress = ap['wtp-enet-mac']
        IPAddress = ap['ip-addr']
        Name = ap['name']
        Model = ap['model']
        Source = controller
        aplist.append((SerialNumber, RadioMACAddress, EthernetMACAddress, IPAddress, Name, Model, Source))
    return aplist

def update_wirelessaps_table(datetimenow, aplist):
    # Put into WirelessAPs table for wireless dashboards
    sql = f"""INSERT INTO devnet_dashboards.WirelessAPs 
      (SerialNumber, RadioMACAddress, EthernetMACAddress, IPAddress, Name, Model, Controller, DateTimeFirstSeen) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, "{datetimenow}") 
    ON DUPLICATE KEY UPDATE RadioMACAddress=VALUES(RadioMACAddress), EthernetMACAddress=VALUES(EthernetMACAddress), 
      IPAddress=VALUES(IPAddress), Name=VALUES(Name), Model=VALUES(Model), Controller=VALUES(Controller), 
      DateTimeLastSeen="{datetimenow}"
    """ 
    InsertUpdateMySQL.insertsql(ReadEnvironmentVars.read_config_file("MySQL"), sql, aplist)

def update_inventory_table(datetimenow, aplist):
    # Put into inventory table for availability dashboards
    sql = f"""INSERT INTO devnet_dashboards.inventory 
      (serial_number, mgmt_ip_address, hostname, model, source, do_ping, device_group) 
    VALUES (%s, %s, %s, %s, %s, 1, 'WirelessAP') 
    ON DUPLICATE KEY UPDATE serial_number=VALUES(serial_number), hostname=VALUES(hostname), 
      model=VALUES(model), source=VALUES(source), device_group='WirelessAP'
    """ 
    # Rearrange the aggregatelist to remove RadioMACAddress field[1] and EthernetMACAddress field[2]
    newagglist = []
    for aprow in aplist:
        newrow = (aprow[0],) + aprow[3:]
        #print(type(newrow))
        newagglist.append(tuple(newrow))
    
    InsertUpdateMySQL.insertsql(ReadEnvironmentVars.read_config_file("MySQL"), sql, newagglist)


def runjob():
    controllerlist = ReadEnvironmentVars.read_config_file("WLC")
    aggregatelist = []
    for controller in controllerlist:
        print(f"Processing Wireless LAN Controller (WLC) instance {controller['alias']} {controller['host']}...")
        thiscontrolleraps = extract_device_properties(controller['alias'], getWirelessAPData.getAPs(controller))
        aggregatelist.extend(thiscontrolleraps)
        print(f"  Got {len(thiscontrolleraps)} APs from {controller['alias']} {controller['host']}...")
        #print(thiscontrolleraps)
    #print(f'Aggregate List:\n{aggregatelist}')
    now = datetime.now()
    dtnow = now.strftime('%Y-%m-%d %H:%M:%S')

    # Put into WirelessAPs table for wireless dashboards
    update_wirelessaps_table(dtnow, aggregatelist)
    
    # Put into inventory table for availability dashboards
    update_inventory_table(dtnow, aggregatelist)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    start = datetime.now()
    print(f'\nRunning thread at {start.strftime("%H:%M:%S")}')
    job_thread.start()


## MAIN
if __name__ == "__main__":
    start = datetime.now()
    print(f'Started task at {start.strftime("%H:%M:%S")}')

    roomid = ReadEnvironmentVars.read_config_file('wirelessalerts_webexroomid')
    sendWebexMessage.sendMessage(roomid,'Starting putAPsIntoDB.py monitoring app...')
    runjob()

    schedule.every(120).seconds.do(run_threaded, runjob)
    print('\nRunning a sleep loop.', end='', flush=True)

    try:
        while True:
            print('.', end='', flush=True)
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        print('\nUser initiated stop - closing down process...')
        sendWebexMessage.sendMessage(roomid,'Stopping putAPsIntoDB.py monitoring app...')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)