# -*- coding: utf-8 -*-
"""
Created on Sat Oct 14 21:19:08 2017

@author: jsu
"""

#pip install pandas-datareader
from pandas_datareader import data
from pandas_datareader.google.daily import GoogleDailyReader
import pandas as pd
import datetime, time, sys
from dateutil.relativedelta import relativedelta

from util_mysql import table_exist, runsql, runsqlmany, fetch_rawsql, dbcommit, getcur, ForceRefreshTable
from get_sp500 import refresh_sp500


rym = [(10,60),(10,36),(10,12),(5,36),(5,12),(3,12),(3,6),(1,6)]
rmd = [(6,90), (6,30), (6,7), (3,30), (3,7), (1,7)]

cdate = datetime.date.today()

#GoogleDailyReader.url = 'http://finance.google.com/finance/historical'

if ForceRefreshTable:
    if cdate.weekday() in (5, 6):
        print("today is weekend, ForeceRefreshTable")
        cdate = cdate - datetime.timedelta(days=cdate.weekday()-4)


tname = "ff_stock_"+cdate.strftime('%Y%m%d')
if table_exist(tname):
    print("Up to date")
    sys.exit()


FF_STOCK_ADJ_DDL = """create table ff_stock_adj (
symbol varchar(10),
close_date date, 
high float,
low float,
close float,
volume float
)
""".replace('\n', ' ').replace('\r', '')

FF_STOCK_SUMMARY_HIST_DDL = """create table ff_stock_summary_hist (
score_date date, 
symbol varchar(10),
rn int, 
summary_score float
)
""".replace('\n', ' ').replace('\r', '')
FF_STOCK_SUMMARY_HIST_I1 = "create index ff_stock_summary_hist_i1 on ff_stock_summary_hist (score_date, symbol)"
FF_STOCK_SUMMARY_HIST_I2 = "create index ff_stock_summary_hist_i2 on ff_stock_summary_hist (symbol)"

FF_STOCK_SUMMARY_TERM_DDL = """create table ff_stock_summary_term (
term_date date, 
term varchar(100),
d int,
symbol varchar(10),
close float,
df float,
dp float,
rn int
)
""".replace('\n', ' ').replace('\r', '')
FF_STOCK_SUMMARY_TERM_I1 = "create index ff_stock_summary_term_i1 on ff_stock_summary_term (term_date, symbol, d)"

def assure_required_tables():
    if table_exist("ff_stock_adj"):
        runsql("drop table ff_stock_adj")
    runsql(FF_STOCK_ADJ_DDL)
    refresh_sp500()
    if not table_exist("ff_stock_summary_hist"):
        runsql(FF_STOCK_SUMMARY_HIST_DDL)
        runsql(FF_STOCK_SUMMARY_HIST_I1)
        runsql(FF_STOCK_SUMMARY_HIST_I2)
    if not table_exist("ff_stock_summary_term"):
        runsql(FF_STOCK_SUMMARY_TERM_DDL)
        runsql(FF_STOCK_SUMMARY_TERM_I1)



assure_required_tables()

symbols = fetch_rawsql("select symbol from ff_scan_symbols where datediff(now(),last_updated)<60")
symbols = [i['symbol'] for i in symbols]


