import xml.etree.ElementTree as ET
import sys, os
import re
import time
from datetime import datetime
import ReadEnvironmentVars
import SelectFromMySQL
import json
import requests
import sendWebexMessage
import schedule, threading


MINTHRESHOLD = 60
HIGHTHRESHOLD = 75
MAX_ROW_CELL_COUNT = 15

def select_wireless_clients(mysqlenv):
    SQL = '''SELECT Controller, RadioPHYType, count(*) 
FROM WirelessClients 
WHERE SeenLastPoll = true 
GROUP BY Controller, RadioPHYType
ORDER BY Controller;
'''
    results = SelectFromMySQL.selectsql(mysqlenv, SQL)
    #print(results)
    
    lineentry = ''
    agg_entries = []
    current_controller = ''
    for entry in results:
        if current_controller != entry[0]:
            agg_entries.append(lineentry)
            ccount_ax5 = ccount_ax2 = ccount_ac = ccount_n5 = ccount_n24 = 0
            ccount_a = ccount_g = ccount_b = 0
            current_controller = entry[0]

        match entry[1]:
            case 'client-dot11ax-5ghz-prot':
                ccount_ax5 = entry[2]
            case 'client-dot11ax-24ghz-prot':
                ccount_ax2 = entry[2]
            case 'client-dot11ac':
                ccount_ac = entry[2]
            case 'client-dot11n-5-ghz-prot':
                ccount_n5 = entry[2]
            case 'client-dot11n-24-ghz-prot':
                ccount_n24 = entry[2]
            case 'client-dot11a':
                ccount_a = entry[2]
            case 'client-dot11g':
                ccount_g = entry[2]
            case 'client-dot11b':
                ccount_b = entry[2]
            # If an exact match is not confirmed, this last case will be used if provided
            case _:
                print(f'Ooops - got a {entry[1]}')
        lineentry = (f'''{{"controller": "{entry[0]}", \
"80211ax5-count": {ccount_ax5}, "80211ax2-count": {ccount_ax2}, \
"80211ac-count": {ccount_ac}, "80211n5-count": {ccount_n5}, \
"80211n24-count": {ccount_n24}, "80211a-count": {ccount_a}, \
"80211g-count": {ccount_g}, "80211b-count": {ccount_b}}}''')
        #print(lineentry)
    agg_entries.append(lineentry)
    agg_entries.pop(0)
    #print(agg_entries)
    return(agg_entries)


def format_to_influx_lineprotocol(clientcounts):
    measurements = ''
    for entry in clientcounts:
        #print(entry)
        entryjson = json.loads(entry)
        #print(entryjson["controller"])
        #print(entryjson["80211ac-count"])
        measurement = f'wirelessclientcounts,controller={entryjson["controller"]} \
80211ax5-count={entryjson["80211ax5-count"]},\
80211ax2-count={entryjson["80211ax2-count"]},\
80211ac-count={entryjson["80211ac-count"]},\
80211n5-count={entryjson["80211n5-count"]},\
80211n24-count={entryjson["80211n24-count"]},\
80211a-count={entryjson["80211a-count"]},\
80211g-count={entryjson["80211g-count"]},\
80211b-count={entryjson["80211b-count"]}'
        #print(measurement)
        measurements += measurement + '\n'
    #print(measurements)
    return(measurements)

def put_wireless_stats_in_influx(influxenv, clientcounts):
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:\
{influxenv["port"]}/api/v2/write?bucket={influxenv["influxbucket"]}&\
org={influxenv["influxorg"]}&precision=s'

    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    print('Sending wireless client data to Influx')
    response = requests.request("POST", influxurl, headers=headers, data=clientcounts)
    print(f'{response.status_code} - {response.reason} - {response.text}')


