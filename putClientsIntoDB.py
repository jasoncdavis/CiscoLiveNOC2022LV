import xml.etree.ElementTree as ET
import sys, os
import re
import time
from datetime import datetime
import ReadEnvironmentVars
import getWirelessClientData
import json
import InsertUpdateMySQL, MySQLExecute
import sendWebexMessage
import schedule, threading

def extract_device_properties(controller, clients):
    """Extract devices properties from JSON string
    
    Reads device inventory as JSON, extracts the fields needed to add as inventory into MySQL
    
    :param server: dictionary containing settings of the WLC being polled [eg. host, username, password,  etc.]
    :param deviceinventory: string of JSON text representing WLC clients in a list
    :returns: list of dictionary entries representing client parameters
    """
    #print(type(clients))
    #print(clients)
    clientlist=[]
    clients_json = json.loads(clients)
    for client in clients_json["wireless-clients"]:
        MACAddress = client['ms-mac-address']
        APMACAddress = client['ap-mac-address']
        Channel = client['current-channel']
        SSID = client['vap-ssid']
        RadioType = client['radio-type']
        RadioPHYType = client['ewlc-ms-phy-type']
        clientlist.append((MACAddress, APMACAddress, Channel, SSID, RadioType, RadioPHYType, controller))
    return clientlist


def runjob():
    controllerlist = ReadEnvironmentVars.read_config_file("WLC")
    aggregatelist = []
    for controller in controllerlist:
        print(f"Processing Wireless LAN Controller (WLC) instance {controller['alias']} {controller['host']}...")
        thiscontrollerclients = extract_device_properties(controller['alias'], getWirelessClientData.getClients(controller))
        aggregatelist.extend(thiscontrollerclients)
        print(f"  Got {len(thiscontrollerclients)} Clients from {controller['alias']} {controller['host']}...")
    #print(f'Aggregate List:\n{aggregatelist}')
    now = datetime.now()
    dtnow = now.strftime('%Y-%m-%d %H:%M:%S')

    # Need to add MySQL update to zilch 'SeenLast' to false for ALL entries before running next step
    sql = f"""Update devnet_dashboards.WirelessClients 
SET SeenLastPoll = 0 
WHERE SeenLastPoll = 1 
LIMIT 100000;
    """
    print('Clearing SeenLastPoll column of WirelessClients table')
    MySQLExecute.executesql(ReadEnvironmentVars.read_config_file("MySQL"), sql)

    print('Updating WirelessClients table with latest results')
    sql = f"""INSERT INTO devnet_dashboards.WirelessClients 
      (MACAddress, APMACAddress, Channel, SSID, RadioType, RadioPHYType, SeenCount, 
      SeenLastDateTime, SeenLastPoll, Controller) 
    VALUES (%s, %s, %s, %s, %s, %s, 1, "{dtnow}", true, %s) 
    ON DUPLICATE KEY UPDATE APMACAddress=VALUES(APMACAddress), Channel=VALUES(Channel), 
      SSID=VALUES(SSID), RadioType=VALUES(RadioType), RadioPHYType=VALUES(RadioPHYType), 
      SeenCount=SeenCount+1, SeenLastDateTime="{dtnow}", SeenLastPoll=true, Controller=VALUES(Controller)
    """ 
    #print(sql)
    #print(aggregatelist)
    InsertUpdateMySQL.insertsql(ReadEnvironmentVars.read_config_file("MySQL"), sql, aggregatelist)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    start = datetime.now()
    print(f'\nRunning thread at {start.strftime("%H:%M:%S")}')
    job_thread.start()


if __name__ == "__main__":
    start = datetime.now()
    print(f'Started task at {start.strftime("%H:%M:%S")}')

    roomid = ReadEnvironmentVars.read_config_file('wirelessalerts_webexroomid')
    sendWebexMessage.sendMessage(roomid,'Starting putClientsIntoDB.py monitoring app...')
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
        sendWebexMessage.sendMessage(roomid,'Stopping putClientsIntoDB.py monitoring app...')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

    #end = datetime.now()
    #print(f'Ended task at {end.strftime("%H:%M:%S")}\nTotal runtime: {end - start}')
