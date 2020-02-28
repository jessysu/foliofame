# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 20:44:57 2017

@author: jsu
"""

import bs4 as bs
import requests
import datetime
from util_mysql import table_exist, runsql, fetch_rawsql, dbcommit, dbclose
from util_logging import Log

def assure_required_table():
    print("checking")
    if not table_exist("ff_scan_symbols"):
        print("table ff_scan_symbols not exist; creating...")
        runsql("create table ff_scan_symbols (symbol varchar(10), last_updated datetime, last_scanned datetime, security varchar(100), sector varchar(100), subsec varchar(200), hq varchar(200), first_added datetime)")


def refresh_sp500():
    assure_required_table()
    print("fetching sp500 list...")
    resp = requests.get('http://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    soup = bs.BeautifulSoup(resp.text, 'html5lib')
    table = soup.find('table', {'class': 'wikitable sortable'})
    for row in table.findAll('tr')[1:]:
        r = row.findAll('td')
        #ticker = r[1].text.rstrip()
        ticker = r[0].text.rstrip()
        #print("working on "+ticker+"...")
        Log.info("SP500", "working on "+ticker+"...")
        check = fetch_rawsql("select symbol from ff_scan_symbols where symbol='"+ticker+"'")
        if len(check)>0:
            rawsql = "update ff_scan_symbols set last_updated=now() WHERE symbol='"+ticker+"'"
            runsql(rawsql)
        else:
            rawsql = "insert into ff_scan_symbols (symbol, last_updated, security, sector, subsec, hq, first_added) values (%s, %s, %s, %s, %s, %s, %s)"
            val = (ticker, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r[0].text, r[3].text, r[4].text, r[5].text, (r[6].text if r[6].text and len(r[6].text)==10 else None))
            runsql(rawsql, val)
    dbcommit()
    

if __name__ == "__main__":
    refresh_sp500()
    dbclose()