def createWirelessRadioDistribution(wirelessdashboarddir, clientcounts):
    #print(clientcounts)
    total_80211ax5_count = total_80211ax2_count = total_80211ac_count = \
    total_80211n5_count = total_80211n24_count = totla_80211a_count = \
    total_80211g_count = total_80211b_count = total_all_clients = 0

    f = open("TEMPLATE-CLstats-WirelessClientRadio.html", "r")
    htmltemplate = f.read()
    #print(htmltemplate)
    for entry in clientcounts:
        #print(entry)
        clientassociations = json.loads(entry)
        controller = clientassociations["controller"]
        clientassociations.pop('controller')
        totalclients = sum(clientassociations.values())
        #print(totalclients)
        total_all_clients += totalclients
        RATIOAX5 = f'{(clientassociations["80211ax5-count"] / totalclients) * 100:.1f}'
        RATIOAX24 = f'{(clientassociations["80211ax2-count"] / totalclients)*100:.1f}'
        RATIOAC = f'{(clientassociations["80211ac-count"] / totalclients)*100:.1f}'
        RATION5 = f'{(clientassociations["80211n5-count"] / totalclients)*100:.1f}'
        RATION24 = f'{(clientassociations["80211n24-count"] / totalclients)*100:.1f}'
        RATIOA = f'{(clientassociations["80211a-count"] / totalclients)*100:.1f}'
        RATIOG = f'{(clientassociations["80211g-count"] / totalclients)*100:.1f}'
        RATIOB = f'{(clientassociations["80211b-count"] / totalclients)*100:.1f}'

        print(f'Wireless client ratios: ', end='')
        print(RATIOAX5, RATIOAX24, RATIOAC, RATION5, RATION24, RATIOA, RATIOG, RATIOB)

        html = htmltemplate.replace('###CONTROLLER###',controller)
        html = html.replace('###TOTALCLIENTS###',str(totalclients))
        html = html.replace('###RATIOAX5###',str(RATIOAX5))
        html = html.replace('###COUNTAX5###',str(clientassociations["80211ax5-count"]))
        html = html.replace('###RATIOAX24###',str(RATIOAX24))
        html = html.replace('###COUNTAX24###',str(clientassociations["80211ax2-count"]))
        html = html.replace('###RATIOAC###',str(RATIOAC))
        html = html.replace('###COUNTAC###',str(clientassociations["80211ac-count"]))
        html = html.replace('###RATION5###',str(RATION5))
        html = html.replace('###COUNTN5###',str(clientassociations["80211n5-count"]))
        html = html.replace('###RATION24###',str(RATION24))
        html = html.replace('###COUNTN24###',str(clientassociations["80211n24-count"]))
        html = html.replace('###RATIOA###',str(RATIOA))
        html = html.replace('###COUNTA###',str(clientassociations["80211a-count"]))
        html = html.replace('###RATIOG###',str(RATIOG))
        html = html.replace('###COUNTG###',str(clientassociations["80211g-count"]))
        html = html.replace('###RATIOB###',str(RATIOB))
        html = html.replace('###COUNTB###',str(clientassociations["80211b-count"]))
        html = html.replace('###RUNDATETIME###', f'{datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S")}')

        #print(html)
        f = open(f'{wirelessdashboarddir}/CLstats-WirelessClientRadio-{controller}.html', "w")
        f.write(html)
        f.close()

        # Also do cumulative dashboard CLstats-WirelessClientRadio-ALL.html

