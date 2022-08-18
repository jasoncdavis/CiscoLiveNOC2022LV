# PollAndReportWireless.py

# Executes the Wireless Client and AP polling, then runs the dashboard
#   creating the HTML
import sys, os
import time
from datetime import datetime
import sendWebexMessage
import schedule, threading
import ReadEnvironmentVars

import putClientsIntoDB
import putAPsIntoDB
import createWirelessClientDashboards

def runjob():
    print('\n###########################')
    print('## Running putClientsIntoDB')
    putClientsIntoDB.runjob()
    print('## Running putAPsIntoDB')
    putAPsIntoDB.runjob()
    print('## Running createWirelessClientDashboards')
    createWirelessClientDashboards.runjob()
    print('## Finished this sequence')


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
    sendWebexMessage.sendMessage(roomid,'Starting Wireless Collection and Reporting scripts...')

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
        sendWebexMessage.sendMessage(roomid,'Stopping Wireless Collection and Reporting scripts...')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)