# getWirelessAPData.py

# Helper program
# Used by putAPsIntoDB.py

from unicodedata import name
from ncclient import manager
import xml.etree.ElementTree as ET
import sys
import re
import time
from datetime import datetime
import ReadEnvironmentVars


def strip_ns(xml_string):
    return re.sub('xmlns="[^"]+"', '', xml_string)

def getAPs(controller):
    capwap_filter = '''<filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
            <access-point-oper-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-wireless-access-point-oper">
                <capwap-data>
                <wtp-mac/>
                <ip-addr/>
                <name/>
                <device-detail>
                    <static-info>
                    <board-data>
                        <wtp-serial-num/>
                        <wtp-enet-mac/>
                    </board-data>
                    <ap-models>
                        <model/>
                    </ap-models>
                    </static-info>
                </device-detail>
                </capwap-data>
            </access-point-oper-data>
        </filter>
    '''

    with manager.connect(host=controller['host'], port=830, username=controller['username'], password=controller['password'], hostkey_verify=controller['CheckSSLCert']) as ncsession:
        ncreply = ncsession.get(capwap_filter).data_xml
        ncreply_nons = strip_ns(ncreply)
        xmldata = ET.fromstring(ncreply_nons).findall(".//capwap-data")

        aprecords = '{"wireless-aps":['
        for ap in xmldata:
            aprecord = (f'{{ "wtp-serial-num": "{ap.find("device-detail/static-info/board-data/wtp-serial-num").text}",'
            f'"wtp-mac": "{ap.find("wtp-mac").text}",'
            f'"ip-addr": "{ap.find("ip-addr").text}",'
            f'"name": "{ap.find("name").text}",'
            f'"wtp-enet-mac": "{ap.find("device-detail/static-info/board-data/wtp-enet-mac").text}",'
            f'"model": "{ap.find("device-detail/static-info/ap-models/model").text}"}}')
            if ap != xmldata[-1]:
                aprecord += ','
            aprecords += aprecord

        aprecords += ']}'
        #print(repr(aprecords))
        return(aprecords)

if __name__ == "__main__":
    start = datetime.now()
    print(f'Started task at {start.strftime("%H:%M:%S")}')
    controllerlist = ReadEnvironmentVars.read_config_file("WLC")
    aggregatelist = []
    deviceresults = []
    for controller in controllerlist:
        print(f"Processing Wireless LAN Controller (WLC) instance {controller['alias']} {controller['host']}...")
        thiscontrollerAPs = getAPs(controller)
        #print(f"  Got {len(thiscontrollerAPs)} APs from {controller['alias']} {controller['host']}...")
        #aggregatelist.extend(thiscontrollerAPs)
    #print(f'Aggregate List:\n{aggregatelist}')

    end = datetime.now()
    print(f'Ended task at {end.strftime("%H:%M:%S")}\nTotal runtime: {end - start}')

