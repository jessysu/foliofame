

import datetime, time, pytz
import requests
from django.db import connection

from ff_app.utils import table_exist
import logging
import pymongo
logger = logging.getLogger(__name__)

utc = pytz.timezone('UTC')
eastern = pytz.timezone('US/Eastern')

IEX_REFRESH_TRADING = 60 # 1 minute refresh inside trading hours
IEX_REFRESH_CLOSE = 3600 # 1 hour refresh outside of trading hours

IEX_cache_all = {}


def execsql(ss, s):
    try:
        cur = connection.cursor()
        r = cur.execute(s)
        cur.close()
    except Exception as e:
        IEX_cache_all[ss]['chartStatus'] = 'finished'
        logger.exception("SQL error")
        raise e
    return r

def execsqlmany(ss, s, p):
    try:
        cur = connection.cursor()
        r = cur.executemany(s,p)
        cur.close()
    except Exception as e:
        IEX_cache_all[ss]['chartStatus'] = 'finished'
        logger.exception("SQL error")
        raise e
    return r

def assure_chart_table(ss):
    if not table_exist("ff_stock_all"):
        execsql(ss, "create table ff_stock_all (symbol varchar(10), close_date date, high float, low float, open float, close float, volume float, chgPct float)")
        execsql(ss, "create index ff_stock_all_i1 on ff_stock_all (symbol, close_date)")

def check_ss_format(ss):
    if not ss:
        return False
    if len(ss) > 5:
        return False
    return True

from threading import Lock
lock = Lock()
def cache_charts(ss, time_out_in_seconds=10, recheck_every=0.1):
    if ss not in IEX_cache_all:
        IEX_cache_all[ss] = {}
    
    enow = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)

    # up to date
    if 'chartUpdated' in IEX_cache_all[ss]:
        u = IEX_cache_all[ss]['chartUpdated']
        # hourly update
        if u.date() == enow.date() and u.hour == enow.hour:
            return True

    # yield to current fetching job, make sure it finishes
    if 'chartStatus' in IEX_cache_all[ss]:
        if IEX_cache_all[ss]['chartStatus'] == 'fetching':
            cnt = 0
            while cnt <= time_out_in_seconds:
                time.sleep(recheck_every)
                if IEX_cache_all[ss]['chartStatus'] == 'finished':
                    return True
                cnt += recheck_every
            # timed out, force re-cache next time
            IEX_cache_all[ss]['chartStatus'] = 'finished'
            IEX_cache_all[ss].pop('chartUpdated', None)
            return False
    
    # actual fetching
    IEX_cache_all[ss]['chartStatus'] = 'fetching'
    
    lock.acquire() 
    
    assure_chart_table(ss)
    r = requests.get("https://api.iextrading.com/1.0/stock/"+ss+"/chart/1y/")
    if r.status_code != 200:
        IEX_cache_all[ss]['chartStatus'] = 'finished'
        return False
    
    r = r.json()
    p = []
    for j in r:
        if 'date' in j and 'high' in j and 'low' in j and 'open' in j and 'close' in j and 'volume' in j and 'changePercent' in j:
            p.append((ss, j['date'], j['high'], j['low'], j['open'], j['close'], j['volume'], j['changePercent']))
    # wipe out today's entry from historical records, if IEX has already updated (depending on IEX's update timing)
    #if enow.hour < 9 or enow.hour > 20 or enow.date().weekday() > 4 :
    #    p = p[:-1]
    execsql(ss, "delete from ff_stock_all where symbol='"+ss+"'")
    if p:
        execsqlmany(ss, "insert into ff_stock_all (symbol, close_date, high, low, open, close, volume, chgPct) values (%s, %s, %s, %s, %s, %s, %s, %s)", p)

    IEX_cache_all[ss]['chartStatus'] = 'finished'
    IEX_cache_all[ss]['chartUpdated'] = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)
    
    lock.release()

    return True

def get_cache_all():
    return IEX_cache_all







#def vol_helper(ss):
    