#symbols = [symbols[0]]
for s in symbols:
    try:
        d = data.DataReader(s, 'google', cdate-relativedelta(years=10)-relativedelta(months=2), datetime.datetime.now())
        d = d.where((pd.notnull(d)), None)
        t1 = d['Close'].values.tolist()
        t2 = d.index.tolist()
        t3 = d['High'].values.tolist()
        t4 = d['Low'].values.tolist()
        t5 = d['Volume'].values.tolist()
        T = [(s,)+(b.to_pydatetime().strftime('%Y-%m-%d'),)+(c,d,a,e) for a,b,c,d,e in zip(t1,t2,t3,t4,t5)]
        runsqlmany("insert into ff_stock_adj (symbol, close_date, high, low, close, volume) values (%s, %s, %s, %s, %s, %s)", T)
        dbcommit()
        print("Done ..."+s+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    except:
        print("Error and skipped ..."+s+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    time.sleep(5)

print("Started backup ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

# check data freshness
md = fetch_rawsql("select max(close_date) cd from ff_stock_adj")[0]['cd']
if md < cdate:
    print("Rotten ingestion")
    sys.exit()

# check data size
cur = getcur()
cur.execute("show tables like 'ff_stock_________'")
T = [t[0] for t in cur.fetchall()]
if T:
    c_adj  = fetch_rawsql("select count(1) cnt from ff_stock_adj")[0]['cnt']
    c_last = fetch_rawsql("select count(1) cnt from "+T[-1])[0]['cnt']
    if c_adj < c_last*0.5:
        print("Weak ingestion")
        sys.exit()

# swap prod table ff_stock with ff_stock_adj
if table_exist(tname):
    runsql("drop table "+tname)
runsql("create table "+tname+" as select * from ff_stock_adj")
runsql("create index "+tname+"_i1 on "+tname+" (symbol, close_date)")
runsql("create index "+tname+"_i2 on "+tname+" (close_date)")
runsql("drop table if exists ff_stock")
runsql("alter table ff_stock_adj rename to ff_stock")
runsql("create index ff_stock_i1 on ff_stock (symbol, close_date)")
runsql("create index ff_stock_i2 on ff_stock (close_date)")
print("Finished daily backup "+tname+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

tname = "ff_stock_"+cdate.strftime('%Yw%W')
if table_exist(tname):
    runsql("drop table "+tname)
runsql("create table "+tname+" as select * from ff_stock")
print("Finished weekly backup "+tname+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
tname = "ff_stock_"+cdate.strftime('%Ym%m')
if table_exist(tname):
    runsql("drop table "+tname)
runsql("create table "+tname+" as select * from ff_stock")
print("Finished monthly backup "+tname+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
dbcommit()

cur = getcur()
cur.execute("show tables like 'ff_stock_________'")
T = [t[0] for t in cur.fetchall()]
for t in T[:-5]:
    runsql("drop table "+t)
cur.execute("show tables like 'ff_stock_____w__'")
T = [t[0] for t in cur.fetchall()]
for t in T[:-4]:
    runsql("drop table "+t)
cur.execute("show tables like 'ff_stock_____m__'")
T = [t[0] for t in cur.fetchall()]
for t in T[:-4]:
    runsql("drop table "+t)
print("Finished clean up ... "+time.strftime('%Y-%m-%d %H:%M:%S'))


print("Started profiling ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("drop table if exists ff_stock_w1")
runsql("create table ff_stock_w1 as select a.*, DATE_FORMAT(close_date, '%Y%m') close_month from ff_stock a")
runsql("create index ff_stock_w1_i1 on ff_stock_w1 (symbol, close_month)")
runsql("drop table if exists ff_stock_w2")
runsql("create table ff_stock_w2 as select symbol, close_month, max(close) c_max, min(close) c_min from ff_stock_w1 group by symbol, close_month")
runsql("create index ff_stock_w2_i1 on ff_stock_w2 (symbol, close_month)")
runsql("create index ff_stock_w2_i2 on ff_stock_w2 (close_month)")
print("Done monthly w2 ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("drop table if exists ff_stock_w3")
runsql("create table ff_stock_w3 as \
       select @rn:=if(@s=start_month and @e=end_month, @rn+1,0) rn, @s:=start_month start_month, @e:=end_month end_month, symbol, c_diff from \
       ( \
       select a.close_month start_month, b.close_month end_month, a.symbol, (b.c_max-a.c_min)/a.c_min c_diff from ff_stock_w2 a, ff_stock_w2 b where a.symbol=b.symbol and a.close_month < b.close_month order by start_month, end_month, c_diff desc \
       ) a, (select @s:='', @e:='', @rn:=0) b")
runsql("create index ff_stock_w3_i1 on ff_stock_w3 (start_month, end_month, symbol, rn)")
print("Done monthly ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

runsql("drop table if exists ff_stock_w4")
runsql("create table ff_stock_w4 as select symbol, close_date, high, low, close from ff_stock where datediff(now(),close_date)<218")
runsql("create index ff_stock_w4_i1 on ff_stock_w4 (symbol, close_date)")
runsql("create index ff_stock_w4_i2 on ff_stock_w4 (close_date)")
runsql("drop table if exists ff_stock_w40")
runsql("create table ff_stock_w40 as select @rn:=@rn+1 rn, close_date from \
       (select distinct (close_date) from ff_stock_w4 order by close_date desc) a, (select @rn:=-1) b")
runsql("create index ff_stock_w40_i1 on ff_stock_w40 (close_date)")
runsql("drop table if exists ff_stock_w41")
runsql("create table ff_stock_w41 as select a.symbol, b.close, b.close-a.close d, round((b.close-a.close)/a.close*100,2) dp from \
       (select a.symbol, a.close from ff_stock_w4 a, (select close_date ms from ff_stock_w40 where rn=1) b where a.close_date = ms) a, \
       (select a.symbol, a.close from ff_stock_w4 a, (select close_date ms from ff_stock_w40 where rn=0) b where a.close_date = ms) b \
       where a.symbol=b.symbol order by symbol")
runsql("create index ff_stock_w41_i1 on ff_stock_w41 (symbol)")
print("Done daily w4 ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("drop table if exists ff_stock_w5")
runsql("create table ff_stock_w5 as \
       select @rn:=if(@s=start_date and @e=end_date, @rn+1,0) rn, @s:=start_date start_date, @e:=end_date end_date, symbol, c_diff, base from \
       ( \
       select a.symbol, a.close_date start_date, b.close_date end_date, (b.close-a.close)/a.close c_diff, a.close base \
       from ff_stock_w4 a, ff_stock_w4 b where a.symbol=b.symbol and a.close_date<=b.close_date order by start_date, end_date, c_diff desc \
       ) a, (select @s:='1970-01-01', @e:='1970-01-01', @rn:=0) b")
runsql("create index ff_stock_w5_i1 on ff_stock_w5 (start_date, end_date, symbol, rn)")
runsql("drop table if exists ff_stock_w42")
sqllist = []
for x,y in zip(['2 days','1 week','2 weeks','1 month','3 months','6 months'],[2,7,14,30,90,180]):
    sqllist.append("select '"+x+"' term, "+str(y)+" d, a.symbol, b.close, b.close-a.close df, round((b.close-a.close)/a.close*100,2) dp, d.rn from ff_stock_w4 a, ff_stock_w4 b, ff_stock_w5 d, (select max(a.close_date) ds, any_value(b.de) de from ff_stock_w40 a, (select max(close_date) de from ff_stock_w40) b where a.close_date <= DATE_SUB(b.de, INTERVAL "+(x[:-1] if x[-1]=="s" else x)+")) c where a.symbol=b.symbol and a.close_date=c.ds and b.close_date=c.de and c.ds=d.start_date and c.de=d.end_date and a.symbol=d.symbol")
rawsql = "create table ff_stock_w42 as " + " union ".join(sqllist)
runsql(rawsql)
runsql("create index ff_stock_w42_i1 on ff_stock_w42 (symbol,d)")
runsql("drop table if exists ff_stock_w43")
runsql("create table ff_stock_w43 as select @rn:=@rn+1 rn, a.* from (select symbol, round(sum(greatest(15-(rn/20),0))+10,1) summary_score from ff_stock_w42 where symbol not like '%-%' group by symbol order by sum(greatest(15-(rn/20),0))+10 desc) a, (select @rn:=0) b")
runsql("create index ff_stock_w43_i1 on ff_stock_w43 (symbol)")
runsql("create index ff_stock_w43_i2 on ff_stock_w43 (rn)")
cnt = fetch_rawsql("select count(1) cnt from ff_stock_summary_hist a, (select max(close_date) de from ff_stock_w40) b where a.score_date>=de")[0]['cnt']
if cnt == 0:
    runsql("insert into ff_stock_summary_hist (score_date, symbol, rn, summary_score) select b.de, a.symbol, a.rn, a.summary_score from ff_stock_w43 a, (select max(close_date) de from ff_stock_w40) b")
cnt = fetch_rawsql("select count(1) cnt from ff_stock_summary_term a, (select max(close_date) de from ff_stock_w40) b where a.term_date>=de")[0]['cnt']
if cnt == 0:
    runsql("insert into ff_stock_summary_term (term_date, term, d, symbol, close, df, dp, rn) select b.de, a.term, a.d, a.symbol, a.close, a.df, a.dp, a.rn from ff_stock_w42 a, (select max(close_date) de from ff_stock_w40) b")
print("Done daily ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

m = (cdate - relativedelta(years=10)).strftime("%Y%m")
runsql("drop table if exists ff_stock_w31")
runsql("create table ff_stock_w31 as select a.*, period_diff(end_month,start_month) md from ff_stock_w3 a where start_month>'"+m+"' and rn<180")
runsql("create index ff_stock_w31_i1 on ff_stock_w31 (symbol, start_month, md, rn)")
runsql("create index ff_stock_w31_i2 on ff_stock_w31 (symbol, end_month, rn, md)")
runsql("create index ff_stock_w31_i3 on ff_stock_w31 (start_month, md, symbol, rn)")
runsql("create index ff_stock_w31_i4 on ff_stock_w31 (end_month, symbol, rn, md)")
print("Done best monthly w31 ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
for r in rym:
    m = (cdate - relativedelta(years=r[0])).strftime("%Y%m")
    runsql("drop table if exists ff_stock_w32")
    runsql("create table ff_stock_w32 as \
            select @r:=if(@s=symbol,@r+1,0) r, @s:=symbol symbol, a.rn, a.start, a.end, a.c_diff, a.d from \
            (select symbol, rn, start_month start, end_month end, c_diff, md d from ff_stock_w31 \
             where start_month>'"+m+"' and md>="+str(r[1])+" order by symbol, rn) a, (select @s:='', @r:=-1) b")
    runsql("create index ff_stock_w32_i1 on ff_stock_w32 (r)")
    runsql("drop table if exists ff_stock_best_"+str(r[0])+"y"+str(r[1])+"m")
    runsql("create table ff_stock_best_"+str(r[0])+"y"+str(r[1])+"m as select symbol, rn, str_to_date(concat(start,'01'),'%Y%m%d') start, str_to_date(concat(end,'01'),'%Y%m%d') end, c_diff, d from ff_stock_w32 where r=0")
runsql("drop table if exists ff_stock_w33")
runsql("create table ff_stock_w33 as select symbol, rn, str_to_date(concat(start,'01'),'%Y%m%d') start, str_to_date(concat(end,'01'),'%Y%m%d') end, c_diff, d from ( \
        select @r:=if(@s=symbol,@r+1,0) r, @s:=symbol symbol, a.rn, a.start, a.end, a.c_diff, a.d from (select symbol, rn, start_month start, end_month end, c_diff, md d from \
        ff_stock_w31 where end_month='"+cdate.strftime("%Y%m")+"' order by symbol, rn, d) a, (select @s:='', @r:=-1) b) a where r=0")
runsql("create index ff_stock_w33_i1 on ff_stock_w33 (symbol)")
print("Done best monthly ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

m = (cdate - relativedelta(months=6)).strftime("%Y-%m-%d")
runsql("drop table if exists ff_stock_w51")
runsql("create table ff_stock_w51 as select a.*, datediff(end_date,start_date) dd from ff_stock_w5 a where start_date>'"+m+"' and rn<180")
runsql("create index ff_stock_w51_i1 on ff_stock_w51 (symbol, start_date, dd, rn)")
runsql("create index ff_stock_w51_i2 on ff_stock_w51 (symbol, end_date, rn, dd)")
runsql("create index ff_stock_w51_i3 on ff_stock_w51 (start_date, dd, symbol, rn)")
runsql("create index ff_stock_w51_i4 on ff_stock_w51 (end_date, symbol, rn, dd)")
print("Done best daily w51 ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
for r in rmd:
    m = (cdate - relativedelta(months=r[0])).strftime("%Y-%m-%d")
    runsql("drop table if exists ff_stock_w52")
    runsql("create table ff_stock_w52 as \
            select @r:=if(@s=symbol,@r+1,0) r, @s:=symbol symbol, a.rn, a.start, a.end, a.c_diff, a.d from \
            (select symbol, rn, start_date start, end_date end, c_diff, dd d from ff_stock_w51 \
             where start_date>'"+m+"' and dd>="+str(r[1])+" order by symbol, rn) a, (select @s:='', @r:=-1) b")
    runsql("create index ff_stock_w52_i1 on ff_stock_w52 (r)")
    runsql("drop table if exists ff_stock_best_"+str(r[0])+"m"+str(r[1])+"d")
    runsql("create table ff_stock_best_"+str(r[0])+"m"+str(r[1])+"d as select symbol, rn, str_to_date(start,'%Y-%m-%d') start, str_to_date(end,'%Y-%m-%d') end, c_diff, d from ff_stock_w52 where r=0")
runsql("drop table if exists ff_stock_w53")
runsql("create table ff_stock_w53 as select symbol, rn, str_to_date(start,'%Y-%m-%d') start, str_to_date(end,'%Y-%m-%d') end, c_diff, d from ( \
        select @r:=if(@s=symbol,@r+1,0) r, @s:=symbol symbol, a.rn, a.start, a.end, a.c_diff, a.d from (select symbol, rn, start_date start, end_date end, c_diff, dd d from \
        ff_stock_w51 where end_date='"+cdate.strftime("%Y-%m-%d")+"' order by symbol, rn, d) a, (select @s:='', @r:=-1) b) a where r=0")
runsql("create index ff_stock_w53_i1 on ff_stock_w53 (symbol)")
print("Done best daily ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

cur.execute("show tables like 'ff_stock_best_____'")
T = [t[0] for t in cur.fetchall()]
cur.execute("show tables like 'ff_stock_best______'")
T += [t[0] for t in cur.fetchall()]
cur.execute("show tables like 'ff_stock_best_______'")
T += [t[0] for t in cur.fetchall()]
T1 = ["select '"+t[14:]+"' rg, a.* from "+t+" a" for t in T]
rawsql = "create table ff_stock_best as " + " union ".join(T1)
runsql("drop table if exists ff_stock_best")
runsql(rawsql)
runsql("create index ff_stock_best_i1 on ff_stock_best (symbol, rn)")

