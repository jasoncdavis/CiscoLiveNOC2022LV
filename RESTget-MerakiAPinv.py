import requests
import ReadEnvironmentVars
import json
import sys
import InsertUpdateMySQLfull

merakienv = ReadEnvironmentVars.read_config_file('Meraki')

url = f'{merakienv["baseURL"]}/organizations/{merakienv["orgId"]}/inventory/devices?networkIds[]={merakienv["networkId"]}&productTypes[]=wireless'

payload={}
headers = {
  'X-Cisco-Meraki-API-Key': merakienv['APIkey']
}

response = requests.request("GET", url, headers=headers, data=payload)

#print(response.text)
aplist = json.loads(response.text)
#print(aplist)
agg_devicelist = []
for device in aplist:
    #print(device)
    url = f'{merakienv["baseURL"]}/devices/{device["serial"]}'
    print(url)
    response = requests.request("GET", url, headers=headers, data=payload)
    #print(response.text)
    devicejson = json.loads(response.text)

    # Structure as name, ip, serial, device_type "Meraki", device_group "WirelessAP",
    #   model, source "MerakiDashboardAPI", softwareversion, location, contacts "Wireless", 1
    device_entry = ((devicejson['name'], 
        devicejson['lanIp'],
        devicejson['serial'],
        'Meraki', 
        'WirelessAP',
        devicejson['model'],
        'MerakiDashboardAPI',
        'Locked - Up-to-date',
        'Four Seasons',
        'Wireless'
    ))
    #print(device_entry)
    agg_devicelist.append(device_entry)
print(agg_devicelist)

InsertUpdateMySQLfull.insertsql(ReadEnvironmentVars.read_config_file("MySQL"), agg_devicelist)