def createWirelessClientDistribution(wirelessdashboarddir, sqlenv, controller):
    # Wireless Client Distribution of SSID and RadioPHYType
    f = open("TEMPLATE-CLstats-WirelessClientSSIDRadio.html", "r")
    htmltemplate = f.read()

    print('Getting wireless client SSID and RadioPHY mapping')
    SQL = f'''SELECT SSID, RadioPHYType, count(*) 
    FROM WirelessClients 
    WHERE SeenLastPoll = true AND Controller = "{controller}" 
    GROUP BY SSID, RadioPHYType
    ORDER BY SSID;'''

    results = SelectFromMySQL.selectsql(sqlenv, SQL)
    #print(results)
    ssidrowhtmltemplate = '''       <tr>
		<td class="label"> ###SSID###</td>
		<td>
		<table class="bar">
			<tr>
            <!-- Remove if Wi-Fi 6 is in the venue
				<td class="ax5-80211" style="width: 15%;">###COUNTAX5###</td>
				<td class="ax24-80211" style="width: 15%;">###COUNTAX24###</td>
            -->    
				<td class="ac-80211" style="width: 10%;">###COUNTAC###</td>
				<td class="n5-80211" style="width: 10%;">###COUNTN5###</td>
				<td class="n24-80211" style="width: 10%;">###COUNTN24###</td>
				<td class="g-80211" style="width: 5%;">###COUNTG###</td>
				<td class="a-80211" style="width: 5%;">###COUNTA###</td>
				<td class="b-80211" style="width: 5%;">###COUNTB###</td>
			</tr>
		</table>
		</td>
	</tr>'''

    totalclients = 0
    previousSSID = ''
    cumulativerows = ''
    radioPHYb = radioPHYg = radioPHYa = radioPHYn24 = radioPHYn5 = \
        radioPHYac = radioPHYax24 = radioPHYax5 = 0
    sensitiveSSIDs = ['noc', 'abracadabra']


    for ssidrow in results:
        #print(f'Working on - {ssidrow}')
        #print(f'ssidrow0 is {ssidrow[0]} and previousSSID is {previousSSID}')
        if ssidrow[0] == previousSSID or previousSSID == '':
            #print(f'Fell through - now matching on {ssidrow[1]}')
            match ssidrow[1]:
                case 'client-dot11b':
                    radioPHYb = ssidrow[2]
                case 'client-dot11g':
                    radioPHYg = ssidrow[2]
                case 'client-dot11a':
                    radioPHYa = ssidrow[2]
                case 'client-dot11n-24-ghz-prot':
                    radioPHYn24 = ssidrow[2]
                case 'client-dot11n-5-ghz-prot':
                    radioPHYn5 = ssidrow[2]
                case 'client-dot11ac':
                    radioPHYac = ssidrow[2]
                case 'client-dot11ax-24ghz-prot':
                    radioPHYax24 = ssidrow[2]
                case 'client-dot11ax-5ghz-prot':
                    radioPHYax5 = ssidrow[2]
            previousSSID = ssidrow[0]
        else:
            #print(f'Got a new ssid - must print prior results')
            #print(radioPHYb, radioPHYg, radioPHYa, radioPHYn24, radioPHYn5, \
            #    radioPHYac, radioPHYax24, radioPHYax5)

            # Hide 'sensitive' SSIDs
            if previousSSID in sensitiveSSIDs:
                previousSSID = '[hidden]'

            ssidrowhtml = ssidrowhtmltemplate.replace('###SSID###',previousSSID)
            ssidrowhtml = ssidrowhtml.replace('###COUNTAX5###',str(radioPHYax5))
            ssidrowhtml = ssidrowhtml.replace('###COUNTAX24###',str(radioPHYax24))
            ssidrowhtml = ssidrowhtml.replace('###COUNTAC###',str(radioPHYac))
            ssidrowhtml = ssidrowhtml.replace('###COUNTN5###',str(radioPHYn5))
            ssidrowhtml = ssidrowhtml.replace('###COUNTN24###',str(radioPHYn24))
            ssidrowhtml = ssidrowhtml.replace('###COUNTA###',str(radioPHYa))
            ssidrowhtml = ssidrowhtml.replace('###COUNTG###',str(radioPHYg))
            ssidrowhtml = ssidrowhtml.replace('###COUNTB###',str(radioPHYb))
            #print(ssidrowhtml)
            cumulativerows += ssidrowhtml

            totalclients += radioPHYax5 + radioPHYax24 + radioPHYac + \
                radioPHYn5 + radioPHYn24 + radioPHYa + radioPHYg + radioPHYb

            #print(f'Now doing new compares for {ssidrow[0]}')
            radioPHYb = radioPHYg = radioPHYa = radioPHYn24 = radioPHYn5 = \
                radioPHYac = radioPHYax24 = radioPHYax5 = 0
            match ssidrow[1]:
                case 'client-dot11b':
                    radioPHYb = ssidrow[2]
                case 'client-dot11g':
                    radioPHYg = ssidrow[2]
                case 'client-dot11a':
                    radioPHYa = ssidrow[2]
                case 'client-dot11n-24-ghz-prot':
                    radioPHYn24 = ssidrow[2]
                case 'client-dot11n-5-ghz-prot':
                    radioPHYn5 = ssidrow[2]
                case 'client-dot11ac':
                    radioPHYac = ssidrow[2]
                case 'client-dot11ax-24ghz-prot':
                    radioPHYax24 = ssidrow[2]
                case 'client-dot11ax-5ghz-prot':
                    radioPHYax5 = ssidrow[2]
            previousSSID = ssidrow[0]
    #print(radioPHYb, radioPHYg, radioPHYa, radioPHYn24, radioPHYn5, \
    #    radioPHYac, radioPHYax24, radioPHYax5)

    # Hide 'sensitive' SSIDs
    if ssidrow[0] in sensitiveSSIDs:
        ssidlabel = '[hidden]'
    else:
        ssidlabel = ssidrow[0]

    ssidrowhtml = ssidrowhtmltemplate.replace('###SSID###',ssidlabel)
    ssidrowhtml = ssidrowhtml.replace('###COUNTAX5###',str(radioPHYax5))
    ssidrowhtml = ssidrowhtml.replace('###COUNTAX24###',str(radioPHYax24))
    ssidrowhtml = ssidrowhtml.replace('###COUNTAC###',str(radioPHYac))
    ssidrowhtml = ssidrowhtml.replace('###COUNTN5###',str(radioPHYn5))
    ssidrowhtml = ssidrowhtml.replace('###COUNTN24###',str(radioPHYn24))
    ssidrowhtml = ssidrowhtml.replace('###COUNTA###',str(radioPHYa))
    ssidrowhtml = ssidrowhtml.replace('###COUNTG###',str(radioPHYg))
    ssidrowhtml = ssidrowhtml.replace('###COUNTB###',str(radioPHYb))
    #print(ssidrowhtml)
    cumulativerows += ssidrowhtml

    totalclients += radioPHYax5 + radioPHYax24 + radioPHYac + \
        radioPHYn5 + radioPHYn24 + radioPHYa + radioPHYg + radioPHYb

    #print(cumulativerows)    

    html = htmltemplate.replace('###TOTALCLIENTS###',str(totalclients))
    html = html.replace('###CONTROLLER###',controller)
    html = html.replace('###SSIDTABLE###',cumulativerows)
    html = html.replace('###RUNDATETIME###', f'{datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S")}')


    #print(html)
    f = open(f'{wirelessdashboarddir}/CLstats-WirelessClientSSIDRadio-{controller}.html', "w")
    f.write(html)
    f.close()


