# -*- coding: utf-8 -*-
"""
Created on Sun Sep  9 23:03:49 2018

@author: jsu
"""

import sys
import time
import requests
import datetime, pytz
import numpy as np
from util_logging import Log

utc = pytz.timezone('UTC')
eastern = pytz.timezone('US/Eastern')

#from dateutil import parser
#from get_sp500 import refresh_sp500
from util_mysql import table_exist, runsql, fetch_rawsql, dbclose, ForceRefreshTable

status_scan_starttime = datetime.datetime.now()
FF_SCAN_HOST          = "https://foliofame.com"
FORCE_RUN             = ForceRefreshTable
MINUTES_TRADING_SCANS = 2  # gap minutes between now and last entry of last scan
MINUTES_FRESH_SCANS   = 60 # ensure latest IEX price is within this minute amount
MAX_ROTTEN            = 20 # number of rotten scanned symbols before sys.exit()
MIN_MARKETCAP         = 10**9 # filtering out very small caps

N_OVERALL_CACHE       = 20  # caching the overall famelist
AGING_TIME_FACTOR     = 2   # time factor for overall famelist
AGING_RAND_SCALE      = 10  # largest randomization scale for overall famelist
AGING_MATURE_HOUR     = 15  # saturating the aging for overall famelist

NON_SCAN_LIST = "NDAQ,DIA".split(",")

FF_STATUS_SCAN = """create table ff_status_scan (
symbol varchar(10),
quote float,
changePct float,
marketcap float,
updated datetime,
scanned datetime,
batched datetime, 
stype varchar(10),
rarity varchar(30),
context varchar(255),
to_tweet varchar(255),
infov float,
status varchar(10)
) character set utf8 collate utf8_unicode_ci
""".replace('\n', ' ').replace('\r', '')

FF_STATUS_SCAN_A1 = """create table ff_status_scan_a1 (
symbol varchar(10),
sector varchar(100),
changePct float,
marketcap float,
updated datetime,
batched datetime
) character set utf8 collate utf8_unicode_ci
""".replace('\n', ' ').replace('\r', '')


VOL_TEMPLATE = [
        {"tweet": u"&STOCK traded &RARITY volume with &VOLUME shares (&Z\u03C3) up to now &URL", "prob": 0.3},
        {"tweet": u"&RARITY &VOLUME-share volume for &STOCK at this point (&Z\u03C3) &URL - or info hub &FH", "prob": 0.3},
        {"tweet": u"&Z standard deviations above average trading volume on &STOCK currently &URL (&RARITY &VOLUME shares)", "prob": 0.4},
        ]
PFL_TEMPLATE = [
        {"tweet": u"&STOCK fluctuated &RARITY at &FLUX of previous closing price &URL", "prob": 0.4},
        {"tweet": u"&RARITY price move range for &STOCK today between &L and &H &URL", "prob": 0.4},
        {"tweet": u"see &URL for insights on &RARITY &FLUX price flux of &STOCK today &FH", "prob": 0.2},
        ]
CHG_TEMPLATE = [
        {"tweet": u"&STOCK currently &MOVE &CHG% &URL - overview at &FH", "prob": 0.2},
        {"tweet": u"&STOCK &HAVE &CHG% &JS &URL", "prob": 0.4},
        {"tweet": u"&STOCK &MOVE &RARITYly for &CHG% so far &URL", "prob": 0.2},
        {"tweet": u"&URL insights on why &STOCK &MOVE &CHG% at this point &FH", "prob": 0.2},
        ]
CFP_TEMPLATE = [
        {"tweet": u"&STOCK &TARGET &MOVE &URL - full &STOCK hub &FH", "prob": 0.4},
        {"tweet": u"&TARGET &MOVE for &STOCK &URL", "prob": 0.3},
        {"tweet": u"&URL for insights on &MOVE of &STOCK today", "prob": 0.3},
        ]


headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.90 Safari/537.36'}

INSERT_SQL = "insert into ff_status_scan (symbol, quote, changePct, marketcap, updated, scanned, batched, stype, rarity, context, to_tweet, infov) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
INSERT_A1  = "insert into ff_status_scan_a1 (symbol, sector, changePct, marketcap, updated, batched) values (%s,%s,%s,%s,%s,%s)"




