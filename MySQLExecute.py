#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inserts or Updates entries in MySQL
 (MySQLExecute.py)

#                                                                      #
Receives MySQL server parameters and a list of dictionary items to
insert into MySQL inventory table.

Required inputs/variables:
    serverparams - dictionary of MySQL server parameters (eg. hostname,
        username, password, database name)
    sql_values - list of dictionary items reflecting device parameters
        to be updated/inserted into MySQL

Outputs:
    None

Version log:
v1      2021-0304   Ported from AO workflows to Python
v2      2021-0425   Refactored to enable for DevNet Automation Exchange
v3      2022-0512   Improved modularity to allow for SQL statement to be
            passed in as parameter

Credits:
"""
__version__ = '3'
__author__ = 'Jason Davis - jadavis@cisco.com'
__license__ = "Cisco Sample Code License, Version 1.1 - https://developer.cisco.com/site/license/cisco-sample-code-license/"

import sys
import MySQLdb

def executesql(serverparams, sql):
    """Insert update to MySQL database
    
    Receives server parameters and device parameters to insert into database, formats the entries as SQL and inserts into 'inventory' table
    
    :param serverparams: dictionary containing settings of the MySQL server [eg. host, database name, username, password,  etc.]
    :param sql_values: list of dictionary entries  representing Prime Infrastructure devices
    :returns: None
    """
    #print(serverparams)
    #print(sql)
    #print(sql_values)
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
        db.commit()
        cursor.close()
        db.close()

def main(serverparams, sql, deviceresults):
    executesql(serverparams, sql, deviceresults)

if __name__ == "__main__":
    main()