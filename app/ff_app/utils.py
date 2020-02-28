
import random
import requests
import datetime
from django.db import connection
from django.contrib import messages
from ff_app.api_cache import cache_fn_internal
import logging
import pymongo
logger = logging.getLogger(__name__)

def runsql(s):
    cur = connection.cursor()
    try:
        cur.execute(s)
    except Exception as e:
        logger.exception("SQL error")
        raise e
    columns = [col[0] for col in cur.description]
    return [
        dict(zip(columns, row))
        for row in cur.fetchall()
    ]

def table_exist(table):
    cur = connection.cursor()
    try:
        cur.execute("SHOW TABLES LIKE '"+table+"'")
    except Exception as e:
        logger.exception("SQL error")
        raise e
    if cur.fetchone():
        return True
    else:
        return False





@cache_fn_internal(refresh_rate_in_seconds=3600)
def get_SP500():
    if not table_exist("ff_scan_symbols"):
        return []
    r = runsql("select symbol from ff_scan_symbols where datediff(now(),last_updated) < 14")
    symbols = [i['symbol'].replace('-','.').rstrip() for i in r]
    seen = {}
    symbols = [seen.setdefault(x, x) for x in symbols if x not in seen] #dedup
    return symbols


def IEX_validator_single(ss, qd=7, qm=10**9):
    r = requests.get("https://api.iextrading.com/1.0/stock/"+ss+"/quote")
    if r.status_code == 200:
        r = r.json()
        if 'closeTime' in r and 'marketCap' in r:
            if r['closeTime'] and r['marketCap']:
                c = int(r['closeTime']) // 1000
                if (datetime.datetime.today() - datetime.datetime.utcfromtimestamp(c)).days < qd:
                    if r['marketCap'] > qm:
                        return True
    return False

def IEX_validator_batch(q, qd=7, qm=10**9):
    t = []
    for qq in range((len(q)-1)//100+1):
        r = requests.get("https://api.iextrading.com/1.0/stock/market/batch?symbols="+",".join(q[100*qq:100*qq+99])+"&types=quote")
        if r.status_code == 200:
            r = r.json()
            for k in r.keys():
                if 'closeTime' in r[k]['quote'] and 'marketCap' in r[k]['quote']:
                    if r[k]['quote']['closeTime'] and r[k]['quote']['marketCap']:
                        c = int(r[k]['quote']['closeTime']) // 1000
                        if (datetime.datetime.today() - datetime.datetime.utcfromtimestamp(c)).days < qd:
                            if r[k]['quote']['marketCap'] > qm:
                                t += [k]
    seen = {}
    t = [seen.setdefault(x, x) for x in t if x not in seen]
    return t



@cache_fn_internal(refresh_rate_in_seconds=3600)
def get_nonSP500(n_max=800):
    s = get_SP500()
    if not table_exist("ff_logging_viewlog"):
        return s
    p = runsql("select distinct symbol from (select a.uid, a.symbol from ff_app_watchlist a, (select uid, symbol, max(request_dt) mrdt from ff_app_watchlist where symbol<>'' group by uid, symbol) b where a.uid=b.uid and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add') a")
    q = []
    for i in p:
        ii = i['symbol'].upper().replace('-','.').rstrip()
        if ii not in s:
            q.append(ii)
    r = IEX_validator_batch(q)
    p = runsql("select symbol, max(request_dt) dt from ff_logging_viewlog where symbol is not null group by symbol order by dt desc")
    q = []
    for i in p:
        ii = i['symbol'].upper().replace('-','.').rstrip()
        if ii not in s and ii not in r:
            q.append(ii)
    t = IEX_validator_batch(q)
    s = s + r + t
    return s[:n_max]


def standardize_ss(ss):
    return ss.upper().replace('-','.')

def assure_ss(request, ss):
    ss = standardize_ss(ss)
    if not ss:
        messages.warning(request, 'No stock symbol.')
        return ''
    if len(ss) > 6:
        messages.warning(request, 'Invalid stock symbol.')
        return ''
    return ss


def assure_sec(sec):
    if not table_exist("ff_status_scan_w8"):
        return ""
    sec = sec.lower()
    S = runsql("select sector, sector3 from ff_status_scan_w6")
    Sv = [s['sector'] for s in S]
    S3 = [s['sector3'].lower() for s in S]
    if sec not in [s.lower() for s in Sv]:
        if sec not in S3:
            return ""
        else:
            i = S3.index(sec)
            sec = Sv[i]
    else:
        sec = next((i for i in Sv if i.lower() == sec),'')
        if not sec:
            return ""
    return sec

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

def R(f=0.5):
    if f<0 or f>1:
        return False
    if random.random() < f:
        return True
    else:
        return False

def wrap_sector_url(s, objtag="span", objclass="", sametab=True):
    if not table_exist("ff_status_scan_w6") or not table_exist("ff_status_scan_w8"):
        return s
    T = runsql("select sector from ff_status_scan_w6")
    T = [t['sector'] for t in T]
    for t in T:
        s = s.replace(t, "<" + objtag + " class='" + objclass + "' href='/fb/sec/"+t+"/'" + ('' if sametab else " target='_blank'") + '>' + t + '</' + objtag + '>')
    return s
   

def wrap_famer_url(s, objtag="span", objclass="", sametab=True):
    T = s.split(' ')
    U = []
    for t in T:
        if any([i for i in ["soar","rise","rose","jump","gain"] if i in t]):
            t = "<" + objtag + " class='" + objclass + "' href='/fmr/gnr/'" + ('' if sametab else " target='_blank'") + '>' + t + '</' + objtag + '>'
        if any([i for i in ["tank","sink","sank","drop","fall","fell"] if i in t]):
            t = "<" + objtag + " class='" + objclass + "' href='/fmr/lsr/'" + ('' if sametab else " target='_blank'") + '>' + t + '</' + objtag + '>'
        if "fluctuate" in t:
            t = "<" + objtag + " class='" + objclass + "' href='/fmr/pfl/'" + ('' if sametab else " target='_blank'") + '>' + t + '</' + objtag + '>'
        U.append(t)
    U = " ".join(U)
    U = U.replace('90-day low', "<"+objtag+" class='"+objclass+"' href='/fmr/fbk/'"+('' if sametab else " target='_blank'")+'>90-day low</'+objtag+'>')
    U = U.replace('90-day high', "<"+objtag+" class='"+objclass+"' href='/fmr/cbk/'"+('' if sametab else " target='_blank'")+'>90-day high</'+objtag+'>')
    withfamer = not (U == s)
    return U, withfamer

def wrap_symbol_url(s, objtag="span", objclass="", objurl="/fh/$SYMBOL/", sametab=True):
    T = s.split(' ')
    U = []
    hassymbol = False
    for t in T:
        hascomma = False
        if t[-1] == ',':
            t = t[:-1]
            hascomma = True
        #if t.upper() == t and not t.isdigit() and t.isalnum():
        if t.upper() == t and not t.isdigit() and t.replace(".","").isalpha():
            t = "<" + objtag + " class='" + objclass + "' href='" + objurl.replace("$SYMBOL",t) + "'" + ('' if sametab else " target='_blank'") + '>' + t + '</' + objtag + '>'
            hassymbol = True
        t = t+',' if hascomma else t
        U.append(t)
    U = " ".join(U)
    return U, hassymbol