def createWirelessAPClientLoad(wirelessdashboarddir, sqlenv):
    # Data to collect
    #   TOtal clients
    #   Total APs online / configured / down
    #   APs < 60 clients (lime)
    #   APs < 75 & >= 60 clients
    #   APs >= 75 clients

    SQL = '''SELECT APMACAddress,count(*) 
    FROM WirelessClients 
    WHERE SeenLastPoll = true 
    GROUP BY APMACAddress
    ORDER BY count(*) DESC;
    '''
    apclientcounts = SelectFromMySQL.selectsql(sqlenv, SQL)
    #print(apclientcounts)
    totalaps = len(apclientcounts)

    print(f'Total APs: {totalaps}')
    # Data to collect
    #   TOtal clients
    #   Total APs online / configured / down
    #   APs < 60 clients (lime)
    #   APs < 75 & >= 60 clients
    #   APs >= 75 clients

    print('Collecting Show-wide AP count...')
    APSQL = '''SELECT EthernetMACAddress, Name, Model from WirelessAPs'''
    APlist = SelectFromMySQL.selectsql(sqlenv, APSQL)
    #print(APlist)

    f = open("TEMPLATE-CLstats-WirelessAPLoad.html", "r")
    htmltemplate = f.read()

    apentries = '\t<tr>\n'
    underthreshold = 0
    midthreshold = 0
    overthreshold = 0
    totalclients = 0

    for count, value in enumerate(apclientcounts, start=1):
        apmac = value[0]
        clientcount = value[1]
        totalclients += clientcount
        apname = [item[1] for item in APlist if apmac == item[0]][0]
        apmodel = [item[2] for item in APlist if apmac == item[0]][0]
        #print(apname, apmodel, clientcount)
        if clientcount < MINTHRESHOLD:
            bgcolor = 'lime'
            textcolor = 'black'
            apentry = f'''			<td bgcolor="lime"><font color="black">{apname}<br />
        {apmodel}<br />
        2.4GHz: 0<br />
        5GHz: {clientcount}</font></td>'''
            underthreshold += 1
        elif clientcount < HIGHTHRESHOLD and clientcount > MINTHRESHOLD:
            bgcolor = 'yellow'
            textcolor = 'black'
            apentry = f'''			<td bgcolor="yellow"><font color="black">{apname}<br />
        {apmodel}<br />
        2.4GHz: 0<br />
        5GHz: {clientcount}</font></td>'''
            midthreshold += 1
        else:
            bgcolor = 'red'
            textcolor = 'white'
            apentry = f'''			<td bgcolor="orange"><font color="black">{apname}<br />
        {apmodel}<br />
        2.4GHz: 0<br />
        5GHz: {clientcount}</font></td>'''
            overthreshold += 1
        #print(apentry)
        apentries += apentry
        # Check if we need to start a new row
        if count % MAX_ROW_CELL_COUNT == 0:
            apentries += '\n\t\t</tr>\n\t\t<tr>\n'
    apentries += '\n\t\t</tr>'

    #print(apentries)
    html = htmltemplate.replace('###TABLEROWS###',apentries)

    # Other fixups
    ## Client count
    print(f'Total venue Wireless Client count: {totalclients}')
    html = html.replace('###TOTALCLIENTCOUNT###',str(totalclients))

    ## AP Count - should be sum of all currently reachable APs
    SQL = '''SELECT count(WirelessAPs.IPAddress)
    FROM WirelessAPs
    LEFT JOIN pingresults ON WirelessAPs.IPAddress = pingresults.mgmt_ip_address
    WHERE pingresults.reachable_pct > 0;
    '''
    aps_up = SelectFromMySQL.selectsql(sqlenv, SQL)[0][0]
    print(f'Count of APs Up: {aps_up}')
    html = html.replace('###APSUPCOUNT###',str(aps_up))

    SQL = '''SELECT NAME 
    FROM WirelessAPs where IPAddress IN (
      SELECT WirelessAPs.IPAddress
      FROM WirelessAPs
      LEFT JOIN pingresults ON WirelessAPs.IPAddress = pingresults.mgmt_ip_address
      WHERE pingresults.reachable_pct > 0 )
      
    '''
    aps_up = SelectFromMySQL.selectsql(sqlenv, SQL)[0][0]
    upap_list = []
    for upap in aps_up:
        upap_list.append(upap[0])
    #print(f'Names of APs Up: {upap_list}')

    ## APs Configured Count - should be sum of all entries in MySQL
    ##   inventory table that are 'WirelessAP'
    ###APSCONFIGURED###
    SQL = '''select count(hostname) from inventory where device_group = 'WirelessAP';
    '''
    apcount = SelectFromMySQL.selectsql(sqlenv, SQL)[0][0]
    print(f'AP Count: {apcount}')
    html = html.replace('###APSCONFIGURED###',str(apcount))

    
    ###RED###   or APs down
    SQL = '''SELECT count(WirelessAPs.IPAddress)
    FROM WirelessAPs
    LEFT JOIN pingresults ON WirelessAPs.IPAddress = pingresults.mgmt_ip_address
    WHERE pingresults.reachable_pct = 0;
    '''
    aps_down = SelectFromMySQL.selectsql(sqlenv, SQL)[0][0]
    print(f'Count of APs Down: {aps_down}')
    html = html.replace('###APSDOWNCOUNT###',str(aps_down))


    SQL = '''SELECT NAME 
    FROM WirelessAPs where IPAddress IN (
      SELECT WirelessAPs.IPAddress
      FROM WirelessAPs
      LEFT JOIN pingresults ON WirelessAPs.IPAddress = pingresults.mgmt_ip_address
      WHERE pingresults.reachable_pct = 0 )
      
    '''
    aps_down = SelectFromMySQL.selectsql(sqlenv, SQL)
    downap_list = []
    for downap in aps_down:
        downap_list.append(downap[0])
    #print(f'Names of APs Down: {downap_list}')

    ###GREEN### ap count <minthresh
    html = html.replace('###GREEN###',str(underthreshold))

    ###YELLOW### ap count in midrange
    html = html.replace('###YELLOW###',str(midthreshold))
    
    ###ORANGE### ap count in highrange
    html = html.replace('###ORANGE###',str(overthreshold))
    
    ###JOBRUNTIME###
    html = html.replace('###RUNDATETIME###', f'{datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S")}')


    #print(html)
    #print(html)
    #f = open(f'{wirelessdashboarddir}/CLstats-WirelessAPLoad-{controller}.html', "w")
    f = open(f'{wirelessdashboarddir}/CLstats-WirelessAPLoad.html', "w")
    f.write(html)
    f.close()


