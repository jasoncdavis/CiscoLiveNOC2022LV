# getWirelessClientData.py

# Helper program
# Used by putClientsIntoDB.py

from unicodedata import name
from ncclient import manager
import xml.etree.ElementTree as ET
import sys
import re
import time
from datetime import datetime


def strip_ns(xml_string):
    return re.sub('xmlns="[^"]+"', '', xml_string)

def getClients(controller):
    wirelessclient_filter = '''
    <filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
      <client-oper-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-wireless-client-oper">
        <dot11-oper-data>
          <ms-mac-address/>
          <ap-mac-address/>
          <current-channel/>
          <vap-ssid/>
          <radio-type/>
          <ewlc-ms-phy-type/>
        </dot11-oper-data>
      </client-oper-data>
    </filter>
    '''

    with manager.connect(host=controller['host'], port=830, username=controller['username'], password=controller['password'], hostkey_verify=controller['CheckSSLCert']) as ncsession:
        ncreply = ncsession.get(wirelessclient_filter).data_xml
        ncreply_nons = strip_ns(ncreply)
        xmldata = ET.fromstring(ncreply_nons).findall(".//dot11-oper-data")

        clientrecords = '{"wireless-clients":['
        for client in xmldata:
            clientrecord = (f'{{ "ms-mac-address": "{client.find("ms-mac-address").text}",'
            f'"ap-mac-address": "{client.find("ap-mac-address").text}",'
            f'"current-channel": "{client.find("current-channel").text}",'
            f'"vap-ssid": "{client.find("vap-ssid").text}",'
            f'"radio-type": "{client.find("radio-type").text}",'
            f'"ewlc-ms-phy-type": "{client.find("ewlc-ms-phy-type").text}"}}')
            if client != xmldata[-1]:
                clientrecord += ','
            #print(repr(clientrecord))
            clientrecords += clientrecord

        clientrecords += ']}'
        return(clientrecords)

if __name__ == "__main__":
    start = datetime.now()
    print(f'Started task at {start.strftime("%H:%M:%S")}')
    print(getClients())
    end = datetime.now()
    print(f'Ended task at {end.strftime("%H:%M:%S")}\nTotal runtime: {end - start}')

