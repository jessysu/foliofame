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



rym = [(5,36),(5,12),(5,6),(3,12),(3,6),(1,6)]
rmd = [(6,90), (6,30), (6,7), (3,30), (3,7), (1,7)]

cdate = datetime.date.today()

#GoogleDailyReader.url = 'http://finance.google.com/finance/historical'

if ForceRefreshTable:
    if cdate.weekday() in (5, 6):
        print("today is weekend, ForeceRefreshTable")
        cdate = cdate - datetime.timedelta(days=cdate.weekday()-4)


tname = "ff_stock_bck"+cdate.strftime('%Y%m%d')
if table_exist(tname) and ForceRefreshTable is False:
    print("Up to date")
    sys.exit()


FF_STOCK_ADJ_DDL = """create table ff_stock_adj (
symbol varchar(10),
close_date date, 
high float,
low float,
open float,
close float,
volume float
) character set utf8 collate utf8_unicode_ci
""".replace('\n', ' ').replace('\r', '')

FF_STOCK_SUMMARY_HIST_DDL = """create table ff_stock_summary_hist (
score_date date, 
symbol varchar(10),
rn int, 
summary_score float
) character set utf8 collate utf8_unicode_ci
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
) character set utf8 collate utf8_unicode_ci
""".replace('\n', ' ').replace('\r', '')
FF_STOCK_SUMMARY_TERM_I1 = "create index ff_stock_summary_term_i1 on ff_stock_summary_term (term_date, symbol, d)"

def assure_required_tables():
    if table_exist("ff_stock_adj"):
        runsql("drop table ff_stock_adj")
    runsql(FF_STOCK_ADJ_DDL)
    try:
        refresh_sp500()
    except Exception as e:
        print("Error in fetching SP500 list. Likely Wikipedia changed layout")
        print("Exception info: " + str(e))
    if not table_exist("ff_stock_summary_hist"):
        runsql(FF_STOCK_SUMMARY_HIST_DDL)
        runsql(FF_STOCK_SUMMARY_HIST_I1)
        runsql(FF_STOCK_SUMMARY_HIST_I2)
    else:
        a = fetch_rawsql("show table status like 'ff_stock_summary_hist'")
        a = a[0]['Collation']
        if a != 'utf8_unicode_ci':
            runsql("ALTER TABLE ff_stock_summary_hist CONVERT TO CHARACTER SET utf8 COLLATE utf8_unicode_ci")
    if not table_exist("ff_stock_summary_term"):
        runsql(FF_STOCK_SUMMARY_TERM_DDL)
        runsql(FF_STOCK_SUMMARY_TERM_I1)
    else:
        a = fetch_rawsql("show table status like 'ff_stock_summary_term'")
        a = a[0]['Collation']
        if a != 'utf8_unicode_ci':
            runsql("ALTER TABLE ff_stock_summary_term CONVERT TO CHARACTER SET utf8 COLLATE utf8_unicode_ci")



assure_required_tables()

symbols = fetch_rawsql("select symbol from ff_scan_symbols where datediff(now(),last_updated)<60")
# for symbols like "BRK.B" (IEX now does not accept "BRK-B")
symbols = [i['symbol'].replace('-','.').rstrip() for i in symbols]
seen = {}
symbols = [seen.setdefault(x, x) for x in symbols if x not in seen] # dedup

