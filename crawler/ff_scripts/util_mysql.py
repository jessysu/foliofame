# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 16:55:38 2017

@author: jsu
"""

#pip install mysqlclient
#import MySQLdb
import mysql.connector as dbc
from static import DB, ForceRefreshTable
from util_logging import Log

db = dbc.connect(host=DB['host'], user=DB['user'], passwd=DB['passwd'], db=DB['db'], use_unicode=True, charset="utf8", collation="utf8_unicode_ci")
#db.set_character_set('utf8')
db.cursor().execute('SET NAMES utf8 COLLATE utf8_unicode_ci;')
db.cursor().execute('SET CHARACTER SET utf8;')
db.cursor().execute('SET character_set_connection=utf8;')
db.cursor().execute('set global group_concat_max_len=256;')
db.cursor().execute('set group_concat_max_len=256;')

#cur = db.cursor()

def dbcommit():
    db.commit()
    return True
    
def dbclose():
    db.close()
    return True

def getcur():
    return db.cursor()


def runsql(s, p=None):
    db1 = dbc.connect(host=DB['host'], user=DB['user'], passwd=DB['passwd'], db=DB['db'], use_unicode=True, charset="utf8", collation="utf8_unicode_ci")
    db1.cursor().execute('SET NAMES utf8 COLLATE utf8_unicode_ci;')
    db1.cursor().execute('set global group_concat_max_len=256;')
    db1.cursor().execute('set group_concat_max_len=256;')
    cur = db1.cursor()
    try:
        if p:
            cur.execute(s,p)
        else:
            cur.execute(s)
    except Exception as e:
        Log.exception("run sql", "SQL error")
        raise e
    db1.commit()
    return True

def runsqlmany(s, p):
    db1 = dbc.connect(host=DB['host'], user=DB['user'], passwd=DB['passwd'], db=DB['db'], use_unicode=True, charset="utf8", collation="utf8_unicode_ci")
    db1.cursor().execute('SET NAMES utf8 COLLATE utf8_unicode_ci;')
    cur = db1.cursor()
    cur.executemany(s,p)
    db1.commit()
    return True


def fetch_rawsql(s):
    db1 = dbc.connect(host=DB['host'], user=DB['user'], passwd=DB['passwd'], db=DB['db'], use_unicode=True, charset="utf8", collation="utf8_unicode_ci")
    db1.cursor().execute('SET NAMES utf8 COLLATE utf8_unicode_ci;')
    cur = db1.cursor()
    cur.execute(s)
    desc = cur.description
    return [ dict(zip([col[0] for col in desc], row)) for row in cur.fetchall()]

def table_column(table):
    db1 = dbc.connect(host=DB['host'], user=DB['user'], passwd=DB['passwd'], db=DB['db'], use_unicode=True, charset="utf8", collation="utf8_unicode_ci")
    db1.cursor().execute('SET NAMES utf8 COLLATE utf8_unicode_ci;')
    cur = db1.cursor()
    cur.execute("SELECT GROUP_CONCAT(upper(COLUMN_NAME)) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '"+table+"'")
    return cur.fetchone()[0].split(',')

def table_exist(table):
    db1 = dbc.connect(host=DB['host'], user=DB['user'], passwd=DB['passwd'], db=DB['db'], use_unicode=True, charset="utf8", collation="utf8_unicode_ci")
    db1.cursor().execute('SET NAMES utf8 COLLATE utf8_unicode_ci;')
    cur = db1.cursor()
    cur.execute("SHOW TABLES LIKE '"+table+"'")
    if cur.fetchone():
        return True
    else:
        return False


ForceRefreshTable = ForceRefreshTable