def assure_tables():
    if not table_exist("ff_status_scan"):
        runsql(FF_STATUS_SCAN)
        runsql("create index ff_status_scan_i1 on ff_status_scan (batched)")
        runsql("create index ff_status_scan_i2 on ff_status_scan (status)")
    else:
        a = fetch_rawsql("show table status like 'ff_status_scan'")
        a = a[0]['Collation']
        if a != 'utf8_unicode_ci':
            runsql("ALTER TABLE ff_status_scan CONVERT TO CHARACTER SET utf8 COLLATE utf8_unicode_ci")
    # maintenance related on collation correction
    if table_exist("ff_scan_symbols"):
        a = fetch_rawsql("show table status like 'ff_scan_symbols'")
        a = a[0]['Collation']
        if a != 'utf8_unicode_ci':
            runsql("ALTER TABLE ff_scan_symbols CONVERT TO CHARACTER SET utf8 COLLATE utf8_unicode_ci")



def get_eastern():
    return utc.localize(datetime.datetime.utcnow()).astimezone(eastern).strftime("%Y-%m-%d %H:%M:%S")

def R(f=0.5):
    if f<0 or f>1:
        return False
    if np.random.random() < f:
        return True
    else:
        return False

# Allowing external call to refresh cache
def cache_baking():
    print("Caching Baking list ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    runsql("drop table if exists ff_status_scan_o1")
    rawsql = "create table ff_status_scan_o1 as select symbol, stype, infov, w_micd from \
          (select a.*, td+w_mic*md w_micd, @rn:=if(@s=symbol,@rn+1,0) rn, @s:=symbol s from \
          (select a.symbol, marketCap, updated, scanned, stype, rarity, context, infov, if(stype='vol',if(md>1,1,md),1) md, if(td>"+str(AGING_TIME_FACTOR)+","+str(AGING_TIME_FACTOR)+",td)*rand()*"+str(AGING_RAND_SCALE)+" td, (log10(marketCap)-9)*(infov-90)*(log10(abs(changePct*10000)+1)) w_mic from \
            (select a.*, (hour(updated)*60+minute(updated))/"+str(AGING_MATURE_HOUR*60)+" md, if(timestampdiff(minute,batched,utc_timestamp())<200,0,(timestampdiff(minute,batched,utc_timestamp())-200)/480) td from ff_status_scan a) a, \
              (select batched as max_batched from ff_status_scan_w1 where n_symbol>=20 order by rn limit 1) b where a.batched=b.max_batched order by w_mic desc limit "+str(N_OVERALL_CACHE*4)+") a, \
            (select @s:='',@rn:=0) b order by marketCap desc, w_micd desc \
          ) a where rn=0 order by w_micd desc limit "+str(N_OVERALL_CACHE)
    runsql(rawsql)
    runsql("drop table if exists ff_status_scan_o2")
    runsql("create table ff_status_scan_o2 as select a.*, c.w_micd from ff_status_scan a, (select batched as max_batched from ff_status_scan_w1 where n_symbol>=20 order by rn limit 1) b, ff_status_scan_o1 c where a.batched=b.max_batched and a.symbol=c.symbol order by w_micd desc")
    runsql("drop table if exists ff_status_scan_o3")
    runsql("create table ff_status_scan_o3 as select (@rn:=if(@s=symbol,@rn,@rn+1))*1 rn, @s:=symbol symbol, quote, changePct, marketcap, stype, context, infov, w_micd from ff_status_scan_o2 a, (select @rn:=0, @s:='') b")
    S = fetch_rawsql("select rn, symbol, max(quote) quote, max(changePct) changePct, max(marketcap) marketcap, max(w_micd) w_micd from ff_status_scan_o3 group by rn, symbol")
    if S:
        for s in S:
            r = requests.get(FF_SCAN_HOST + "/api/v1/fame66/w52/"+s['symbol']+"/", headers=headers)
            if r.status_code == 200:
                r = r.json()
                if 'datasets' in r:
                    ctx = r['datasets'][0]
                    ctx = str(ctx)
                    if len(ctx) <= 255:
                        runsql("insert into ff_status_scan_o3 (rn, symbol, quote, changePct, marketcap, stype, context, infov, w_micd) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (s['rn'],s['symbol'],s['quote'],s['changePct'],s['marketcap'],'f6w',ctx,0,s['w_micd']))
                    else:
                        print("ctx longer than 255 for fame66 support of "+s['symbol'])
            r = requests.get(FF_SCAN_HOST + "/api/v1/famebits/f66/"+s['symbol']+"/", headers=headers)
            if r.status_code == 200:
                r = r.json()
                if 'bits' in r:
                    a = [i['pr'] for i in r['bits']]
                    b = [i['c_diff'] for i in r['bits']]
                    ctx = str({"pr":a, "c_diff":b})
                    if len(ctx) <= 255:
                        runsql("insert into ff_status_scan_o3 (rn, symbol, quote, changePct, marketcap, stype, context, infov, w_micd) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (s['rn'],s['symbol'],s['quote'],s['changePct'],s['marketcap'],'f66',ctx,0,s['w_micd']))
                    else:
                        print("ctx longer than 255 for fame66 chart of "+s['symbol'])
            r = requests.get(FF_SCAN_HOST + "/api/v1/famebits/ahd/"+s['symbol']+"/", headers=headers)
            if r.status_code == 200:
                r = r.json()
                if 'target' in r:
                    if r['target'] == 'self':
                        ctx = str(r)
                        if len(ctx) <= 255:
                            runsql("insert into ff_status_scan_o3 (rn, symbol, quote, changePct, marketcap, stype, context, infov, w_micd) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (s['rn'],s['symbol'],s['quote'],s['changePct'],s['marketcap'],'ahd',ctx,r['I'],s['w_micd']))
                        else:
                            print("ctx longer than 255 for Fame Ahead of "+s['symbol'])
    runsql("drop table if exists ff_status_scan_o4")
    runsql("create table ff_status_scan_o4 as select * from ff_status_scan_o3 order by rn")
    runsql("create index ff_status_scan_o4_i1 on ff_status_scan_o4 (rn)")
    runsql("create index ff_status_scan_o4_i2 on ff_status_scan_o4 (stype, infov, marketcap)")
    print("Done caching Baking list ... "+time.strftime('%Y-%m-%d %H:%M:%S'))


def do_scan():
    status_scan_starttime = datetime.datetime.now()
    assure_tables()
    
    symbols = fetch_rawsql("select symbol, sector from ff_scan_symbols where datediff(now(),last_updated)<14")
    s = [i['symbol'] for i in symbols]
    r = requests.get(FF_SCAN_HOST + "/api/v1/misc/nonsp/")
    if r.status_code != 200:
        print("Failed to retrieve list of non-SP500 symbols")
    else:
        r = r.json()
        for i in r['symbol_list']:
            if i in s or i in NON_SCAN_LIST:
                continue
            symbols += [{'symbol':i,'sector':''}]

    # stop when:
    # 1. data not stablized, before 9:45am
    # 2. more than 1 hour after trading stopped 
    # 3. none-trading days
    enow = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)
    etime = enow.hour + enow.minute/60
    if enow.weekday() < 5 and etime > 9.75 and etime < 17.5:
        has_recent_scans = fetch_rawsql("select count(1) cnt from ff_status_scan where timestampdiff(minute, scanned, '"+get_eastern()+"') < " + str(MINUTES_TRADING_SCANS))[0]['cnt']
        if has_recent_scans:
            print("Already scanned status in the last " + str(MINUTES_TRADING_SCANS) + " minutes. Cooldown even if FORCE_RUN")
            dbclose()
            sys.exit()
    elif not FORCE_RUN:
        print("Not during trading hours - skipped status scan")
        dbclose()
        sys.exit()

    # Clear scan cache only when scan actually runs
    if table_exist("ff_status_scan_a1"):
        runsql("drop table ff_status_scan_a1")
    runsql(FF_STATUS_SCAN_A1)

    n_rotten   = 0
    for s0 in symbols:
        s = s0['symbol']
        print("Scanning "+s+" ...")
        try:
            q = requests.get("https://api.iextrading.com/1.0/stock/"+s+"/quote")
            q = q.json()
        except:
            print("- bad IEX call for "+s+" ... skipped")
            continue
            """
            print("Unexpected error:", sys.exec_info()[0])
            raise
    		"""
        # check required keys
        if not ('calculationPrice' in q and 'latestPrice' in q and 'changePercent' in q and 'marketCap' in q and 'latestUpdate' in q and 'primaryExchange' in q):
            print("- bad IEX return format for "+s+" ... skipped")
            continue
        if 'Arca' in q['primaryExchange']:
            print("- not scanning ETF "+s+" ... skipped")
            continue
        if q['marketCap'] < MIN_MARKETCAP:
            print("- MarketCap too low to scan,  for "+s+" ... skipped")
            continue
        
        # double-check if IEX actually returns the latest quote
        updated = utc.localize(datetime.datetime.utcfromtimestamp(q['latestUpdate']//1000)).astimezone(eastern)
        print(enow, updated)
        diff = enow - updated
        dmin = (diff.days * 86400 + diff.seconds) // 60
        if dmin > MINUTES_FRESH_SCANS and not FORCE_RUN:
            print("- rotten/older IEX return data for "+s+" ... skipped")
            n_rotten += 1
            if n_rotten >= MAX_ROTTEN:
                sys.exit()
            continue
    
        # Upon the first IEX fresh data of today, swap out yesterday's benchmark ceil-floor tables (from get_stock_adj)
        # *The benchmark tables should only be updated at the time market opens
        if s == symbols[0]['symbol'] and q['calculationPrice'] == 'tops':
            if table_exist("ff_stock_cf_w00") and table_exist("ff_stock_cf_w0"):
                runsql("drop table ff_stock_cf_w0")
                runsql("create table ff_stock_cf_w0 as select * from ff_stock_cf_w00")
                runsql("create index ff_stock_cf_w0_i1 on ff_stock_cf_w0 (symbol)")
                runsql("drop table ff_stock_cf_w00")
    
        # FF_scans - Volume
        while True:
            r = requests.get(FF_SCAN_HOST + "/api/v1/famebits/vol/"+s+"/", headers=headers)
            if r.status_code != 429:
                break
            time.sleep(5)
        try:
            r = r.json()
            if r['I']>90 and 'high' in r['rarity']:
                msg = VOL_TEMPLATE[np.random.choice(len(VOL_TEMPLATE), p=[e['prob'] for e in VOL_TEMPLATE], size=1)[0]]["tweet"]
                msg = msg.replace("&STOCK", "$"+s)
                msg = msg.replace("&RARITY", r['rarity'])
                msg = msg.replace("&VOLUME", r['volume_human'])
                msg = msg.replace("&Z", "{0:.1f}".format(r['z']))
                msg = msg.replace("&URL", FF_SCAN_HOST+"fb/vol/"+s+"/")
                msg = msg.replace("&FH", FF_SCAN_HOST+"/fh/"+s+"/")
                #ctx = str({"v": r['volume_human'], "z": "{0:.1f}".format(r['z'])})
                ctx = str(r)
                val = (s, q['latestPrice'], q['changePercent'], q['marketCap'], updated.strftime("%Y-%m-%d %H:%M:%S"), get_eastern(), enow.strftime("%Y-%m-%d %H:%M:%S"), 'vol', r['rarity'], ctx, msg, r['I'])
                runsql(INSERT_SQL, val)
        except Exception as e:
            print(e)
            print("- error FF vol scan for "+s+" ... skipped")
            print(r)

        # FF_scans - Volatility + Fluctuation
        while True:
            r = requests.get(FF_SCAN_HOST + "/api/v1/famebits/pfl/"+s+"/", headers=headers)
            if r.status_code != 429:
                break
            time.sleep(5)
        try:
            r = r.json()
            if r['I']>90 and 'large' in r['rarity']:
                msg = PFL_TEMPLATE[np.random.choice(len(PFL_TEMPLATE), p=[e['prob'] for e in PFL_TEMPLATE], size=1)[0]]["tweet"]
                msg = msg.replace("&STOCK", "$"+s)
                msg = msg.replace("&RARITY", r['rarity'])
                msg = msg.replace("&URL", FF_SCAN_HOST+"/fb/vol/"+s+"/")
                msg = msg.replace("&FLUX", str(r['hl_ratio'])+"%")
                msg = msg.replace("&L", str(r['low']))
                msg = msg.replace("&H", str(r['high']))
                msg = msg.replace("&FH", FF_SCAN_HOST+"/fh/"+s+"/")
                #ctx = str({"f": r['hl_ratio'], "l": r['low'], "h": r['high']})
                ctx = str(r)
                val = (s, q['latestPrice'], q['changePercent'], q['marketCap'], updated.strftime("%Y-%m-%d %H:%M:%S"), get_eastern(), enow.strftime("%Y-%m-%d %H:%M:%S"), 'pfl', r['rarity'], ctx, msg, r['I'])
                runsql(INSERT_SQL, val)
        except Exception as e:
            print(e)
            print("- error FF pfl scan for "+s+" ... skipped")
            print(r)

        # FF_scans - Single Day Change
        while True:
            r = requests.get(FF_SCAN_HOST + "/api/v1/famebits/chg/"+s+"/", headers=headers)
            if r.status_code != 429:
                break
            time.sleep(5)
        try:
            r = r.json()
            if s0['sector']:
                val = (s, s0['sector'], q['changePercent'], q['marketCap'], updated.strftime("%Y-%m-%d %H:%M:%S"), enow.strftime("%Y-%m-%d %H:%M:%S"))
                runsql(INSERT_A1, val)
            if r['I']>90 and 'large' in r['rarity']:
                msg = CHG_TEMPLATE[np.random.choice(len(CHG_TEMPLATE), p=[e['prob'] for e in CHG_TEMPLATE], size=1)[0]]["tweet"]
                msg = msg.replace("&STOCK", "$"+s)
                msg = msg.replace("&RARITY", r['rarity'])
                msg = msg.replace("&CHG", str(abs(round(r['chg']*100,2))))
                msg = msg.replace("&MOVE", r['move'])
                msg = msg.replace("&URL", FF_SCAN_HOST+"/fb/chg/"+s+"/")
                msg = msg.replace("&FH", FF_SCAN_HOST+"/fh/"+s+"/")
                msg = msg.replace("&HAVE", ("is having" if r['status']=="live" else "had"))
                msg = msg.replace("&JS", (("roar" if "extreme" in r['rarity'] else ("jump" if "very" in r['rarity'] else "gain")) if r['chg']>0 else ("crash" if "extreme" in r['rarity'] else ("dive" if "very" in r['rarity'] else "drop"))))
                #ctx = str({"c": r['chg'], "m": r['move'], "js": r['js']})
                ctx = str(r)
                val = (s, q['latestPrice'], q['changePercent'], q['marketCap'], updated.strftime("%Y-%m-%d %H:%M:%S"), get_eastern(), enow.strftime("%Y-%m-%d %H:%M:%S"), 'chg', r['rarity'], ctx, msg, r['I'])
                runsql(INSERT_SQL, val)
        except Exception as e:
            print(e)
            print("- error FF chg scan for "+s+" ... skipped")
            print(r)
        
        # FF_scans - Ceiling Floor Penetration
        while True:
            r = requests.get(FF_SCAN_HOST + "/api/v1/famebits/cfp/"+s+"/", headers=headers)
            if r.status_code != 429:
                break
            time.sleep(5)
        try:
            r = r.json()
            if r['I']>90 and r['target']=='quoted':
                msg = CFP_TEMPLATE[np.random.choice(len(CFP_TEMPLATE), p=[e['prob'] for e in CFP_TEMPLATE], size=1)[0]]["tweet"]
                msg = msg.replace("&STOCK", "$"+s)
                msg = msg.replace("&TARGET", r['target'])
                msg = msg.replace("&MOVE", r['move'])
                msg = msg.replace("&URL", FF_SCAN_HOST+"/fb/dme/"+s+"/")
                msg = msg.replace("&FH", FF_SCAN_HOST+"/fh/"+s+"/")
                #ctx = str({"t": r['target'], "m": r['move']})
                ctx = str(r)
                val = (s, q['latestPrice'], q['changePercent'], q['marketCap'], updated.strftime("%Y-%m-%d %H:%M:%S"), get_eastern(), enow.strftime("%Y-%m-%d %H:%M:%S"), 'cfp', r['rarity'], ctx, msg, r['I'])
                runsql(INSERT_SQL, val)
        except Exception as e:
            print(e)
            print("- error FF cfp scan for "+s+" ... skipped")
            print(r)
        

    runsql("drop table if exists ff_status_scan_w1")
    runsql("create table ff_status_scan_w1 as select a.*, @rn:=@rn+1 rn from (select batched, count(1) n_item, count(distinct symbol) n_symbol from ff_status_scan group by batched order by batched desc) a, (select @rn:=0) b")
    runsql("create index ff_status_scan_w1_i1 on ff_status_scan_w1 (n_symbol, rn)")
    runsql("drop table if exists ff_status_scan_w2")
    runsql("create table ff_status_scan_w2 as select stype, if(changePct>=0,'u','d') ch, count(1) n from ff_status_scan a, (select batched as max_batched from ff_status_scan_w1 where n_symbol>=20 order by rn limit 1) b where a.batched=b.max_batched and a.marketcap>"+str(MIN_MARKETCAP)+" group by stype, if(changePct>=0,'u','d')")
    runsql("drop table if exists ff_status_scan_w3")
    runsql("create table ff_status_scan_w3 as select * from ff_status_scan_a1")
    runsql("drop table if exists ff_status_scan_w4")
    runsql("create table ff_status_scan_w4 as select max(batched) batched, sector, count(1) cnt, sum(marketcap) sm, round(sum(changePct*marketcap)) cm, round(sum(changePct*marketcap)/sum(marketcap)*100,2) marketchgPct from ff_status_scan_w3 group by sector having cnt>20 order by marketchgPct desc")
    if not table_exist("ff_status_scan_a2"):
        runsql("create table ff_status_scan_a2 as select * from ff_status_scan_w4")
        runsql("create index ff_status_scan_a2_i1 on ff_status_scan_a2 (batched)")
    else:
        runsql("insert into ff_status_scan_a2 select * from ff_status_scan_w4")
    runsql("drop table if exists ff_status_scan_w5")
    runsql("create table ff_status_scan_w5 as select d.sector, stype, count(1) n, sum(if(changePct>=0,1,0)) n_u, sum(if(changePct<0,1,0)) n_d, any_value(d.cnt) n_sector, any_value(round(count(1)/d.cnt,4)) s_ratio from ff_status_scan a join (select batched as max_batched from ff_status_scan_w1 order by rn limit 1) b on a.batched=b.max_batched join (select symbol, sector from ff_scan_symbols where datediff(now(),last_updated)<60) c on a.symbol=c.symbol right join ff_status_scan_w4 d on c.sector=d.sector group by d.sector, a.stype order by sector, s_ratio desc")
    runsql("create index ff_status_scan_w5_i1 on ff_status_scan_w5 (sector, s_ratio)")
    runsql("drop table if exists ff_status_scan_w6")
    runsql("create table ff_status_scan_w6 as select max(batched) batched, sector, any_value(if(locate(' ',sector)>0, concat(substr(sector,1,1),substr(sector,locate(' ',sector)+1,2)), substr(sector,1,3))) sector3, count(1) cnt, sum(if(changePct>=0,1,0)) n_u, sum(if(changePct<0,1,0)) n_d, sum(marketcap) sm, round(sum(changePct*marketcap)) cm, round(sum(abs(changePct)*marketcap)) am, round(sum(changePct*marketcap)/sum(marketcap)*100,2) marketchgPct from ff_status_scan_w3 group by sector having cnt>20 order by marketchgPct desc")
    runsql("drop table if exists ff_status_scan_w7")
    runsql("create table ff_status_scan_w7 as select a.security, a.subsec, a.hq, b.*, changePct*marketcap marketeff, abs(changePct*marketcap) marketabs from (select symbol, security, subsec, hq from ff_scan_symbols where datediff(now(),last_updated)<60) a, ff_status_scan_w3 b where a.symbol=b.symbol order by marketabs")
    runsql("create index ff_status_scan_w7_i1 on ff_status_scan_w7 (sector, marketabs)")
    runsql("drop table if exists ff_status_scan_w8")
    runsql("create table ff_status_scan_w8 as select b.batched_date, a.* from ff_status_scan_a2 a,(select date(batched) batched_date, max(batched) batched_time from ff_status_scan_a2 group by date(batched)) b where a.batched=b.batched_time")
    runsql("create index ff_status_scan_w8_i1 on ff_status_scan_w8 (sector, batched_date)")
    runsql("create index ff_status_scan_w8_i2 on ff_status_scan_w8 (batched_date)")
    cache_baking()

    status_scan_endtime = datetime.datetime.now()

    timedetail = "status_scan job is running from {0} to {1}, and total runging time is {2}".format( status_scan_starttime, status_scan_endtime, (status_scan_endtime-status_scan_starttime).seconds )
    print(timedetail)
    Log.info("status_scan.py", timedetail)


if __name__ == '__main__':
    do_scan()