def runjob():
    mysqlenv = ReadEnvironmentVars.read_config_file("MySQL")
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    wirelessdashboarddir = ReadEnvironmentVars.read_config_file("WirelessDashboardDirectory")

    # Process stats for Grafana Wireless dashboards
    clientcounts = select_wireless_clients(mysqlenv)
    #print(clientcounts)
    clients_lineprotocol = format_to_influx_lineprotocol(clientcounts)
    #print(clients_lineprotocol)
    put_wireless_stats_in_influx(influxenv, clients_lineprotocol)

    #Wireless Radio Distribution
    createWirelessRadioDistribution(wirelessdashboarddir, clientcounts)

    #Wireless Client Distribution
    createWirelessClientDistribution(wirelessdashboarddir, mysqlenv, 'CLUS-KNWLC-SSO-1')
    createWirelessClientDistribution(wirelessdashboarddir, mysqlenv, 'CLUS-WLC-SSO-1')

    #AP Client Load
    createWirelessAPClientLoad(wirelessdashboarddir, mysqlenv)


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
    sendWebexMessage.sendMessage(roomid,'Starting createWirelessClientDashboards.py monitoring app...')
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
        sendWebexMessage.sendMessage(roomid,'Stopping createWirelessClientDashboards.py monitoring app...')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)