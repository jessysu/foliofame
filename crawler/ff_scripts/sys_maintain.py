# -*- coding: utf-8 -*-
"""
Created on Fri Feb 22 22:55:32 2019

@author: pocos
"""

import datetime, time, pytz
from dateutil.relativedelta import relativedelta

from util_mysql import table_exist, runsql, dbcommit, getcur

utc = pytz.timezone('UTC')
eastern = pytz.timezone('US/Eastern')


def backup_table(tb, d=3, w=2, m=2):
    if not table_exist(tb):
        print("Backup source "+tb+" does not exist")
        return False
    cdate = utc.localize(datetime.datetime.utcnow()).astimezone(eastern).date()
    if d:
        tname = tb + "_bck" + cdate.strftime('%Y%m%d')
        runsql("drop table if exists "+tname)
        runsql("create table "+tname+" as select * from "+tb)
        cur = getcur()
        cur.execute("show tables like '" + tb + "_bck________'")
        T = [t[0] for t in cur.fetchall()]
        for t in T[:-d]:
            runsql("drop table "+t)
        print("..Backup + cleanup "+tb+" daily ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

    if w:
        tname = tb + "_bck" + cdate.strftime('%Yw%W')
        runsql("drop table if exists "+tname)
        runsql("create table "+tname+" as select * from "+tb)
        cur = getcur()
        cur.execute("show tables like '" + tb + "_bck____w__'")
        T = [t[0] for t in cur.fetchall()]
        for t in T[:-w]:
            runsql("drop table "+t)
        print("..Backup + cleanup "+tb+" weekly ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

    if m:
        tname = tb + "_bck" + cdate.strftime('%Ym%m')
        runsql("drop table if exists "+tname)
        runsql("create table "+tname+" as select * from "+tb)
        cur = getcur()
        cur.execute("show tables like '" + tb + "_bck____m__'")
        T = [t[0] for t in cur.fetchall()]
        for t in T[:-m]:
            runsql("drop table "+t)
        print("..Backup + cleanup "+tb+" monthly ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

    dbcommit()
    print("Successfully backed up "+tb)
    return True

def maintain_tasks():
    backup_table("ff_status_scan", d=3, w=3, m=3)
    
if __name__ == '__main__':
    maintain_tasks()
