#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Selects entries from MySQL
 (SelectFromMySQL.py)

#                                                                      #
Receives MySQL server parameters and an SQL query to MySQL.

Required inputs/variables:
    serverparams - dictionary of MySQL server parameters (eg. hostname,
        username, password, database name)
    sql - SQL reflecting select statement to run with MySQL server

Outputs:
    None

Version log:
v1      2022-0513   Created new as part of refactoring of CiscoLive 22

Credits:
"""
__version__ = '1'
__author__ = 'Jason Davis - jadavis@cisco.com'
__license__ = "Cisco Sample Code License, Version 1.1 - https://developer.cisco.com/site/license/cisco-sample-code-license/"

from socketserver import StreamRequestHandler
import sys
import MySQLdb
import ReadEnvironmentVars

def selectsql(serverparams, sql):
    """Select from MySQL database
    
    Receives server parameters and SQL statement parameters to send to database.
    
    :param serverparams: dictionary containing settings of the MySQL server [eg. host, database name, username, password,  etc.]
    :param sql: string of SQL statement/command
    :returns: None
    """
    #print(serverparams)
    #print(sql)
    try:
        db=MySQLdb.connect(host=serverparams["host"],user=serverparams["username"], 
            passwd=serverparams["password"],db=serverparams["database"])
    except MySQLdb.OperationalError as e:
        print("OperationalError")
        print(e)
        sys.exit(f'Check optionsconfig.yaml file for misconfiguration')
    except:
        sys.exit("Unknown error occurred")

    cursor=db.cursor()
    
    #SQL = f"""INSERT INTO {serverparams["database"]}.inventory (hostname, mgmt_ip_address, device_type, 
    #  device_group, source, do_ping) 
    #VALUES (%s, %s, %s, %s, %s, %s) 
    #ON DUPLICATE KEY UPDATE hostname=VALUES(hostname), device_type=VALUES(device_type), 
    #  device_group=VALUES(device_group), source=VALUES(source)
    #""" 
    
    try:
        cursor.execute(sql)
    except MySQLdb.DataError as e:
        sys.exit(f'DataError - {str(e)}')
    except MySQLdb.InternalError as e:
        sys.exit(f'InternalError - {str(e)}')
    except MySQLdb.IntegrityError as e:
        sys.exit(f'IntegrityError - {str(e)}')
    except MySQLdb.OperationalError as e:
        sys.exit(f'OperationalError - {str(e)}')
    except MySQLdb.NotSupportedError as e:
        sys.exit(f'NotSupportedError - {str(e)}')
    except MySQLdb.ProgrammingError as e:
        sys.exit(f'ProgrammingError - {str(e)}')
    except:
        sys.exit('Unknown error occurred')
    finally:
        print(f'Number of database records affected: {str(cursor.rowcount)}')
        rows = cursor.fetchall()
        #print(rows)
        return(rows)
        #db.commit()
        cursor.close()
        db.close()


if __name__ == "__main__":
    sql = '''select RadioPHYType,count(*) from WirelessClients where SeenLastPoll = true group by RadioPHYType;
    '''
    selectsql(ReadEnvironmentVars.read_config_file("MySQL"), sql)