#symbols = [symbols[0]]
for s in symbols:
    try:
        d = data.DataReader(s, 'iex', cdate-relativedelta(years=5)-relativedelta(months=2), datetime.datetime.now())
        d = d.where((pd.notnull(d)), None)
        t0 = d['open'].values.tolist()
        t1 = d['close'].values.tolist()
        t2 = d.index.tolist()
        t3 = d['high'].values.tolist()
        t4 = d['low'].values.tolist()
        t5 = d['volume'].values.tolist()
        #T = [(s,)+(b.to_pydatetime().strftime('%Y-%m-%d'),)+(c,d,a,e) for a,b,c,d,e in zip(t1,t2,t3,t4,t5)]
        T = [(s,)+(c,)+(d,e,a,b,f) for a,b,c,d,e,f in zip(t0,t1,t2,t3,t4,t5)]
        runsqlmany("insert into ff_stock_adj (symbol, close_date, high, low, open, close, volume) values (%s, %s, %s, %s, %s, %s, %s)", T)
        dbcommit()
        print("Done ..."+s+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    except:
        print("Error and skipped ..."+s+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    #time.sleep(1)

print("Started backup ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

# check data freshness
md = fetch_rawsql("select max(close_date) cd from ff_stock_adj")[0]['cd']
if md < cdate and not ForceRefreshTable:
    print("Rotten ingestion")
    sys.exit()

# check data size
cur = getcur()
cur.execute("show tables like 'ff_stock_bck________'")
T = [t[0] for t in cur.fetchall()]
if T:
    c_adj = fetch_rawsql("select count(1) cnt from ff_stock_adj")[0]['cnt']
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

tname = "ff_stock_bck"+cdate.strftime('%Yw%W')
if table_exist(tname):
    runsql("drop table "+tname)
runsql("create table "+tname+" as select * from ff_stock")
print("Finished weekly backup "+tname+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
tname = "ff_stock_bck"+cdate.strftime('%Ym%m')
if table_exist(tname):
    runsql("drop table "+tname)
runsql("create table "+tname+" as select * from ff_stock")
print("Finished monthly backup "+tname+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
dbcommit()

cur = getcur()
cur.execute("show tables like 'ff_stock_bck________'")
T = [t[0] for t in cur.fetchall()]
for t in T[:-5]:
    runsql("drop table "+t)
cur.execute("show tables like 'ff_stock_bck____w__'")
T = [t[0] for t in cur.fetchall()]
for t in T[:-4]:
    runsql("drop table "+t)
cur.execute("show tables like 'ff_stock_bck____m__'")
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
runsql("create index ff_stock_w42_i2 on ff_stock_w42 (d,term)")
runsql("drop table if exists ff_stock_w43")
runsql("create table ff_stock_w43 as select @rn:=@rn+1 rn, a.* from (select symbol, round(sum(greatest(15-(rn/20),0))+10,1) summary_score from ff_stock_w42 where symbol not like '%-%' group by symbol order by sum(greatest(15-(rn/20),0))+10 desc) a, (select @rn:=0) b")
runsql("create index ff_stock_w43_i1 on ff_stock_w43 (symbol)")
runsql("create index ff_stock_w43_i2 on ff_stock_w43 (rn)")

cnt=0
try:
    cnt = fetch_rawsql("select count(1) cnt from ff_stock_summary_hist a, (select max(close_date) de from ff_stock_w40) b where a.score_date>=de")[0]['cnt']
except Exception as e:
    print("first run, no ff_stock_summary_hist data")
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

cur.execute("show tables like 'ff_stock_best_%'")
T = [t[0] for t in cur.fetchall()]
for i in T:
    runsql("drop table if exists "+i)
for r in rym:
    m = (cdate - relativedelta(years=r[0])).strftime("%Y%m")
    runsql("drop table if exists ff_stock_w32")
    runsql("create table ff_stock_w32 as \
            select @r:=if(@s=symbol,@r+1,0) r, @s:=symbol symbol, a.rn, a.start, a.end, a.c_diff, a.d from \
            (select symbol, rn, start_month start, end_month end, c_diff, md d from ff_stock_w31 \
             where start_month>'"+m+"' and md>="+str(r[1])+" order by symbol, rn) a, (select @s:='', @r:=-1) b")
    runsql("create index ff_stock_w32_i1 on ff_stock_w32 (r)")
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
for r in rmd:
    m = (cdate - relativedelta(months=r[0])).strftime("%Y-%m-%d")
    runsql("drop table if exists ff_stock_w52")
    runsql("create table ff_stock_w52 as \
            select @r:=if(@s=symbol,@r+1,0) r, @s:=symbol symbol, a.rn, a.start, a.end, a.c_diff, a.d from \
            (select symbol, rn, start_date start, end_date end, c_diff, dd d from ff_stock_w51 \
             where start_date>'"+m+"' and dd>="+str(r[1])+" order by symbol, rn) a, (select @s:='', @r:=-1) b")
    runsql("create index ff_stock_w52_i1 on ff_stock_w52 (r)")
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
runsql("create index ff_stock_best_i1 on ff_stock_best (symbol, rn, rg)")
runsql("create index ff_stock_best_i2 on ff_stock_best (rg)")
print("Done BestEver summary ... "+time.strftime('%Y-%m-%d %H:%M:%S'))


# volume-related
print("Started volume profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("drop table if exists ff_stock_vol_w1")
runsql("create table ff_stock_vol_w1 as select symbol, avg(volume) avg_volume, std(volume) std_volume from ff_stock where close_date>=date_sub(now() , interval 6 month) group by symbol")
runsql("create index ff_stock_vol_w1_i1 on ff_stock_vol_w1 (symbol)")
runsql("drop table if exists ff_stock_vol_w2")
runsql("create table ff_stock_vol_w2 as select a.symbol, close_date, volume, (volume-avg_volume)/(std_volume+0.000001) z_volume from ff_stock a, ff_stock_vol_w1 b where close_date>=date_sub(now() , interval 6 month) and a.symbol=b.symbol")
runsql("drop table if exists ff_stock_vol_w3")
runsql("create table ff_stock_vol_w3 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, a.* from (select z_volume, cnt from (select z_volume from ff_stock_vol_w2) a, (select count(1) cnt from ff_stock_vol_w2) b order by z_volume) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_vol_w4")
runsql("create table ff_stock_vol_w4 as select a.bin, a.min_z, ifnull(b.min_z,(select max(z_volume) from ff_stock_vol_w3)) max_z from (select bin bin, min(z_volume) min_z from ff_stock_vol_w3 group by bin) a left join (select bin-1 bin, min(z_volume) min_z from ff_stock_vol_w3 group by bin-1) b on a.bin=b.bin")
runsql("drop table if exists ff_stock_vol_w5")
runsql("create table ff_stock_vol_w5 as select a.*, avg_volume, std_volume, (volume-avg_volume)/(std_volume+0.000001) z_volume from (select * from ff_stock where close_date>=date_sub(now() , interval 6 month)) a, ff_stock_vol_w1 b where a.symbol=b.symbol")
runsql("create index ff_stock_vol_w5_i1 on ff_stock_vol_w5 (symbol)")
runsql("create index ff_stock_vol_w5_i2 on ff_stock_vol_w5 (close_date)")
runsql("drop table if exists ff_stock_vol_w6")
runsql("create table ff_stock_vol_w6 as select a.*, minmin_z, maxmax_z from ff_stock_vol_w5 a, (select min(min_z) minmin_z, max(max_z) maxmax_z from ff_stock_vol_w4) b")
runsql("drop table if exists ff_stock_vol_w7")
runsql("create table ff_stock_vol_w7 as select a.*, ifnull(bin,if(z_volume>=maxmax_z,100,-1)) bin from ff_stock_vol_w6 a left join ff_stock_vol_w4 b on a.z_volume>=b.min_z and a.z_volume<b.max_z")
runsql("create index ff_stock_vol_w7_i1 on ff_stock_vol_w7 (symbol)")
runsql("create index ff_stock_vol_w7_i2 on ff_stock_vol_w7 (close_date, symbol, z_volume)")
runsql("drop table if exists ff_stock_vol_w8")
runsql("create table ff_stock_vol_w8 as select * from ff_stock_vol_w7 where close_date=(select max(close_date) from ff_stock)")
runsql("create index ff_stock_vol_w8_i1 on ff_stock_vol_w8 (symbol)")
runsql("drop table if exists ff_stock_vol_w9")
runsql("create table ff_stock_vol_w9 as select @rn:=if(@s=a.symbol,@rn+1,0) rn, @s:=symbol symbol, a.close_date, close, volume, z_volume from (select * from ff_stock_vol_w7 order by symbol, close_date) a, (select @rn:=-1,@s:='') b")
runsql("create index ff_stock_vol_w9_i1 on ff_stock_vol_w9 (symbol, rn)")
runsql("drop table if exists ff_stock_vol_w10")
runsql("create table ff_stock_vol_w10 as select b.*, (b.close-a.close)/a.close chg from ff_stock_vol_w9 a, ff_stock_vol_w9 b where a.symbol=b.symbol and a.rn+1=b.rn")
runsql("create index ff_stock_vol_w10_i1 on ff_stock_vol_w10 (symbol)")
runsql("drop table if exists ff_stock_vol_w11")
runsql("create table ff_stock_vol_w11 as select a.symbol, sum( a.chg/sqrt(b.s_chg/b.n) * a.z_volume) / b.n corr from ff_stock_vol_w10 a, (select symbol, sum(chg*chg) s_chg, count(1) n from ff_stock_vol_w10 group by symbol) b where a.symbol=b.symbol group by a.symbol")
runsql("drop table if exists ff_stock_vol_w12")
runsql("create table ff_stock_vol_w12 as select @rn:=@rn+1 rn_neg, a.* from (select * from ff_stock_vol_w11 order by corr) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_vol_w13")
runsql("create table ff_stock_vol_w13 as select @rn:=@rn+1 rn_pos, a.* from (select * from ff_stock_vol_w12 order by corr desc) a, (select @rn:=0) b")
print("Done volume profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))




# create ff_stock var with 7 days moving average
if table_exist("ff_stock_var_d7"):
    runsql("drop table ff_stock_var_d7")
print("Start to calculate bollinger band... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("CREATE TABLE ff_stock_var_d7 \
    SELECT b.*, a.mat7, a.mat7std, a.mat7+a.mat7std*2 AS mat7upper, a.mat7-a.mat7std*2 AS mat7lower FROM (\
        SELECT a.symbol, a.close_date, AVG(b.close) AS mat7, stddev(b.close) AS mat7std\
        FROM (select * from ff_stock where close_date>=date_sub('"+cdate.strftime("%Y-%m-%d")+"' , interval 6 month)) a\
        JOIN (select * from ff_stock where close_date>=date_sub('"+cdate.strftime("%Y-%m-%d")+"' , interval 6 month)) b ON a.symbol=b.symbol AND DATEDIFF(a.close_date, b.close_date) BETWEEN 0 AND 6\
        GROUP BY a.symbol, a.close_date\
        ) a\
    JOIN ff_stock b\
    ON a.symbol=b.symbol AND a.close_date=b.close_date")
print("Done calculate bollinger band... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("create index ff_stock_var_d7_i1 on ff_stock_var_d7 (symbol, close_date)")
runsql("create index ff_stock_var_d7_i2 on ff_stock_var_d7 (close_date)")

if table_exist("ff_stock_var_diff_w1"):
    runsql("drop table ff_stock_var_diff_w1")
print("Start to calculate  variance indicator... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("create table ff_stock_var_diff_w1 as \
    select a.symbol, a.mat7std, b.mat7std_avg, a.mat7std/(b.mat7std_avg+0.000001) mat7_ratio from\
    (select symbol, mat7std from ff_stock_var_d7 where close_date=(select max(close_date) from ff_stock_var_d7)) a,\
    (select symbol, avg(mat7std) mat7std_avg from ff_stock_var_d7 group by symbol) b\
    where a.symbol=b.symbol order by mat7_ratio desc")
print("Done calculate  variance indicator... "+time.strftime('%Y-%m-%d %H:%M:%S'))

runsql("drop table if exists ff_stock_var_diff_w2")
runsql("create table ff_stock_var_diff_w2 as select @rn:=@rn+1 rnls, a.* from (select * from ff_stock_var_diff_w1 order by mat7_ratio desc) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_var_diff_w3")
runsql("create table ff_stock_var_diff_w3 select @rn:=@rn+1 rnsl, a.* from (select * from ff_stock_var_diff_w2 order by mat7_ratio) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_var_diff_w4")
runsql("create table ff_stock_var_diff_w4 as select a.symbol, dd1w_avg, dd1w_std, dd1m_avg, dd1m_std, dd6m_avg, dd6m_std from (select symbol, avg((high-low)/close) dd1m_avg, std((high-low)/close) dd1m_std from ff_stock where close_date>=date_sub(now() , interval 1 month) group by symbol) a, (select symbol, avg((high-low)/close) dd6m_avg, std((high-low)/close) dd6m_std from ff_stock where close_date>=date_sub(now() , interval 6 month) group by symbol) b, (select symbol, avg((high-low)/close) dd1w_avg, std((high-low)/close) dd1w_std from ff_stock where close_date>=date_sub(now() , interval 1 week) group by symbol) c where a.symbol=b.symbol and a.symbol=c.symbol")
runsql("drop table if exists ff_stock_var_diff_w5")
runsql("create table ff_stock_var_diff_w5 as select a.*, (hlr-dd6m_avg)/(dd6m_std+0.000001) z_hl from (select symbol, close_date, high, low, close, high-low hl, (high-low)/close hlr from ff_stock where close_date>=date_sub(now() , interval 6 month)) a, ff_stock_var_diff_w4 b where a.symbol=b.symbol")
runsql("drop table if exists ff_stock_var_diff_w6")
runsql("create table ff_stock_var_diff_w6 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, a.* from (select z_hl, cnt from (select z_hl from ff_stock_var_diff_w5) a, (select count(1) cnt from ff_stock_var_diff_w5) b order by z_hl) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_var_diff_w7")
runsql("create table ff_stock_var_diff_w7 as select a.bin, a.min_z, ifnull(b.min_z,(select max(z_hl) from ff_stock_var_diff_w6)) max_z from (select bin bin, min(z_hl) min_z from ff_stock_var_diff_w6 group by bin) a left join (select bin-1 bin, min(z_hl) min_z from ff_stock_var_diff_w6 group by bin-1) b on a.bin=b.bin")
runsql("drop table if exists ff_stock_var_diff_w8")
runsql("create table ff_stock_var_diff_w8 as select a.*, minmin_z, maxmax_z from ff_stock_var_diff_w5 a, (select min(min_z) minmin_z, max(max_z) maxmax_z from ff_stock_var_diff_w7) b")
runsql("drop table if exists ff_stock_var_diff_w9")
runsql("create table ff_stock_var_diff_w9 as select a.*, ifnull(bin,if(z_hl>=maxmax_z,100,-1)) bin from ff_stock_var_diff_w8 a left join ff_stock_var_diff_w7 b on a.z_hl>=b.min_z and a.z_hl<b.max_z")
runsql("create index ff_stock_var_diff_w9_i1 on ff_stock_var_diff_w9 (symbol)")
runsql("create index ff_stock_var_diff_w9_i2 on ff_stock_var_diff_w9 (close_date, symbol, z_hl)")
runsql("drop table if exists ff_stock_var_diff_w10")
runsql("create table ff_stock_var_diff_w10 as select a.*, dd6m_avg avg_hl, dd6m_std std_hl from (select * from ff_stock_var_diff_w9 where close_date=(select max(close_date) from ff_stock)) a, ff_stock_var_diff_w4 b where a.symbol=b.symbol")
runsql("create index ff_stock_var_diff_w10_w1 on ff_stock_var_diff_w10 (symbol)")
runsql("drop table if exists ff_stock_var_diff_w11")
runsql("create table ff_stock_var_diff_w11 as select symbol, close_date, close, mat7, mat7std, (close-mat7)/(mat7std+0.000001) z_mat7 from ff_stock_var_d7 where close_date<>(select min(close_date) from ff_stock_var_d7)")
runsql("drop table if exists ff_stock_var_diff_w12")
runsql("create table ff_stock_var_diff_w12 as select symbol, avg(z_mat7) z_mat7_avg, std(z_mat7) z_mat7_std from ff_stock_var_diff_w11 group by symbol")
runsql("create index ff_stock_var_diff_w12_w1 on ff_stock_var_diff_w12 (symbol)")
print("Done volatility profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))


# changerate-related
print("Started changerate profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("drop table if exists ff_stock_chg_w1")
runsql("create table ff_stock_chg_w1 as select @rn:=if(@s=symbol,@rn+1,0) rn, @s:=symbol symbol, close_date, close from (select symbol, close_date, close from ff_stock where close_date>=date_sub(now() , interval 12 month) order by symbol, close_date) a, (select @rn:=-1, @s:='') b")
runsql("create index ff_stock_chg_w1_i1 on ff_stock_chg_w1 (symbol, rn)")
runsql("drop table if exists ff_stock_chg_w2")
runsql("create table ff_stock_chg_w2 as select b.*, a.close previous_close, (b.close-a.close)/a.close chg from ff_stock_chg_w1 a, ff_stock_chg_w1 b where a.symbol=b.symbol and b.rn=a.rn+1")
runsql("create index ff_stock_chg_w2_i1 on ff_stock_chg_w2 (close_date, symbol)")
runsql("create index ff_stock_chg_w2_i2 on ff_stock_chg_w2 (symbol, chg, close_date)")
runsql("drop table if exists ff_stock_chg_w3")
runsql("create table ff_stock_chg_w3 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, floor(@rn/(cnt+1)*1000) bin_1000, floor(@rn/(cnt+1)*10000) bin_10000, a.* from (select chg, cnt from (select chg from ff_stock_chg_w2) a, (select count(1) cnt from ff_stock_chg_w2) b order by chg) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_chg_w4")
runsql("create table ff_stock_chg_w4 as select 0 bin, -9999 min_chg, (select min(chg) from ff_stock_chg_w3) max_chg \
        union select round(a.bin/100,2) bin, a.min_chg, b.min_chg max_chg from (select bin_10000+1 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_10000<11 group by bin_10000) a, (select bin_10000 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_10000<11 group by bin_10000) b where a.bin=b.bin \
        union select round(a.bin/10,1) bin, a.min_chg, b.min_chg max_chg from (select bin_1000+1 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_1000<11 and bin_1000>0 group by bin_1000) a, (select bin_1000 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_1000<11 and bin_1000>0  group by bin_1000) b where a.bin=b.bin \
        union select a.bin, a.min_chg, b.min_chg max_chg from (select bin+1 bin, min(chg) min_chg from ff_stock_chg_w3 where bin>0 group by bin+1) a, (select bin bin, min(chg) min_chg from ff_stock_chg_w3 where bin>0 group by bin) b where a.bin=b.bin \
        union select round(a.bin/10,1) bin, a.min_chg, ifnull(b.min_chg,(select max(chg) from ff_stock_chg_w3)) max_chg from (select bin_1000+1 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_1000>989 group by bin_1000+1) a, (select bin_1000 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_1000>989 group by bin_1000) b where a.bin=b.bin \
        union select if(a.bin=10000,100,round(a.bin/100,2)) bin, a.min_chg, ifnull(b.min_chg,(select max(chg) from ff_stock_chg_w3)) max_chg from (select bin_10000+1 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_10000>9989 group by bin_10000+1) a left join (select bin_10000 bin, min(chg) min_chg from ff_stock_chg_w3 where bin_10000>9989 group by bin_10000) b on a.bin=b.bin \
        union select 100 bin, (select max(chg) from ff_stock_chg_w3) min_chg, 9999 max_chg")
runsql("drop table if exists ff_stock_chg_w5")
runsql("create table ff_stock_chg_w5 as select symbol, 'x' minmax, 'week' term, 7 d, max(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 week) group by symbol \
        union select symbol, 'n' minmax, 'week' term, 7 d, min(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 week) group by symbol \
        union select symbol, 'x' minmax, 'month' term, 30 d, max(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 month) group by symbol \
        union select symbol, 'n' minmax, 'month' term, 30 d, min(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 month) group by symbol \
        union select symbol, 'x' minmax, '3 months' term, 90 d, max(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 3 month) group by symbol \
        union select symbol, 'n' minmax, '3 months' term, 90 d, min(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 3 month) group by symbol \
        union select symbol, 'x' minmax, '6 months' term, 180 d, max(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 6 month) group by symbol \
        union select symbol, 'n' minmax, '6 months' term, 180 d, min(chg) val from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 6 month) group by symbol \
        union select symbol, 'x' minmax, 'year' term, 365 d, max(chg) val from ff_stock_chg_w2 group by symbol \
        union select symbol, 'n' minmax, 'year' term, 365 d, min(chg) val from ff_stock_chg_w2 group by symbol")
runsql("drop table if exists ff_stock_chg_w6")
runsql("create table ff_stock_chg_w6 as select a.*, b.bin from ff_stock_chg_w5 a, ff_stock_chg_w4 b where a.val>b.min_chg and a.val<=b.max_chg")
runsql("drop table if exists ff_stock_chg_w7")
runsql("create table ff_stock_chg_w7 as select a.*, (select max(close_date) from ff_stock_chg_w2 b where b.symbol=a.symbol and b.chg=a.val) close_date from ff_stock_chg_w6 a")
runsql("create index ff_stock_chg_w7_i1 on ff_stock_chg_w7 (symbol, d, minmax)")
runsql("drop table if exists ff_stock_chg_w8")
runsql("create table ff_stock_chg_w8 as select symbol, 'week' term, 7 d, count(1) n, sum(if(chg>0,1,0)) n_up from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 week) group by symbol \
        union select symbol, 'month' term, 30 d, count(1) n, sum(if(chg>0,1,0)) n_up from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 month) group by symbol \
        union select symbol, '3 months' term, 90 d, count(1) n, sum(if(chg>0,1,0)) n_up from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 3 month) group by symbol \
        union select symbol, '6 months' term, 180 d, count(1) n, sum(if(chg>0,1,0)) n_up from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 6 month) group by symbol \
        union select symbol, 'year' term, 365 d, count(1) n, sum(if(chg>0,1,0)) n_up from ff_stock_chg_w2 where close_date>=date_sub(now() , interval 1 year) group by symbol")
runsql("drop table if exists ff_stock_chg_w9")
runsql("create table ff_stock_chg_w9 as select a.*, round(n_up/n,4) up_ratio, round(n/d,2) d_ratio from ff_stock_chg_w8 a")
runsql("create index ff_stock_chg_w9_i1 on ff_stock_chg_w9 (symbol, d_ratio)")
runsql("drop table if exists ff_stock_chg_w10")
runsql("create table ff_stock_chg_w10 as select a.*, @r:=if(@s=symbol,if(chg*@c>0,@r+1,1),1) r, chg*@c chg_c, @rg:=if(@s=symbol,if(chg*@c>0,@rg*(1+chg),1+chg),1+chg) run_gain, @ud:=if(chg>=0,'u','d') ud, @c:=chg c, @s:=symbol s from (select * from ff_stock_chg_w2 order by symbol, rn) a, (select @r:=0, @rg:=0, @ud:='', @c:=0, @s:='') b")
runsql("create index ff_stock_chg_w10_i1 on ff_stock_chg_w10 (symbol, ud, close_date)")
runsql("drop table if exists ff_stock_chg_w11")
runsql("create table ff_stock_chg_w11 as select symbol, ud, max(r) max_run from ff_stock_chg_w10 group by symbol, ud")
runsql("drop table if exists ff_stock_chg_w12")
runsql("create table ff_stock_chg_w12 as select a.*, (select close_date from ff_stock_chg_w10 b where a.symbol=b.symbol and a.ud=b.ud and b.r=a.max_run order by close_date desc limit 1) end_date, (select rn from ff_stock_chg_w10 b where a.symbol=b.symbol and a.ud=b.ud and b.r=a.max_run order by close_date desc limit 1) end_rn from ff_stock_chg_w11 a")
runsql("drop table if exists ff_stock_chg_w13")
runsql("create table ff_stock_chg_w13 as select a.*, (select close_date from ff_stock_chg_w10 b where a.symbol=b.symbol and a.ud=b.ud and b.rn=a.end_rn-a.max_run+1) start_date from ff_stock_chg_w12 a")
runsql("drop table if exists ff_stock_chg_w14")
runsql("create table ff_stock_chg_w14 as select a.*, (run_gain-1) run_gain, pow(10,log10(1+abs(run_gain-1))/max_run)-1 daily_diff from ff_stock_chg_w13 a, ff_stock_chg_w10 b where a.symbol=b.symbol and a.ud=b.ud and a.end_date=b.close_date")
runsql("create index ff_stock_chg_w14_i1 on ff_stock_chg_w14 (symbol, ud)")
print("Done changerate profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))



# ceiling-floor-penetration-related
CF_WINDOWS = [7, 14, 30, 60, 90, 180]
print("Started ceilfloor profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))
s = ["select symbol, b.close_date, any_value("+str(w)+") d, max(high) h, min(low) l, avg(close) m from ff_stock a, (select close_date from ff_stock_w40 where rn=0) b where datediff(b.close_date,a.close_date) BETWEEN 0 AND "+str(w-1)+" group by a.symbol, b.close_date" for w in CF_WINDOWS]
s = " union ".join(s)
if not table_exist("ff_stock_cf_w0"):
    runsql("create table ff_stock_cf_w0 as " + s)
    runsql("create index ff_stock_cf_w0_i1 on ff_stock_cf_w0 (symbol)")
else:
    runsql("drop table if exists ff_stock_cf_w00")
    runsql("create table ff_stock_cf_w00 as " + s)
for w in CF_WINDOWS:
    runsql("drop table if exists ff_stock_cf_w1_"+str(w))
    runsql("create table ff_stock_cf_w1_"+str(w)+" as select a.symbol, a.close_date, any_value(a.high) high, any_value(a.low) low, any_value(a.open) open, any_value(a.close) close, any_value("+str(w)+") d, max(b.high) h, min(b.low) l, avg(b.close) m from (select * from ff_stock where close_date>=date_add(date_sub(now(), interval 12 month), interval 7 day)) a, (select * from ff_stock where close_date>=date_sub(now(), interval 12 month)) b where a.symbol=b.symbol and datediff(a.close_date,b.close_date) BETWEEN 1 AND "+str(w)+" group by a.symbol, a.close_date")
    print("... Finished ff_stock_cf_w1_"+str(w)+"..."+time.strftime('%Y-%m-%d %H:%M:%S'))
runsql("drop table if exists ff_stock_cf_w2")
s = ["select * from ff_stock_cf_w1_"+str(w) for w in CF_WINDOWS]
s = " union ".join(s)
runsql("create table ff_stock_cf_w2 as "+s)
runsql("create index ff_stock_cf_w2_i1 on ff_stock_cf_w2 (symbol, close_date)")
runsql("drop table if exists ff_stock_cf_w3")
runsql("create table ff_stock_cf_w3 as select * from (select symbol, close_date, max(if(high>h,d,0)) hh, max(if(close>h,d,0)) ch, min(if(close>m,d,999)) cc, min(if(close<m,d,999)) ccl, max(if(low<l,d,0)) ll, max(if(close<l,d,0)) cl, count(1) n from ff_stock_cf_w2 group by symbol, close_date) a where n="+str(len(CF_WINDOWS)))
runsql("create index ff_stock_cf_w3_i1 on ff_stock_cf_w3 (symbol, close_date)")
runsql("drop table if exists ff_stock_cf_w4")
s = ''
for x in ['h','l','m']:
    for w in CF_WINDOWS:
      s += ", sum(if(d="+str(w)+","+x+",0)) " + x + str(w)
s = "create table ff_stock_cf_w4 as select a.symbol, a.close_date, any_value(high) high, any_value(low) low, any_value(open) open, any_value(close) close, any_value(hh) hh, any_value(ch) ch, any_value(cc) cc, any_value(ccl) ccl, any_value(ll) ll, any_value(cl) cl" + s + " from ff_stock_cf_w2 a, ff_stock_cf_w3 b where a.symbol=b.symbol and a.close_date=b.close_date group by a.symbol, a.close_date"
runsql(s)
runsql("create index ff_stock_cf_w4_i1 on ff_stock_cf_w4 (symbol, close_date)")
runsql("drop table if exists ff_stock_cf_w5")
runsql("create table ff_stock_cf_w5 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, floor(@rn/(cnt+1)*1000) bin_1000, floor(@rn/(cnt+1)*10000) bin_10000, a.* from (select a.*, cnt from (select symbol, close_date, ch from ff_stock_cf_w4) a, (select count(1) cnt from ff_stock_cf_w4) b order by ch) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_cf_w6")
runsql("create table ff_stock_cf_w6 as select 0 bin, -9999 min_ch, (select min(ch) from ff_stock_cf_w5) max_ch union select a.bin, a.min_ch, b.min_ch max_ch from (select bin+1 bin, min(ch) min_ch from ff_stock_cf_w5 where bin>=0 group by bin+1) a, (select bin bin, min(ch) min_ch from ff_stock_cf_w5 where bin>0 group by bin) b where a.bin=b.bin union select 100 bin, (select max(ch) from ff_stock_cf_w5) min_ch, 9999 max_ch")
runsql("drop table if exists ff_stock_cf_w7")
runsql("create table ff_stock_cf_w7 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, floor(@rn/(cnt+1)*1000) bin_1000, floor(@rn/(cnt+1)*10000) bin_10000, a.* from (select a.*, cnt from (select symbol, close_date, cl from ff_stock_cf_w4) a, (select count(1) cnt from ff_stock_cf_w4) b order by cl) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_cf_w8")
runsql("create table ff_stock_cf_w8 as select 0 bin, -9999 min_cl, (select min(cl) from ff_stock_cf_w7) max_cl union select a.bin, a.min_cl, b.min_cl max_cl from (select bin+1 bin, min(cl) min_cl from ff_stock_cf_w7 where bin>=0 group by bin+1) a, (select bin bin, min(cl) min_cl from ff_stock_cf_w7 where bin>0 group by bin) b where a.bin=b.bin union select 100 bin, (select max(cl) from ff_stock_cf_w7) min_cl, 9999 max_cl")
runsql("drop table if exists ff_stock_cf_w9")
runsql("create table ff_stock_cf_w9 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, floor(@rn/(cnt+1)*1000) bin_1000, floor(@rn/(cnt+1)*10000) bin_10000, a.* from (select a.*, cnt from (select symbol, close_date, hh from ff_stock_cf_w4) a, (select count(1) cnt from ff_stock_cf_w4) b order by hh) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_cf_w10")
runsql("create table ff_stock_cf_w10 as select 0 bin, -9999 min_hh, (select min(hh) from ff_stock_cf_w9) max_hh union select a.bin, a.min_hh, b.min_hh max_hh from (select bin+1 bin, min(hh) min_hh from ff_stock_cf_w9 where bin>=0 group by bin+1) a, (select bin bin, min(hh) min_hh from ff_stock_cf_w9 where bin>0 group by bin) b where a.bin=b.bin union select 100 bin, (select max(hh) from ff_stock_cf_w9) min_hh, 9999 max_hh")
runsql("drop table if exists ff_stock_cf_w11")
runsql("create table ff_stock_cf_w11 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, floor(@rn/(cnt+1)*1000) bin_1000, floor(@rn/(cnt+1)*10000) bin_10000, a.* from (select a.*, cnt from (select symbol, close_date, ll from ff_stock_cf_w4) a, (select count(1) cnt from ff_stock_cf_w4) b order by ll) a, (select @rn:=0) b")
runsql("drop table if exists ff_stock_cf_w12")
runsql("create table ff_stock_cf_w12 as select 0 bin, -9999 min_ll, (select min(ll) from ff_stock_cf_w11) max_ll union select a.bin, a.min_ll, b.min_ll max_ll from (select bin+1 bin, min(ll) min_ll from ff_stock_cf_w11 where bin>=0 group by bin+1) a, (select bin bin, min(ll) min_ll from ff_stock_cf_w11 where bin>0 group by bin) b where a.bin=b.bin union select 100 bin, (select max(ll) from ff_stock_cf_w11) min_ll, 9999 max_ll")
print("Done ceilfloor profiling... "+time.strftime('%Y-%m-%d %H:%M:%S'))



# Fame Ahead related
runsql("drop table if exists ff_stock_fameon_w1")
runsql("create table ff_stock_fameon_w1 as select symbol, stype, dateb, max(batched) maxb, count(1) n from (select symbol, if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)) stype, date(batched) dateb, batched from ff_status_scan where batched>=date_sub(curdate() , interval 6 month)) a group by symbol, stype, dateb")
runsql("drop table if exists ff_stock_fameon_w2")
runsql("create table ff_stock_fameon_w2 as select distinct(dateb) dateb from ff_stock_fameon_w1")
runsql("drop table if exists ff_stock_fameon_w3")
runsql("create table ff_stock_fameon_w3 as select a.*, \
  (select min(close_date) from ff_stock_w40 where close_date>=date_add(dateb , interval 2 day)) date2d, \
  (select min(close_date) from ff_stock_w40 where close_date>=date_add(dateb , interval 1 week)) date1w, \
  (select min(close_date) from ff_stock_w40 where close_date>=date_add(dateb , interval 2 week)) date2w, \
  (select min(close_date) from ff_stock_w40 where close_date>=date_add(dateb , interval 1 month)) date1m, \
  (select min(close_date) from ff_stock_w40 where close_date>=date_add(dateb , interval 2 month)) date2m \
from ff_stock_fameon_w2 a")
runsql("drop table if exists ff_stock_fameon_w4")
runsql("create table ff_stock_fameon_w4 as select a.*, date2d, date1w, date2w, date1m, date2m from ff_stock_fameon_w1 a, ff_stock_fameon_w3 b where a.dateb=b.dateb")
runsql("create index ff_stock_fameon_w4_i1 on ff_stock_fameon_w4 (symbol, dateb, date2d, date1w, date2w, date1m, date2m)")
runsql("drop table if exists ff_stock_fameon_w5")
runsql("create table ff_stock_fameon_w5 as select a.*, cb.close closeb, c2d.close close2d, c1w.close close1w, c2w.close close2w, c1m.close close1m, c2m.close close2m from ff_stock_fameon_w4 a inner join ff_stock cb on a.symbol=cb.symbol and a.dateb=cb.close_date left join ff_stock c2d on a.symbol=c2d.symbol and a.date2d=c2d.close_date left join ff_stock c1w on a.symbol=c1w.symbol and a.date1w=c1w.close_date left join ff_stock c2w on a.symbol=c2w.symbol and a.date2w=c2w.close_date left join ff_stock c1m on a.symbol=c1m.symbol and a.date1m=c1m.close_date left join ff_stock c2m on a.symbol=c2m.symbol and a.date2m=c2m.close_date")
runsql("drop table if exists ff_stock_fameon_w6")
runsql("create table ff_stock_fameon_w6 as select a.*, (close2d-closeb)/closeb chr2d, (close1w-closeb)/closeb chr1w, (close2w-closeb)/closeb chr2w, (close1m-closeb)/closeb chr1m, (close2m-closeb)/closeb chr2m from ff_stock_fameon_w5 a")
runsql("create index ff_stock_fameon_w6_i1 on ff_stock_fameon_w6 (symbol, stype, dateb)")
runsql("drop table if exists ff_stock_fameon_w7")
runsql("create table ff_stock_fameon_w7 as select a.dateb, b.rn, c1.close_date dated1, c2.close_date dated2, c3.close_date dated3, c4.close_date dated4, c5.close_date dated5, c6.close_date dated6, c7.close_date dated7, c8.close_date dated8, c9.close_date dated9, c10.close_date dated10 from ff_stock_fameon_w2 a inner join ff_stock_w40 b on a.dateb=b.close_date \
        left join ff_stock_w40 c1 on b.rn=c1.rn+1 left join ff_stock_w40 c2 on b.rn=c2.rn+2 left join ff_stock_w40 c3 on b.rn=c3.rn+3 left join ff_stock_w40 c4 on b.rn=c4.rn+4 left join ff_stock_w40 c5 on b.rn=c5.rn+5 left join ff_stock_w40 c6 on b.rn=c6.rn+6 left join ff_stock_w40 c7 on b.rn=c7.rn+7 left join ff_stock_w40 c8 on b.rn=c8.rn+8 left join ff_stock_w40 c9 on b.rn=c9.rn+9 left join ff_stock_w40 c10 on b.rn=c10.rn+10")
runsql("drop table if exists ff_stock_fameon_w8")
runsql("create table ff_stock_fameon_w8 as select a.*, rn, dated1, dated2, dated3, dated4, dated5, dated6, dated7, dated8, dated9, dated10 from ff_stock_fameon_w1 a, ff_stock_fameon_w7 b where a.dateb=b.dateb and b.rn>0")
runsql("create index ff_stock_fameon_w8_i1 on ff_stock_fameon_w8 (symbol, dateb, dated1, dated2, dated3, dated4, dated5, dated6, dated7, dated8, dated9, dated10)")
runsql("drop table if exists ff_stock_fameon_w9")
runsql("create table ff_stock_fameon_w9 as \
    select a.*, cb.close closeb, c1.close closed1, c2.close closed2, c3.close closed3, c4.close closed4, c5.close closed5, c6.close closed6, c7.close closed7, c8.close closed8, c9.close closed9, c10.close closed10 \
    from ff_stock_fameon_w8 a inner join ff_stock cb on a.symbol=cb.symbol and a.dateb=cb.close_date \
    left join ff_stock c1 on a.symbol=c1.symbol and a.dated1=c1.close_date \
    left join ff_stock c2 on a.symbol=c2.symbol and a.dated2=c2.close_date \
    left join ff_stock c3 on a.symbol=c3.symbol and a.dated3=c3.close_date \
    left join ff_stock c4 on a.symbol=c4.symbol and a.dated4=c4.close_date \
    left join ff_stock c5 on a.symbol=c5.symbol and a.dated5=c5.close_date \
    left join ff_stock c6 on a.symbol=c6.symbol and a.dated6=c6.close_date \
    left join ff_stock c7 on a.symbol=c7.symbol and a.dated7=c7.close_date \
    left join ff_stock c8 on a.symbol=c8.symbol and a.dated8=c8.close_date \
    left join ff_stock c9 on a.symbol=c9.symbol and a.dated9=c9.close_date \
    left join ff_stock c10 on a.symbol=c10.symbol and a.dated10=c10.close_date")
runsql("drop table if exists ff_stock_fameon_w10")
runsql("create table ff_stock_fameon_w10 as select a.* , (closed1-closeb)/closeb chrd1, (closed2-closeb)/closeb chrd2, (closed3-closeb)/closeb chrd3, (closed4-closeb)/closeb chrd4, (closed5-closeb)/closeb chrd5, (closed6-closeb)/closeb chrd6, (closed7-closeb)/closeb chrd7, (closed8-closeb)/closeb chrd8, (closed9-closeb)/closeb chrd9, (closed10-closeb)/closeb chrd10 \
       , (closed2-closed1)/closed1 chr12, (closed3-closed2)/closed2 chr23, (closed4-closed3)/closed3 chr34, (closed5-closed4)/closed4 chr45, (closed6-closed5)/closed5 chr56, (closed7-closed6)/closed6 chr67, (closed8-closed7)/closed7 chr78, (closed9-closed8)/closed8 chr89, (closed10-closed9)/closed9 chr910 from ff_stock_fameon_w9 a")
runsql("create index ff_stock_fameon_w10_i1 on ff_stock_fameon_w10 (symbol, stype, dateb)")
runsql("drop table if exists ff_stock_fameon_w11")
runsql("create table ff_stock_fameon_w11 as select a.symbol, a.stype, a.dateb, a.maxb, b.rn, a.closeb, close2d, close1w, close2w, close1m, close2m, chr2d, chr1w, chr2w, chr1m, chr2m, chrd1, chrd2, chrd3, chrd4, chrd5, chrd6, chrd7, chrd8, chrd9, chrd10, chr12, chr23, chr34, chr45, chr56, chr67, chr78, chr89, chr910 from ff_stock_fameon_w6 a, ff_stock_fameon_w10 b where a.symbol=b.symbol and a.stype=b.stype and a.dateb=b.dateb")
runsql("create index ff_stock_fameon_w11_i1 on ff_stock_fameon_w11 (dateb, symbol, stype)")
runsql("create index ff_stock_fameon_w11_i2 on ff_stock_fameon_w11 (symbol, stype, dateb)")
runsql("drop table if exists ff_stock_fameon_w12")
runsql("create table ff_stock_fameon_w12 as select symbol, dateb, group_concat(stype order by stype) sstype, any_value(closeb) closeb \
       , any_value(close2d) close2d, any_value(close1w) close1w, any_value(close2w) close2w, any_value(close1m) close1m, any_value(close2m) close2m \
       , any_value(chr2d) chr2d, any_value(chr1w) chr1w, any_value(chr2w) chr2w, any_value(chr1m) chr1m, any_value(chr2m) chr2m \
       , any_value(chrd1) chrd1, any_value(chrd2) chrd2, any_value(chrd3) chrd3, any_value(chrd4) chrd4, any_value(chrd5) chrd5, any_value(chrd6) chrd6, any_value(chrd7) chrd7, any_value(chrd8) chrd8, any_value(chrd9) chrd9, any_value(chrd10) chrd10 \
       , any_value(chr12) chr12, any_value(chr23) chr23, any_value(chr34) chr34, any_value(chr45) chr45, any_value(chr56) chr56, any_value(chr67) chr67, any_value(chr78) chr78, any_value(chr89) chr89, any_value(chr910) chr910 \
       from ff_stock_fameon_w11 group by dateb, symbol")
runsql("create index ff_stock_fameon_w12_i1 on ff_stock_fameon_w12 (symbol, sstype)")
runsql("drop table if exists ff_stock_fameon_w13")
runsql("create table ff_stock_fameon_w13 as select symbol, stype, cnt, rk, @rk n_rk, greatest(floor(rk/(@n+1)*100),1) bin from (select a.symbol, a.stype, @p:=@c dummy, @c:=a.cnt cnt, @n:=@n+1 n, @rk:=if(@p=@c,@rk,@n) rk from (select symbol, stype, count(1) cnt from ff_stock_fameon_w11 group by symbol, stype order by cnt) a, (select @rk:=0,@c:=null,@p:=null,@n:=0) b) a")
runsql("create index ff_stock_fameon_w13_i1 on ff_stock_fameon_w13 (symbol, stype, cnt)")
runsql("drop table if exists ff_stock_fameon_w20")
runsql("create table ff_stock_fameon_w20 as select a.* \
       , (select min(close_date) from ff_stock_w40 where close_date>=date_add(a.close_date , interval 2 day)) date2d \
       , (select min(close_date) from ff_stock_w40 where close_date>=date_add(a.close_date , interval 1 week)) date1w \
       , (select min(close_date) from ff_stock_w40 where close_date>=date_add(a.close_date , interval 2 week)) date2w \
       , (select min(close_date) from ff_stock_w40 where close_date>=date_add(a.close_date , interval 1 month)) date1m \
       , (select min(close_date) from ff_stock_w40 where close_date>=date_add(a.close_date , interval 2 month)) date2m \
       from ff_stock_w40 a")
runsql("create index ff_stock_fameon_w20_i1 on ff_stock_fameon_w20 (close_date)")


# refresh cache of Baking Items
from status_scan import cache_baking
cache_baking()

# maintenance routine
from sys_maintain import maintain_tasks
maintain_tasks()


from finnews_sense import build_sense
build_sense()
