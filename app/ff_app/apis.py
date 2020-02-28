
from django.http import JsonResponse, HttpResponse
#from django.shortcuts import redirect
from dateutil.relativedelta import relativedelta
from copy import deepcopy

import requests
import re
import random
import datetime, pytz
import math, json

from ratelimit.decorators import ratelimittrylogin
from ff_app.api_cache import cache_api_internal
from ff_app.helper_allstocks import cache_charts

utc = pytz.timezone('UTC')
eastern = pytz.timezone('US/Eastern')

from ff_app.views import get_rank, get_overall_list
from ff_app.views_my import get_watched_symbols, get_recent_symbols
from ff_app.defs import STYPE_LIST, BLOCKED_STOCKS
from ff_app.utils import runsql, table_exist, get_SP500, get_nonSP500, assure_sec, human_format, R, wrap_symbol_url, wrap_famer_url, wrap_sector_url
from ff_user.decorators import getUser



#########
# Start IEX real time cache
#########
IEX_REFRESH_TRADING = 60 # 1 minute refresh inside trading hours
IEX_REFRESH_CLOSE = 3600 # 1 hour refresh outside of trading hours

IEX_cache = {}

def cache_IEX(ss):
    if not ss:
        return False
    ss = ss.upper().replace('-','.')
    enow = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)
    etime = enow.hour + enow.minute/60
    refetch = True
    if ss in IEX_cache:
        if 'lastUpdate' in IEX_cache[ss]:
            d = enow - IEX_cache[ss]['lastUpdate']
            if enow.weekday() < 5 and etime > 9.75 and etime < 17:
                if d.days < 1 and d.seconds < IEX_REFRESH_TRADING:
                    refetch = False
            else:
                if d.days*86400 + d.seconds < IEX_REFRESH_CLOSE:
                    refetch = False
    if refetch:
        r = requests.get("https://api.iextrading.com/1.0/stock/"+ss+"/quote")
        if r.status_code != 200:
            return False
        r = r.json()
        if 'calculationPrice' in r and 'latestPrice' in r and 'latestVolume' in r and 'high' in r and 'low' in r and 'previousClose' in r and 'changePercent' in r and 'companyName' in r:
            IEX_cache[ss] = {'lastUpdate': enow, 
                             'companyName': r['companyName'],
                             'calculationPrice': r['calculationPrice'],
                             'latestPrice': r['latestPrice'],
                             'latestVolume': r['latestVolume'],
                             'high': r['high'],
                             'low': r['low'],
                             'previousClose': r['previousClose'],
                             'chg': r['changePercent'],
                            }
        else:
            return False
    return True

def get_cache_IEX(ss):
    if cache_IEX(ss):
        return IEX_cache[ss]
    return {}

def get_IEX_realtime_volume_est(I):
    tt = 1.0
    ve = I['latestVolume'] * 1.0
    if I['calculationPrice'] == 'tops':
        md = I['lastUpdate'].hour + I['lastUpdate'].minute/60 - 9.75
        if md > 0:
            ve = ve * max(1.0, 6.5/md) * 1.1
            tt = min(1.0, md/6.5)
    return ve, tt

def get_realtime_volume_stats(ss, timebend=1/2):
    n = 0
    if ss not in get_SP500():
        r = cache_charts(ss)
        if not r:
            return (None, None, None, None)
        n = runsql("select count(1) cnt from ff_stock_all where symbol='"+ss+"' and close_date>date_sub(now() , interval 3 month)")[0]['cnt']
        rawsql = "select a.volume, b.avg_volume, b.std_volume, c.maxmax_z from \
                  (select volume from ff_stock_all where symbol='"+ss+"' and close_date=(select max(close_date) from ff_stock_all where symbol='"+ss+"')) a, \
                  (select avg(volume) avg_volume, std(volume) std_volume from ff_stock_all where symbol='"+ss+"') b, \
                  (select max(max_z) maxmax_z from ff_stock_vol_w4) c"
    else:
        rawsql = "select volume, avg_volume, std_volume, z_volume, minmin_z, maxmax_z, bin from ff_stock_vol_w8 where symbol = '"+ss+"'"
    vc = runsql(rawsql)
    if len(vc) == 0 :
        return (None, None, None, None)
    if ss not in get_SP500() and n < 5:
        return (IEX_cache[ss]['latestVolume'], 0, 50, IEX_cache[ss]['latestVolume'])
    vc = vc[0]
    #(ve, tt) = get_IEX_realtime_volume_est(ss)
    (ve, tt) = get_IEX_realtime_volume_est(IEX_cache[ss])
    z_mod = (math.pow(tt, timebend) if IEX_cache[ss]['calculationPrice'] == 'tops' else 1)
    z = ( (ve if ve else vc['volume']) - vc['avg_volume'] ) / (vc['std_volume'] + 0.000001) * z_mod
    v = ( IEX_cache[ss]['latestVolume'] if IEX_cache[ss]['latestVolume'] else vc['volume'] )
    rawsql = "select bin from ff_stock_vol_w4 where "+str(z)+">=min_z and "+str(z)+"<max_z"
    vb = runsql(rawsql)
    if len(vb) == 0:
        if z >= vc['maxmax_z']:
            b = 100
        else:
            b = 0
    else:
        b = vb[0]['bin']
    # assign a middle volume bin (b ranges 0-100) for early hours when we are not sure
    iexh = IEX_cache[ss]['lastUpdate'].hour + IEX_cache[ss]['lastUpdate'].minute/60
    if IEX_cache[ss]['calculationPrice'] == 'tops' and iexh < 11:
        b = 50 + int( (b-50) / (12-iexh))
    return (v, z, b, ve)

def get_realtime_volatility_stats(ss):
    if ss not in get_SP500():
        r = cache_charts(ss)
        if not r:
            return (None, None, None, None, None, None, None)
        rawsql = "select a.*, b.*, c.* from \
                  (select high, low, high-low hl from ff_stock_all where symbol='"+ss+"' and close_date=(select max(close_date) md from ff_stock_w40)) a, \
                  (select avg((high-low)/close) avg_hl, std((high-low)/close) std_hl from ff_stock_all where symbol='"+ss+"') b, \
                  (select min(min_z) minmin_z, max(max_z) maxmax_z from ff_stock_var_diff_w7) c"
    else:
        rawsql = "select hl, avg_hl, std_hl, z_hl, minmin_z, maxmax_z, bin from ff_stock_var_diff_w10 where symbol = '"+ss+"'"
    vc = runsql(rawsql)
    if len(vc) == 0 :
        return (None, None, None, None, None, None, None)
    vc = vc[0]
    h = (IEX_cache[ss]['high'] if IEX_cache[ss]['high'] else vc['low'])
    l = (IEX_cache[ss]['low'] if IEX_cache[ss]['low'] else vc['low'])
    v = (IEX_cache[ss]['high'] - IEX_cache[ss]['low']) * 1.0
    if v < 0:
        v = vc['high'] - vc['low']
    pc  = IEX_cache[ss]['previousClose']
    hlr = v * 1.0 / pc
    z = ( hlr - vc['avg_hl'] ) / (vc['std_hl'] + 0.000001)
    rawsql = "select bin from ff_stock_var_diff_w7 where "+str(z)+">=min_z and "+str(z)+"<max_z"
    vb = runsql(rawsql)
    if len(vb) == 0:
        if z >= vc['maxmax_z']:
            b = 100
        else:
            b = 0
    else:
        b = vb[0]['bin']
    return (v, z, b, h, l, pc, hlr)


def get_realtime_change_stats(ss):
    chg = IEX_cache[ss]['chg']
    if chg is None:
        return None, None
    rawsql = "select bin from ff_stock_chg_w4 where "+str(chg)+" > min_chg and "+str(chg)+" <= max_chg"
    c = runsql(rawsql)
    if len(c) == 0:
        if chg >= 9999:
            b = 100
        else:
            b = 0
    else:
        b = c[0]['bin']
    return b, chg


def get_realtime_ceilfloor_stats(ss, base="quoted"):
    if ss not in get_SP500():
        r = cache_charts(ss)
        if not r:
            return (None, None, None, None)
        q = IEX_cache[ss]['latestPrice']
        # rn is to delay the update until next open, to keep the ceil-floor breaking event
        rn = 0
        try:
            mb = runsql("select max(batched) mb from ff_status_scan")[0]['mb']
            mb = eastern.localize(mb)
            enow = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)
            t_diff = enow - mb
            h_diff = (t_diff.days * 86400 + t_diff.seconds) // 3600
            if h_diff > 8:
                rn = 1
        except:
            pass
        rawsql = "select max(if(&HIGH>h and qed>0,d,0)) hh, max(if(&LOW<l and qed>0,d,0)) ll from ( \
                   select any_value(b.close_date) close_date, 7 d, max(high) h, min(low) l, avg(close) m, any_value(if(c.n>0,1,0)) qed from ff_stock_all a, (select close_date from ff_stock_w40 where rn="+str(rn)+") b, (select count(1) n from ff_stock_all where symbol='"+ss+"' and close_date<date_sub(now() , interval 7 day)) c where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 0 AND 6 \
                   union select any_value(b.close_date) close_date, 14 d, max(high) h, min(low) l, avg(close) m, any_value(if(c.n>0,1,0)) qed from ff_stock_all a, (select close_date from ff_stock_w40 where rn="+str(rn)+") b, (select count(1) n from ff_stock_all where symbol='"+ss+"' and close_date<date_sub(now() , interval 14 day)) c where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 0 AND 13 \
                   union select any_value(b.close_date) close_date, 30 d, max(high) h, min(low) l, avg(close) m, any_value(if(c.n>0,1,0)) qed from ff_stock_all a, (select close_date from ff_stock_w40 where rn="+str(rn)+") b, (select count(1) n from ff_stock_all where symbol='"+ss+"' and close_date<date_sub(now() , interval 30 day)) c where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 0 AND 29 \
                   union select any_value(b.close_date) close_date, 60 d, max(high) h, min(low) l, avg(close) m, any_value(if(c.n>0,1,0)) qed from ff_stock_all a, (select close_date from ff_stock_w40 where rn="+str(rn)+") b, (select count(1) n from ff_stock_all where symbol='"+ss+"' and close_date<date_sub(now() , interval 60 day)) c where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 0 AND 59 \
                   union select any_value(b.close_date) close_date, 90 d, max(high) h, min(low) l, avg(close) m, any_value(if(c.n>0,1,0)) qed from ff_stock_all a, (select close_date from ff_stock_w40 where rn="+str(rn)+") b, (select count(1) n from ff_stock_all where symbol='"+ss+"' and close_date<date_sub(now() , interval 90 day)) c where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 0 AND 89 \
                   union select any_value(b.close_date) close_date, 180 d, max(high) h, min(low) l, avg(close) m, any_value(if(c.n>0,1,0)) qed from ff_stock_all a, (select close_date from ff_stock_w40 where rn="+str(rn)+") b, (select count(1) n from ff_stock_all where symbol='"+ss+"' and close_date<date_sub(now() , interval 180 day)) c where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 0 AND 179 \
                   ) a"
        rawsql = rawsql.replace('&HIGH', str(q) if base=="quoted" else str(IEX_cache[ss]['high']))
        rawsql = rawsql.replace('&LOW', str(q) if base=="quoted" else str(IEX_cache[ss]['low']))
    else:
        q = IEX_cache[ss]['latestPrice']
        if base == "quoted":
            rawsql = "select max(if("+str(q)+">h,d,0)) hh, max(if("+str(q)+"<l,d,0)) ll from ff_stock_cf_w0 where symbol='"+ss+"'"
        else:
            rawsql = "select max(if("+str(IEX_cache[ss]['high'])+">h,d,0)) hh, max(if("+str(IEX_cache[ss]['low'])+"<l,d,0)) ll from ff_stock_cf_w0 where symbol='"+ss+"'"
    b = 0
    hl = 'e'
    d = 0
    if q is None:
        return (None, hl, d, q)
    elif IEX_cache[ss]['low'] is None or IEX_cache[ss]['high'] is None:
        return (None, hl, d, q)
    c = runsql(rawsql)
    if len(c) == 0:
        b = 0
    else:
        c = c[0]
        if c['hh'] >= c['ll'] and c['hh'] > 0:
            if base == "quoted":
                rawsql = "select bin from ff_stock_cf_w6 where "+str(c['hh'])+">=min_ch and "+str(c['hh'])+"<max_ch"
            else:
                rawsql = "select bin from ff_stock_cf_w10 where "+str(c['hh'])+">=min_hh and "+str(c['hh'])+"<max_hh"
            e = runsql(rawsql)
            if len(e) > 0:
                b = e[0]['bin']
                hl = 'h'
                d = c['hh']
                if base != "quoted":
                    q = IEX_cache[ss]['high']
        elif c['hh'] < c['ll'] and c['ll'] > 0:
            if base == "quoted":
                rawsql = "select bin from ff_stock_cf_w8 where "+str(c['ll'])+">=min_cl and "+str(c['ll'])+"<max_cl"
            else:
                rawsql = "select bin from ff_stock_cf_w12 where "+str(c['ll'])+">=min_ll and "+str(c['ll'])+"<max_ll"
            e = runsql(rawsql)
            if len(e) > 0:
                b = e[0]['bin']
                hl = 'l'
                d = c['ll']
                if base != "quoted":
                    q = IEX_cache[ss]['low']
    return b, hl, d, q

def get_realtime_ceilfloor_move(hl, d):
    if d == 0:
        move = "between 7-day high and low"
        qmove = "comfy 7d"
    elif hl == 'h':
        move = "above " + str(d) + "-day high"
        qmove = str(d) + "d max"
    elif hl == 'l':
        move = "below " + str(d) + "-day low"
        qmove = str(d) + "d min"
    else:
        move = "uncertain"
        qmove = "uncertain"
    return move, qmove




def get_rarity_descriptor(b, hilo):
    p = round(max(b, 100-b),2)
    if p == 100:
        rarity = 'extreme ' + hilo
    elif p >= 95:
        rarity = 'very ' + hilo
    elif p >= 90:
        rarity = hilo
    elif p >= 80:
        rarity = 'moderate ' + hilo
    else:
        rarity = 'normal'
    return (rarity, p)

def get_rarity_descriptor_single(b, desc):
    p = round(b,2)
    if p == 100:
        rarity = 'extremely ' + desc
    elif p >= 90:
        rarity = 'very ' + desc
    elif p >= 80:
        rarity = desc
    elif p >= 65:
        rarity = 'moderately ' + desc
    elif p >= 55:
        rarity = 'slightly ' + desc
    else:
        rarity = 'normal'
    return (rarity, p)

def get_rarity_quantifier_single(b, q):
    p = round(b,2)
    if p == 100:
        rarity = 'extremely large ' + q
    elif p >= 90:
        rarity = 'very large ' + q
    elif p >= 80:
        rarity = 'large ' + q
    elif p >= 65:
        rarity = 'moderate ' + q
    elif p >= 55:
        rarity = 'small ' + q
    else:
        rarity = 'normal'
    return (rarity, p)

#########
# End IEX real time cache
#########








def check_SP500_and_table(ss, t):
    ss = ss.upper().replace('-','.')
    if not ss in get_SP500():
        return False
    if not table_exist(t):
        return False
    return True



@getUser()
@cache_api_internal(refresh_rate_in_seconds=600)
def famebits_date(request, ss=""):
    if not table_exist("ff_status_scan_w1"):
        return JsonResponse({})
    b = runsql("select batched from ff_status_scan_w1 order by rn limit 1")[0]['batched']
    return JsonResponse({"date": b.strftime('%a, %b %d %Y')})


@getUser()
@cache_api_internal(refresh_rate_in_seconds=600)
def fame66_support(request, ss=""):
    if not table_exist("ff_stock_w42"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    if is_SP500:
        points = runsql("select term as label, dp as value from ff_stock_w42 where symbol='"+ss+"' order by d desc")
    else:
        r = cache_charts(ss)
        if not r:
            return JsonResponse({})
        points = runsql("select b.label, (c.e-close)/close*100 value from ff_stock_all a, (select '6 months' label, min(close_date) md from ff_stock_w40 where close_date>=date_sub((select max(close_date) md from ff_stock_w40) , interval 6 month) \
                          union select '3 months' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 3 month) \
                          union select '1 month' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 1 month) \
                          union select '2 weeks' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 2 week) \
                          union select '1 week' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 1 week) \
                          union select '2 days' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 2 day)) b, \
                          (select close e from ff_stock_all where symbol='"+ss+"' and close_date=(select max(close_date) md from ff_stock_w40)) c \
                          where a.symbol='"+ss+"' and a.close_date=b.md")
    rs = {"key":ss, "values":points}
    return JsonResponse(rs)


@getUser()
@cache_api_internal(refresh_rate_in_seconds=600)
def fame66_w52_support(request, ss=""):
    if not table_exist("ff_stock_w42"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    if is_SP500:
        points = runsql("select term as label, close-df as value from ff_stock_w42 where symbol='"+ss+"' order by d desc")
    else:
        r = cache_charts(ss)
        if not r:
            return JsonResponse({})
        points = runsql("select b.label, a.close value from ff_stock_all a, (select '6 months' label, min(close_date) md from ff_stock_w40 where close_date>=date_sub((select max(close_date) md from ff_stock_w40) , interval 6 month) \
                          union select '3 months' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 3 month) \
                          union select '1 month' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 1 month) \
                          union select '2 weeks' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 2 week) \
                          union select '1 week' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 1 week) \
                          union select '2 days' label, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 2 day)) b where a.symbol='"+ss+"' and a.close_date=b.md")
    labels = [i['label'] for i in points]
    data   = [i['value'] for i in points]
    rs = {"labels":labels, "datasets":[{"data": data}]}
    return JsonResponse(rs)

@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_volume", group="famebits_volume", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_volume(request, ss="", ns=0):
    #if not check_SP500_and_table(ss, "ff_stock_vol_w13"):
    if not table_exist("ff_stock_vol_w13"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    cache_IEX(ss)
    if not ss in IEX_cache:
        return JsonResponse({})
    b = [] # list of sentences
    (v, z, be, ve) = get_realtime_volume_stats(ss)
    if v is None:
        return JsonResponse({})

    hilo = ('high' if z >= 0 else 'low')
    (rarity, p) = get_rarity_descriptor(be, hilo)
    v_type = IEX_cache[ss]['calculationPrice']
    
    # Sentence 0, only key-value's
    if ns == 0:
        return JsonResponse({'volume':v, 'volume_human':human_format(v), 'z':z, 'rarity':rarity, 'status':('live' if v_type=='tops' else 'closed'), 'I':(p-50)*2})
    
    b.append(ss + ' traded ' + human_format(v) + ' shares ' + ('so far' if v_type == 'tops' else 'before close') + ', which is ' + rarity + ' (' + '{0:.1f}'.format(abs(z)) + ' standard deviations ' + ("above" if z>=0 else "below") + ' its own average trading volume' + (' at the moment' if v_type == 'tops' else '')+ ')')
    
    if p >= 80 and len(b)<ns:
        prob = "almost zero" if p==100 else "less than "+str(max(round(100-p),1))+"%" 
        b.append('The chance for ' + '{0:.1f}'.format(z) + u'\u03C3 ' + hilo +' volume to happen on SP500 stocks is '+prob)
    
    hold_time = False
    if table_exist("ff_status_scan_w1") and table_exist("ff_stock_w40"):
        scan_date = runsql("select date(batched) b from ff_status_scan_w1 order by rn limit 1")[0]
        scan_date = scan_date['b']
        crawl_date = runsql("select close_date c from ff_stock_w40 order by rn limit 1")[0]
        crawl_date = crawl_date['c']
        hold_time = scan_date == crawl_date

    # split here
    if len(b)<ns:
        if is_SP500:
            rr = runsql("select * from ff_stock_vol_w13 where symbol = '"+ss+"'")
        else:
            rr = runsql("select a.symbol, sum( a.chgPct/sqrt(b.s_chg/b.n) * (a.volume-b.avg_volume)/b.std_volume) / any_value(b.n) corr from ff_stock_all a, (select avg(volume) avg_volume, std(volume) std_volume, sum(chgPct*chgPct) s_chg, count(1) n from ff_stock_all where symbol='"+ss+"') b where a.symbol='"+ss+"'")
        if rr:
            rr = rr[0]
            if abs(rr['corr']) >= 0.25:
                b.append("Change in price is "+("highly " if abs(rr['corr']) >= 0.5 else "") + 
                         ("positively" if rr['corr']>0 else "negatively")+" correlated with volume (" + 
                         ("#"+str(int(min(rr['rn_pos'],rr['rn_neg'])))+" in SP500 with " if min(rr['rn_pos'],rr['rn_neg'])<=20 and is_SP500 else "") + 
                         "r=" + '{0:.2f}'.format(rr['corr']) + ")" )
            else:
                b.append("Trading volume does not significantly correlate with change in share price")

    time_holder = " and close_date < (select close_date from ff_stock_w40 order by rn limit 1) " if hold_time else ""
    if len(b)<ns:
        z_pos = z >= 0
        if is_SP500:
            rawsql = "select (select count(1) from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and z_volume"+(">" if z_pos else "<")+str(z)+") n_6m, \
                     (select count(1) from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 3 month) and z_volume"+(">" if z_pos else "<")+str(z)+") n_3m,\
                     (select count(1) from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month) and z_volume"+(">" if z_pos else "<")+str(z)+") n_1m,\
                     (select count(1) from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month)) n_1m_days"
        else:
            rawsql = "select (select count(1) from ff_stock_all where symbol='"+ss+"'"+time_holder+" and (volume-avg_volume)/std_volume"+(">" if z_pos else "<")+str(z)+") n_6m, \
                     (select count(1) from ff_stock_all where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 3 month) and (volume-avg_volume)/std_volume"+(">" if z_pos else "<")+str(z)+") n_3m,\
                     (select count(1) from ff_stock_all where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month) and (volume-avg_volume)/std_volume"+(">" if z_pos else "<")+str(z)+") n_1m,\
                     (select count(1) from ff_stock_all where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month)) n_1m_days \
                     from (select avg(volume) avg_volume, std(volume) std_volume from ff_stock_all where symbol='"+ss+"') a"
        rf = runsql(rawsql)[0]
        if rf['n_1m'] > 3:
            b.append("In the past month, " + str(int(round(100*(rf['n_1m_days']-rf['n_1m'])/rf['n_1m_days']))) + "% of the time "+ss+" was traded at similar volumes")
        elif rf['n_1m'] > 0:
            b.append("In the past month, " + ss + " only has " + str(rf['n_1m']) + " day"+("s" if rf['n_1m']>1 else "")+" with "+("higher" if z_pos else "lower")+" volume")
        elif rf['n_3m'] > 0:
            b.append("In the past 3 months, " + ss + " only has " + str(rf['n_3m']) + " day"+("s" if rf['n_1m']>1 else "")+" with "+("higher" if z_pos else "lower")+" volume")
        elif rf['n_6m'] > 0:
            b.append("In the past 6 months, " + ss + " only has " + str(rf['n_6m']) + " day"+("s" if rf['n_1m']>1 else "")+" with "+("higher" if z_pos else "lower")+" volume")
        else:
            b.append("The volumes were all " + ("lower" if z_pos else "higher") + " in the past 6 months")

    if len(b)<ns and is_SP500:
        if rf['n_6m'] == 0:
            rn = runsql("select close_date, volume, z_volume from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and z_volume<>"+str(z)+" order by z_volume "+("desc " if z_pos else "")+"limit 1")[0]
            b.append("The next "+("highest" if z_pos else "lowest")+" volume was "+human_format(rn['volume'])+" shares ({0:.1f}".format(rn['z_volume']) + u'\u03C3 '+") on "+rn['close_date'].strftime("%b %d").replace(" 0"," "))
        elif rf['n_1m'] == 1:
            rn = runsql("select close_date, volume, z_volume from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub(now() , interval 1 month) and z_volume"+(">" if z_pos else "<")+str(z))[0]
            b.append("That was "+rn['close_date'].strftime("%b %d").replace(" 0"," ")+", with "+human_format(rn['volume'])+" shares traded")
        elif rf['n_3m'] == 1:
            rn = runsql("select close_date, volume, z_volume from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub(now() , interval 3 month) and z_volume"+(">" if z_pos else "<")+str(z))[0]
            b.append("That was "+rn['close_date'].strftime("%b %d").replace(" 0"," ")+", with "+human_format(rn['volume'])+" shares traded")
        elif rf['n_6m'] == 1:
            rn = runsql("select close_date, volume, z_volume from ff_stock_vol_w7 where symbol='"+ss+"'"+time_holder+" and close_date>=date_sub(now() , interval 6 month) and z_volume"+(">" if z_pos else "<")+str(z))[0]
            b.append("That was "+rn['close_date'].strftime("%b %d").replace(" 0"," ")+", with "+human_format(rn['volume'])+" shares traded")

    if len(b)<ns:
        rp = runsql("select count(distinct symbol) n_match, (select count(1) from ff_stock_vol_w8) n_all from ff_stock_vol_w7 where close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month) and symbol<>'"+ss+"' and z_volume"+(">" if z_pos else "<")+str(z))[0]
        if rp['n_match'] == 0:
            b.append("None of the SP500 stocks had encountered this rarity in the past month")
        elif rp['n_match'] <= 10:
            b.append("Only "+str(rp['n_match'])+" stocks in SP500 had encountered this rarity in the past month")
        elif rp['n_match']/rp['n_all']<0.5:
            b.append(("Only " if rp['n_match']/rp['n_all']<0.3 else "")+str(int(round(100*rp['n_match']/rp['n_all'])))+"% of SP500 stocks had similar variation in volume during the past month")
        else:
            b.append("It is very common for major stocks to have similar variation in volume")

    return JsonResponse({'bits': b})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_fame66", group="famebits_fame66", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_fame66(request, ss="", ns=0):
    if not table_exist("ff_stock_w42"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    if is_SP500:
        s = runsql("select term, dp, rn from ff_stock_w42 where symbol='"+ss+"' order by d desc")
    else:
        r = cache_charts(ss)
        if not r:
            return JsonResponse({})
        s = runsql("select a.term, a.d, a.dp, ifnull((select max(rn) from ff_stock_w42 b where d=a.d and dp>a.dp),1) rn from ( \
                      select b.label term, b.d, round((c.e-close)/close*100,2) dp from ff_stock_all a, (select '6 months' label, 180 d, min(close_date) md from ff_stock_w40 where close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 6 month) \
                      union select '3 months' label, 90 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 3 month) \
                      union select '1 month' label, 30 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month) \
                      union select '2 weeks' label, 14 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 2 week) \
                      union select '1 week' label, 7 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 1 week) \
                      union select '2 days' label, 2 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 2 day)) b, \
                      (select close e from ff_stock_all where symbol='"+ss+"' and close_date=(select max(close_date) md from ff_stock_w40)) c \
                      where a.symbol='"+ss+"' and a.close_date=b.md) a group by a.term, a.d, a.dp order by d desc")
    b = []
    for t in s:
        b.append({"pr": get_rank(t['rn']), "range": t['term'], "c_diff": t['dp']})
    return JsonResponse({'bits': b})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_fame66sent", group="famebits_fame66sent", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_fame66sent(request, ss="", ns=0):
    if not table_exist("ff_stock_w43"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    
    # Best term in Fame66
    s = []
    if is_SP500:
        f = runsql("select term, d, df, dp, rn from ff_stock_w42 where symbol='"+ss+"' order by rn limit 1")
        if not f:
            return JsonResponse({})
        f = f[0]
    else:
        r = cache_charts(ss)
        if not r:
            return JsonResponse({})
        f = runsql("select a.*, ifnull((select max(rn) from ff_stock_w42 b where d=a.d and dp>a.dp),1) rn from ( \
                      select b.label term, b.d, round((c.e-close)/close*100,2) dp from ff_stock_all a, (select '6 months' label, 180 d, min(close_date) md from ff_stock_w40 where close_date>=date_sub((select max(close_date) md from ff_stock_w40), interval 6 month) \
                      union select '3 months' label, 90 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 3 month) \
                      union select '1 month' label, 30 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 1 month) \
                      union select '2 weeks' label, 14 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 2 week) \
                      union select '1 week' label, 7 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 1 week) \
                      union select '2 days' label, 2 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40), interval 2 day)) b, \
                      (select close e from ff_stock_all where symbol='"+ss+"' and close_date=(select max(close_date) md from ff_stock_w40)) c \
                      where a.symbol='"+ss+"' and a.close_date=b.md) a order by rn limit 1")
        if len(f):
            f = f[0]
        else:
            return JsonResponse({})
        
    if ns == 0:
        return JsonResponse({'term': f['term'], 'dp': ("" if f['dp']<0 else "+")+str(f['dp'])+"%", 'rn': f['rn']})
    
    # sentence 1
    if len(s) < ns:
        gl = "lost" if f['dp']<0 else "gained"
        s.append(ss + " " + gl + " " + str(abs(f['dp'])) + '% in the past ' + f['term'])
    # sentence 2
    if len(s) < ns:
        if is_SP500:
            d = runsql("select sum(if(d<30,rn,0)-if(d<30,0,rn)) drn from ff_stock_w42 where symbol='"+ss+"'")[0]['drn']
        else:
            h = runsql("select sum(pn*rn) drn, sum(greatest(15-(rn/20),0))+10 sscore from ( \
                        select a.*, ifnull((select max(rn) from ff_stock_w42 b where d=a.d and dp>a.dp),1) rn from ( \
                        select b.pn, b.d, (c.e-close)/close*100 dp from ff_stock_all a, (select -1 pn, 180 d, min(close_date) md from ff_stock_w40 where close_date>=date_sub((select max(close_date) md from ff_stock_w40) , interval 6 month) \
                        union select -1 pn, 90 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 3 month) \
                        union select -1 pn, 30 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 1 month) \
                        union select 1 pn, 14 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 2 week) \
                        union select 1 pn, 7 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 1 week) \
                        union select 1 pn, 2 d, max(close_date) md from ff_stock_w40 where close_date<=date_sub((select max(close_date) md from ff_stock_w40) , interval 2 day)) b, \
                        (select close e from ff_stock_all where symbol='"+ss+"' and close_date=(select max(close_date) md from ff_stock_w40)) c \
                        where a.symbol='"+ss+"' and a.close_date=b.md) a) a")[0]
            d = h['drn']
            g = h['sscore']
        if abs(d) < 150:
            s.append("There is no significant difference in holding " + ss + " long term or short term")
        else:
            s.append("History says that " + ss + " did " + ("significantly" if abs(d)>400 else "slightly") + " better when holding it " + ("shorter" if d<0 else "longer"))
    # sentence 3
    if len(s) < ns:
        if is_SP500:
            g = runsql("select * from ff_stock_w43 where symbol='" + ss + "'")[0]
            g = g['rn']
        else:
            g = runsql("select count(1) cnt from ff_stock_w43 where summary_score>" + str(g))[0]
            g = g['cnt']
        if g < 11:
            perf = "extremely well"
        elif g < 51:
            perf = "very well"
        elif g < 201:
            perf = "well"
        elif g < 401:
            perf = "mediocre"
        else:
            perf = "poorly"
        s.append("Overall, " + ss + " performed " + perf + " over all 6 windows we watched" + (" and ranked #" + str(int(g)) + ' among the SP500 stocks' if is_SP500 else "" ))
        if not is_SP500:
            s.append("That was " + ("comparable to the #"+str(int(g))+" in SP500 stocks" if g else "better than ALL SP500 stocks"))
    # sentence 4
    if len(s) < ns and is_SP500:
        c = runsql("select * from ff_scan_symbols where symbol = '" + ss + "'")[0]
        t = runsql("select a.* from ff_stock_w42 a, (select * from ff_stock_w42 where symbol='"+ss+"' order by rn limit 1) b where a.symbol in (select symbol from ff_scan_symbols where sector = (select sector from ff_scan_symbols where symbol='"+ss+"')) and a.rn<b.rn and a.d=b.d order by a.rn")
        if len(t) == 0:
            s.append("That was the best performance for a "+c['sector']+" stock in the past " + f['term'])
        else:
            s.append("Ranked #"+str(len(t)+1)+" in the "+c['sector']+" sector during the past " + f['term'])
            # sentence 5
            if len(s) < ns:
                gl = "lost" if t[0]['dp']<0 else "gained"
                s.append("The best " + c['sector'] + " stock in such period was " + t[0]['symbol'] + ", which " + gl + " " + str(t[0]['dp']) + "%")

    return JsonResponse({'bits': s})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_bestlist", group="famebits_bestlist", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_bestlist(request, ss="", ns=0):
    # Cannot be extended to non-SP500
    if not check_SP500_and_table(ss, "ff_stock_best"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    cdt = utc.localize(datetime.datetime.now()).astimezone(eastern) - datetime.timedelta(days=1)
    
    symbol_best = runsql("select * from ff_stock_best where symbol='"+ss+"' order by rn, d desc")
    best_terms = []
    for s in symbol_best:
        if s['rg'][:2] in [b['rg'][:2] for b in best_terms]:
            continue
        d = {'rg': s['rg'], 'c_diff': int(100*s['c_diff']), 'pr': get_rank(s['rn'])}
        
        i = re.split('(\D+)',s['rg'])
        d['range'] = i[0] + " " + ("month" if i[1]=='m' else "year") + ("s" if int(i[0])>1 else "")
        sy = s['start'].year == s['end'].year
        if i[3] == 'm':
            #d['period'] = "Between " + s['start'].strftime("%B"+("" if sy else " %Y")) + " and " + s['end'].strftime("%B %Y")
            d['period'] = s['start'].strftime("%b"+("" if sy else " %Y")) + " - " + s['end'].strftime("%b %Y")
            d['url_period'] = '/hsm/?ds='+s['start'].strftime("%m/%Y").replace("/","%2F")+"&de="+s['end'].strftime("%m/%Y").replace("/","%2F")+"&ss="+ss
            d['url_range'] = '/hsm/?ds='+(cdt-relativedelta(years=int(i[0]))).strftime("%m/%Y").replace("/","%2F")+"&de="+cdt.strftime("%m/%Y").replace("/","%2F")+"&ss="+ss
        else:
            #d['period'] = "Between " + ("{d.month}/{d.day}"+("" if sy else "/{d.year}")).format(d=s['start']) + " and " + "{d.month}/{d.day}/{d.year}".format(d=s['end'])
            d['period'] = "{d.month}/{d.day}/{d.year}".format(d=s['start']) + " - " + "{d.month}/{d.day}/{d.year}".format(d=s['end'])
            d['url_period'] = '/hsd/?ds='+s['start'].strftime("%m/%d/%Y").replace("/","%2F")+"&de="+s['end'].strftime("%m/%d/%Y").replace("/","%2F")+"&ss="+ss
            d['url_range'] = '/hsm/?ds='+(cdt-relativedelta(months=int(i[0]))).strftime("%m/%Y").replace("/","%2F")+"&de="+cdt.strftime("%m/%Y").replace("/","%2F")+"&ss="+ss
        best_terms.append(d)
    return JsonResponse({'bits': best_terms})

@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_bestsent", group="famebits_bestsent", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_bestsent(request, ss="", ns=0):
    # Cannot be extended to non-SP500
    if not check_SP500_and_table(ss, "ff_stock_best"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    
    b = runsql("select a.*, pow(10,log10(1+c_diff)/d)-1 d_diff from ff_stock_best a where symbol='"+ss+"' order by rn, c_diff desc limit 1")[0]
    i = re.split('(\D+)', b['rg'])
    sy = b['start'].year == b['end'].year
    if i[3] == 'm':
        duration = str(b['d']) + " month" + ("s" if b['d']>1 else "")
        period   = b['start'].strftime("%B"+("" if sy else " %Y")) + " and " + b['end'].strftime("%B %Y")
        d_unit   = "monthly"
    else:
        duration = str(b['d']) + " day" + ("s" if b['d']>1 else "")
        period   = "{d.month}/{d.day}/{d.year}".format(d=b['start']) + " and " + "{d.month}/{d.day}/{d.year}".format(d=b['end'])
        d_unit   = "daily"
    gain = str(int(100*b['c_diff'])) + "%"
    dret = str(round(100*b['d_diff'],2)) + "%"

    # sentence 0
    if ns == 0:
        return JsonResponse({'duration': duration, 'gain': ("" if b['c_diff']<0 else "+") + gain})
    
    c = runsql("select * from ff_scan_symbols where symbol = '" + ss + "'")[0]
    s = []
    # sentence 1
    if len(s) < ns:
        s.append(ss + ' gained ' + gain + ' between ' + period)
    # sentence 2
    if len(s) < ns:
        s.append('With an average ' + d_unit + ' return of  ' + dret + ' during ' + duration)
    # sentence 3
    if len(s) < ns:
        rsp500 = int(b['rn']) + 1
        s.append('Ranked #' + str(rsp500) + ' among SP500 stocks over the same period')
    # sentence 4
    if len(s) < ns:
        term = i[2] + " " + ("day" if i[1]=='m' else "month") + ("s" if int(i[2])>1 else "")
        term += " or longer in the past " + i[0] + " " + ("month" if i[1]=='m' else "year") + ("s" if int(i[0])>1 else "")
        t = runsql("select a.* from ff_stock_best a, (select rg, rn from ff_stock_best where symbol='"+ss+"' order by rn, c_diff desc limit 1) b where a.symbol in (select symbol from ff_scan_symbols where sector = (select sector from ff_scan_symbols where symbol='"+ss+"')) and a.rn<b.rn and a.rg=b.rg order by rn, c_diff desc")
        if len(t) == 0:
            s.append("That was the best performance in the "+c['sector']+" sector for holding "+term)
        else:
            s.append("Ranked #"+str(len(t)+1)+" in the "+c['sector']+" sector for holding "+term)
    # sentence 5
    if len(s) < ns and len(t) > 0:
        if i[3] == 'm':
            period   = t[0]['start'].strftime("%B"+("" if sy else " %Y")) + " and " + t[0]['end'].strftime("%B %Y")
        else:
            period   = "{d.month}/{d.day}/{d.year}".format(d=t[0]['start']) + " and " + "{d.month}/{d.day}/{d.year}".format(d=t[0]['end'])
        gain = str(int(100*t[0]['c_diff'])) + "%"
        s.append("The best in the same sector under the same term was "+t[0]['symbol']+", which gained "+gain+" between "+period)
    # sentence 6
    if len(s) < ns:
        d = runsql("select a.*, pow(10,log10(1+c_diff)/d)-1 d_diff from ff_stock_best a, (select rg from ff_stock_best where symbol='"+ss+"' order by rn, c_diff desc limit 1) b where a.rg=b.rg order by log10(1+c_diff)/d desc")[0]
        if d['symbol'] == ss:
            s.append("The " + d_unit + " return was also the best in the SP500 stocks for holding "+term)
        else:
            sy = d['start'].year == d['end'].year
            if i[3] == 'm':
                period   = d['start'].strftime("%B"+("" if sy else " %Y")) + " and " + d['end'].strftime("%B %Y")
            else:
                period   = "{d.month}/{d.day}/{d.year}".format(d=d['start']) + " and " + "{d.month}/{d.day}/{d.year}".format(d=d['end'])
            s.append("Holding " + term + ", a better option was to own " + d['symbol'] + " between " + period)
            # sentence 7
            if len(s) < ns:
                dret = str(round(100*d['d_diff'],2)) + "%"
                s.append("Which gave the average " + d_unit + " return of " + dret)
    return JsonResponse({'bits': s})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_pricefluc", group="famebits_pricefluc", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_pricefluc(request, ss="", ns=0, FLUX_SURPRESS=3):
    if not table_exist("ff_stock_vol_w13"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    cache_IEX(ss)
    if not ss in IEX_cache:
        return JsonResponse({})
    s = [] # list of sentences
    (v, z, b, h, l, pc, hlr) = get_realtime_volatility_stats(ss)
    if v is None:
        return JsonResponse({})

    (rarity, p) = get_rarity_descriptor_single(b, "large")
    v_type = IEX_cache[ss]['calculationPrice']
    I = max(p-FLUX_SURPRESS, 0)
    
    # Sentence 0, only key-value's
    if ns == 0:
        return JsonResponse({'high': h, 'low': l, 'previousClose': pc, 'daily_volatility':round(v,2), 'hl_ratio':round(hlr*100,2), 'z':z, 'rarity':rarity, 'status':('live' if v_type=='tops' else 'closed'), 'I':I})
    
    # Sentence 1-1
    if ns > 1:
        if is_SP500:
            rs = runsql("select * from ff_stock_var_diff_w3 where symbol='"+ss+"'")[0]
        else:
            rs = runsql("select any_value(a.mat7_ratio) mat7_ratio, sum(if(a.mat7_ratio>b.mat7_ratio,1,0)) rnsl, sum(if(a.mat7_ratio<b.mat7_ratio,1,0)) rnls from \
                         (select mat7std/(b.mat7std_avg+0.000001) mat7_ratio from (select mat7std from ( \
                          select a.close_date, avg(b.close) mat7, std(b.close) mat7std from ff_stock_all a, ff_stock_all b where a.symbol='"+ss+"' and b.symbol='"+ss+"' and DATEDIFF(a.close_date, b.close_date) BETWEEN 0 AND 6 group by close_date \
                          ) a where close_date=(select max(close_date) md from ff_stock_w40)) a, \
                         (select avg(mat7std) mat7std_avg from ( \
                          select a.close_date, avg(b.close) mat7, std(b.close) mat7std from ff_stock_all a, ff_stock_all b where a.symbol='"+ss+"' and b.symbol='"+ss+"' and DATEDIFF(a.close_date, b.close_date) BETWEEN 0 AND 6 group by close_date \
                          ) a) b) a, ff_stock_var_diff_w1 b")[0]
        if min(rs['rnsl'], rs['rnls']) < 50:
            dec = "significantly "
        elif min(rs['rnsl'], rs['rnls']) > 100 and min(rs['rnsl'], rs['rnls']) < 200:
            dec = "slightly "
        else:
            dec = ""
        if rs['rnsl']<200:
            state = " became " + dec + "stabilized"
        elif rs['rnls']<200:
            state = " became " + dec + "volatile"
        else:
            state = " stayed around the same volatility"
        s.append("The stock price of " + ss + state + " recently")

    # Sentence 1-2
    if ns > 3:
        if is_SP500:
            rs = runsql("select * from ff_stock_var_diff_w12 where symbol='"+ss+"'")[0]
        else:
            rs = runsql("select avg(z_mat7) z_mat7_avg, std(z_mat7) z_mat7_std from ( \
                         select a.*, (close-mat7)/(mat7std+0.000001) z_mat7 from ( \
                         select a.close_date, any_value(a.close) close, avg(b.close) mat7, std(b.close) mat7std from ff_stock_all a, ff_stock_all b where a.symbol='"+ss+"' and b.symbol='"+ss+"' and DATEDIFF(a.close_date, b.close_date) BETWEEN 0 AND 6 group by close_date \
                         ) a where close_date<>(select min(close_date) from ff_stock_var_d7) ) a")[0]
        state = ""
        if rs['z_mat7_std']>1.12:
            state = "fluctuating and "
            if rs['z_mat7_std']>1.18:
                state = "significantly " + state
            elif rs['z_mat7_std']<1.15:
                state = "somehow " + state
        elif rs['z_mat7_std']<1.10:
            state = "consistently "
        if rs['z_mat7_avg']<0.05:
            state = (state + "going down" if state else "going down in general")
        elif rs['z_mat7_avg']>0.05:
            state = (state + "going up" if state else "going up in general")
        else:
            state += "sticking around"
        s.append("Over the past 6 months, "+ss+" has been "+state)

    # Sentence 2-1
    s.append(('So far ' if v_type == 'tops' else 'During last trading day, ') + ss + ' traded between $' + str(l) + ' and $' + str(h) + ' - this range corresponds to {0:.2f}% of the previous closing price'.format(hlr*100))
    
    # Sentence 2-2
    if len(s) < ns:
        s.append('The daily high-low range ' + ('is ' if v_type == 'tops' else 'was ') + rarity + ', being {0:.1f} standard deviations ('.format(abs(z))+ u'\u03C3' +') ' + ('below' if z<0 else 'above') + ' average')

    # Sentence 2-3
    if len(s) < ns and p > 80:
        s.append('The chance for any SP500 stock to have such ' + '{0:.1f}'.format(z) + u'\u03C3 rare daily high-low range is '+(str(100-p)+'%' if p>99 else "almost zero"))
    
    # Sentence 2-4
    if len(s) < ns:
        if is_SP500:
            rawsql = "select (select count(1) from ff_stock_var_diff_w9 where symbol='"+ss+"' and z_hl>"+str(z)+") n_6m, \
                         (select count(1) from ff_stock_var_diff_w9 where symbol='"+ss+"' and close_date>=date_sub(now() , interval 3 month) and z_hl>"+str(z)+") n_3m,\
                         (select count(1) from ff_stock_var_diff_w9 where symbol='"+ss+"' and close_date>=date_sub(now() , interval 1 month) and z_hl>"+str(z)+") n_1m,\
                         (select count(1) from ff_stock_var_diff_w9 where symbol='"+ss+"' and close_date>=date_sub(now() , interval 1 month)) n_1m_days"
        else:
            rawsql = "select sum(if(z_hl>"+str(z)+",1,0)) n_6m, \
                       sum(if(close_date>=date_sub(now() , interval 3 month) and z_hl>"+str(z)+",1,0)) n_3m, \
                       sum(if(close_date>=date_sub(now() , interval 1 month) and z_hl>"+str(z)+",1,0)) n_1m, \
                       sum(if(close_date>=date_sub(now() , interval 1 month),1,0)) n_1m_days \
                      from (select close_date, (high-low)/close hlr, ((high-low)/close-avg_hlr)/(std_hlr+0.000001) z_hl from ff_stock_all a, (select avg((high-low)/close) avg_hlr, std((high-low)/close) std_hlr from ff_stock_all where symbol='"+ss+"') b where symbol='"+ss+"') a"
        rf = runsql(rawsql)[0]
        if rf['n_1m'] > 3:
            s.append("In the past month, " + str(int(round(100*(rf['n_1m_days']-rf['n_1m'])/rf['n_1m_days']))) + "% of the time "+ss+" was traded at similar daily high-low range")
        elif rf['n_1m'] > 0:
            s.append("In the past month, " + ss + " only has " + str(rf['n_1m']) + " day"+("s" if rf['n_1m']>1 else "")+" with larger daily high-low range")
        elif rf['n_3m'] > 0:
            s.append("In the past 3 months, " + ss + " only has " + str(rf['n_3m']) + " day"+("s" if rf['n_1m']>1 else "")+" with larger daily high-low range")
        elif rf['n_6m'] > 0:
            s.append("In the past 6 months, " + ss + " only has " + str(rf['n_6m']) + " day"+("s" if rf['n_1m']>1 else "")+" with larger daily high-low range")
        else:
            s.append("This is the largest daily high-low range for " + ss + " in the past 6 months")

    # Sentence 2-5
    if len(s) < ns:
        if rf['n_6m'] > 0:
            if is_SP500:
                rl = runsql("select * from ff_stock_var_diff_w9 where symbol='" + ss + "' order by z_hl desc limit 1")[0]
            else:
                rl = runsql("select close_date, (high-low)/close hlr from ff_stock_all where symbol='"+ss+"' order by hlr desc limit 1")[0]
            s.append("In the past 6 months, the largest daily high-low difference for " + ss + " was " + str(round(rl['hlr']*100,2)) + "% on {d.month}/{d.day}/{d.year}".format(d=rl['close_date']))

    # Sentence 2-6
    if len(s) < ns:
        rp = runsql("select count(distinct symbol) n_match, (select count(1) from ff_stock_var_diff_w10) n_all from ff_stock_var_diff_w9 where close_date>=date_sub(now() , interval 1 month) and symbol<>'"+ss+"' and z_hl>"+str(z))[0]
        if rp['n_match'] == 0:
            s.append("None of the SP500 stocks had encountered this large daily high-low range in the past month")
        elif rp['n_match'] <= 10:
            s.append("Only "+str(rp['n_match'])+" stocks in SP500 had encountered larger daily high-low range in the past month")
        elif rp['n_match'] / rp['n_all'] < 0.5:
            s.append(("Only " if rp['n_match']/rp['n_all']<0.3 else "")+str(int(round(100*rp['n_match']/rp['n_all'])))+"% of SP500 stocks had similar variation in daily high-low range during the past month")

    return JsonResponse({'bits': [i for i in s if i]})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_changerate", group="famebits_changerate", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_changerate(request, ss="", ns=0):
    if not table_exist("ff_stock_chg_w13"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    cache_IEX(ss)
    if not ss in IEX_cache:
        return JsonResponse({})
    s = [] # list of sentences
    (b, chg) = get_realtime_change_stats(ss)
    if chg is None:
        return JsonResponse({})

    (rarity, p) = get_rarity_descriptor(b, "large")
    p_ = (p-50)*2
    v_type = IEX_cache[ss]['calculationPrice']
    if chg < 0:
        if rarity == "normal":
            move = 'moves down' if v_type=='tops' else 'moved down'
        elif p_ < 85:
            move = 'drops' if v_type=='tops' else 'dropped'
        elif p_ < 90:
            move = 'stumbles' if v_type=='tops' else 'stumbled'
        elif p_ < 95:
            move = 'dives' if v_type=='tops' else 'dived'
        elif p_ < 99:
            move = 'sinks' if v_type=='tops' else 'sank'
        else:
            move = 'crashes' if v_type=='tops' else 'crashed'
    else:
        if rarity == "normal":
            move = 'moves up' if v_type=='tops' else 'moved up'
        elif p_ < 85:
            move = 'rises' if v_type=='tops' else 'rose'
        elif p_ < 90:
            move = 'jumps' if v_type=='tops' else 'jumped'
        elif p_ < 95:
            move = 'fires up' if v_type=='tops' else 'fired up'
        elif p_ < 99:
            move = 'soars' if v_type=='tops' else 'soared'
        else:
            move = 'rallies' if v_type=='tops' else 'rallied'
    if abs(chg) >= 0.1:
        chg = round(chg, 3)

    if p_ < 90:
        rarity = ""
    js = ("roar" if "extreme" in rarity else ("jump" if "very" in rarity else "gain")) if chg>0 else ("crash" if "extreme" in rarity else ("dive" if "very" in rarity else "drop"))
    # Sentence 0, only key-value's
    if ns == 0:
        return JsonResponse({'chg':chg, 'rarity':rarity, 'move':move, 'js':js, 'status':('live' if v_type=='tops' else 'closed'), 'I':p_})
    
    s.append(('So far ' if v_type == 'tops' else 'During last trading day, ') + 'the price of ' + ss + (' has a ' if v_type == 'tops' else ' had a ') + ('typical' if rarity=='normal' else rarity+' '+js)+' of '+str(round(abs(chg)*100,2))+'%')
    
    if is_SP500:
        rs = runsql("select * from ff_stock_chg_w7 where symbol = '"+ss+"' and d=365 order by minmax desc")
    else:
        r = cache_charts(ss)
        if not r:
            return JsonResponse({})
        rs = runsql("select a.close_date, a.chgPct/100 val from ff_stock_all a, (select close_date from ff_stock_all where symbol='"+ss+"' and chgPct=(select max(chgPct) val from ff_stock_all where symbol='"+ss+"') limit 1) b where a.symbol='"+ss+"' and a.close_date=b.close_date \
                     union select a.close_date, a.chgPct/100 val from ff_stock_all a, (select close_date from ff_stock_all where symbol='"+ss+"' and chgPct=(select min(chgPct) val from ff_stock_all where symbol='"+ss+"') limit 1) b where a.symbol='"+ss+"' and a.close_date=b.close_date")
    if len(rs) > 1:
        su = "biggest single day jump for " + ss + " was " +str(round(rs[0]['val']*100,2))+"% on {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rs[0]['close_date'])
        sd = "biggest single day drop was " +str(round(abs(rs[1]['val'])*100,2))+"% on {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rs[1]['close_date'])
        s1 = "Over the last " + ("year" if is_SP500 else "6 months") + ", the " + (su if chg>0 else sd)
        s2 = "The " + (sd if chg>0 else su)
        if len(s) < ns:
            s.append(s1)
        if len(s) < ns:
            s.append(s2)
    if len(s) < ns:
        if is_SP500:
            rs = runsql("select * from ff_stock_chg_w9 where symbol='"+ss+"' and d_ratio>0.5 order by up_ratio desc")
        else:
            rs = runsql("select 'week' term, 7 d, count(1) n, sum(if(chgPct>0,1,0)) n_up, sum(if(chgPct>0,1,0))/count(1) up_ratio, count(1)/7 d_ratio from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now() , interval 1 week) \
                         union select 'month' term, 30 d, count(1) n, sum(if(chgPct>0,1,0)) n_up, sum(if(chgPct>0,1,0))/count(1) up_ratio, count(1)/30 d_ratio from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now() , interval 1 month) \
                         union select '3 months' term, 90 d, count(1) n, sum(if(chgPct>0,1,0)) n_up, sum(if(chgPct>0,1,0))/count(1) up_ratio, count(1)/90 d_ratio from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now() , interval 3 month) \
                         union select '6 months' term, 30 d, count(1) n, sum(if(chgPct>0,1,0)) n_up, sum(if(chgPct>0,1,0))/count(1) up_ratio, count(1)/180 d_ratio from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now() , interval 6 month)")
        if rs[0]['up_ratio'] >= rs[-1]['up_ratio']:
            s.append(ss + " went up for " + str(round(rs[0]['up_ratio']*100))+"% of the trading days in the past "+str(rs[0]['d'])+" days")
        else:
            s.append(ss + " went down for " + str(round((1-rs[0]['up_ratio'])*100))+"% of the trading days in the past "+str(rs[0]['d'])+" days")
    if len(s) < ns and is_SP500:
        rs = runsql("select * from ff_stock_chg_w14 where symbol='"+ss+"' order by ud desc")
        s.append("The share price for "+ss+" went up on "+str(int(rs[0]['max_run']))+" consecutive trading days starting {:%m/%d/%Y}".format(rs[0]['start_date'])+", for a gain of "+str(round(rs[0]['run_gain']*100,2))+"% (average "+str(round(rs[0]['daily_diff']*100,2))+"% per day)")
    if len(s) < ns and is_SP500:
        s.append("The longest dive run in the past year was the "+str(int(rs[1]['max_run']))+"-day period starting on {:%m/%d/%Y}".format(rs[0]['start_date'])+", for a total drop of "+str(round(abs(rs[1]['run_gain'])*100,2))+"% (average "+str(round(rs[1]['daily_diff']*100,2))+"% per day)")

    return JsonResponse({'bits': [i for i in s if i]})




@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_ceilfloor", group="famebits_ceilfloor", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_ceilfloor(request, ss="", ns=0, SWAP_SUPPRESS=3, QUOTED_SUPPRESS=2):
    if not table_exist("ff_stock_cf_w8"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    cache_IEX(ss)
    if not ss in IEX_cache:
        return JsonResponse({})

    s = [] # list of sentences
    t = "quoted"
    v_type = IEX_cache[ss]['calculationPrice']
    isSwap = False
    
    # check if the quoted stock price goes beyond ceiling or floor
    (b, hl, d, q) = get_realtime_ceilfloor_stats(ss)
    if b is None:
        return JsonResponse({})

    if ns > 0:
        (rarity, _) = get_rarity_descriptor_single(b, "rare")
        (move, _) = get_realtime_ceilfloor_move(hl, d)
        s.append(('The current quoted' if v_type == 'tops' else 'During the last trading day, the closing') + ' price of ' + ss + ' ($'+str(q)+') ' + ('is ' if v_type == 'tops' else 'was ') + move + ', which is '+ rarity)

    # check if the daily high-low price goes beyond ceiling or floor
    (_b, _hl, _d, _q) = get_realtime_ceilfloor_stats(ss, base="broader")
    if ns > 1:
        (_rarity, _) = get_rarity_descriptor_single(_b, "rare")
        (_move, _) = get_realtime_ceilfloor_move(_hl, _d)
        if move != _move:
            s.append(('So far ' if v_type == 'tops' else 'On last trading day, ') + ('the daily-'+('high' if _hl=='h' else 'low')+' ($'+str(_q)+') of ' if _b>0 else '') + ss + ' is '+ _move + ', which is '+ _rarity)
    if b == 0 and _b > 0:
        # swap out the level-0 return dict from quoted to high-low
        t = "daily high" if _hl=="h" else "daily low"
        hl = _hl
        d = _d
        b = _b
        q = _q
        isSwap = True
        
    if ns == 0:
        # final level-0
        b -= QUOTED_SUPPRESS
        if isSwap:
            b -= SWAP_SUPPRESS
        b = round((b/100)**2 * 100,2)
        (rarity, p) = get_rarity_descriptor_single(b, "rare")
        (move, qmove) = get_realtime_ceilfloor_move(hl, d)
        return JsonResponse({'target': t, 'price':q, 'rarity':rarity, 'move':move, 'qmove':qmove, 'status':('live' if v_type=='tops' else 'closed'), 'I':p})
    
    ds = 0
    sa = []
    if is_SP500:
        rs = runsql("select * from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 1 month) and hh = (select max(hh) max_hh from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 1 month)) order by close_date desc")
    else:
        rawsql = "select a.* from (select a.close_date, max(if(high>h,d,0)) hh, max(if(low<l,d,0)) ll from (\
                   select b.close_date, any_value(7) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 7 group by b.close_date \
                   union select b.close_date, any_value(14) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 14 group by b.close_date \
                   union select b.close_date, any_value(30) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 30 group by b.close_date \
                   union select b.close_date, any_value(60) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 60 group by b.close_date \
                   union select b.close_date, any_value(90) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 90 group by b.close_date \
                   union select b.close_date, any_value(180) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 180 group by b.close_date \
                  ) a group by a.close_date ) a where &COND order by close_date desc"
                   
        rhlsql = "select max(if(high>h,d,0)) hh, max(if(low<l,d,0)) ll from ( \
                   select b.close_date, any_value(7) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 7 group by b.close_date \
                   union select b.close_date, any_value(14) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 14 group by b.close_date \
                   union select b.close_date, any_value(30) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 30 group by b.close_date \
                   union select b.close_date, any_value(60) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 60 group by b.close_date \
                   union select b.close_date, any_value(90) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 90 group by b.close_date \
                   union select b.close_date, any_value(180) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval &INT)) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 180 group by b.close_date \
                  ) a"
        rhl = runsql(rhlsql.replace('&INT', '1 month'))[0]
        if not rhl['hh'] or not rhl['ll']:
            return JsonResponse({})
        rs = runsql(rawsql.replace('&COND','hh = '+str(rhl['hh'])).replace('&INT', '1 month'))
    if len(rs) > 0:
        ds = rs[0]['hh']
        ls = len(rs)
        is_30 = False
        if ds == d: # today's ceiling breaking is also the 30-day high
            ls += 1
            is_30 = True
        if ds > 0:
            sa.append("Over the last month, " + ss + " has gone above the " + str(ds) + "-day high on " + str(ls) + " day" + ("s" if ls>1 else "") )
            if len(rs) > 1:
                if not is_30:
                    sa.append("The last time it went above the " + str(ds) + "-day high was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rs[0]['close_date']) )
            else:
                if is_30:
                    sa.append("The other time was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rs[0]['close_date']) )
                else:
                    sa.append("That was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rs[0]['close_date']) )
    dt = 0
    sb = []
    if is_SP500:
        rt = runsql("select * from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 1 month) and ll = (select max(ll) max_ll from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 1 month)) order by close_date desc")
    else:
        rt = runsql(rawsql.replace('&COND','ll = '+str(rhl['ll'])).replace('&INT', '1 month'))
    if len(rt) > 0:
        dt = rt[0]['ll']
        lt = len(rt)
        is_30 = False
        if dt == d: # today's ceiling breaking is also the 30-day high
            lt += 1
            is_30 = True
        if dt > 0:
            sb.append("The price of " + ss + " has gone below the " + str(dt) + "-day low on " + str(lt) + " day" + ("s" if lt>1 else "") + " over the last last month")
            if len(rt) > 1:
                if not is_30:
                    sb.append("The last time it went below the " + str(dt) + "-day low was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rt[0]['close_date']) )
            else:
                if is_30:
                    sb.append("The other time was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rt[0]['close_date']) )
                else:
                    sb.append("That was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=rt[0]['close_date']) )

    s = (s + sa + sb if hl=='h' else s + sb + sa)
    if ns < len(s):
        s = s[:ns]
    
    if ns > len(s) and len(rs) == 0 and len(rt) == 0:
        s.append(ss + " were all traded within the 7-day high and 7-day low during the last 30 days")

    if ns > len(s):
        if is_SP500:
            r = runsql("select * from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 6 month) and hh = (select max(hh) max_hh from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 6 month)) order by close_date desc")
        else:
            rhl = runsql(rhlsql.replace('&INT', '6 month'))[0]
            r = runsql(rawsql.replace('&COND','hh = '+str(rhl['hh'])).replace('&INT', '6 month'))
        if len(r) > 0:
            d = r[0]['hh']
            s.append("The biggest ceiling penetration in the past 6 months was on the " + str(d) + "-day high" + (", " + ("which occurred " + str(len(r)) + " times with the latest " if len(r)>1 else "") + "on {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=r[0]['close_date']) if d>ds else "") )

    if ns > len(s) and is_SP500:
        r = runsql("select hh, max(close_date) latest, count(1) cnt from ff_stock_cf_w4 where symbol='"+ss+"' and hh>0 and close_date>=date_sub(now(), interval 6 month) group by hh order by hh desc limit 3")
        if len(r) > 0:
            s1 = ["over the "+str(i['hh'])+"-day high "+str(i['cnt'])+" time"+("s" if i['cnt']>1 else "") for i in r]
            if len(r) > 1:
                s1[-1] = "and " + s1[-1]
            s1 = ", ".join(s1)
            s.append("During the past 6 months, " + ss + " went " + s1 )
        
    if ns > len(s):
        if is_SP500:
            r = runsql("select * from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 6 month) and ll = (select max(ll) max_ll from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval 6 month)) order by close_date desc")
        else:
            r = runsql(rawsql.replace('&COND','ll = '+str(rhl['ll'])).replace('&INT', '6 month'))
        if len(r) > 0:
            d = r[0]['ll']
            s.append("The largest floor breaking was on the " + str(d) + "-day low" + (", " + ("which occurred " + str(len(r)) + " times with the latest " if len(r)>1 else "") + "on {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=r[0]['close_date']) if d>dt else "") )

    if ns > len(s):
        r = runsql("select ll, max(close_date) latest, count(1) cnt from ff_stock_cf_w4 where symbol='"+ss+"' and ll>0 and close_date>=date_sub(now(), interval 6 month) group by ll order by ll desc limit 3")
        if len(r) > 0:
            s1 = ["below the "+str(i['ll'])+"-day low "+str(i['cnt'])+" time"+("s" if i['cnt']>1 else "") for i in r]
            if len(r) > 1:
                s1[-1] = "and " + s1[-1]
            s1 = ", ".join(s1)
            s.append("During the past 6 months, " + ss + " went " + s1 )
        
    return JsonResponse({'bits': [i for i in s if i]})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_dailymoveevents", group="famebits_dailymoveevents", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=3600)
def famebits_dailymoveevents(request, ss="", ns=1, target="b", mat=90, close_interval="90 day"):
    #if not check_SP500_and_table(ss, "ff_stock_cf_w4"):
    #    return JsonResponse({})
    if not table_exist("ff_stock_w43"):
        return JsonResponse({})
    if target not in ['b','bc','mu','md','mua','mda']:
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()

    if is_SP500:
        #s = runsql("select * from (select a.*, if(@p and @p>0,if(close<>@p,(close-@p)/@p,0),null) chr, @p:=a.close p from (select * from ff_stock_cf_w4 where symbol='"+ss+"' order by close_date) a, (select @p:=null) b) a order by close_date desc")
        s = runsql("select * from (select a.*, if(@p and @p>0,if(close<>@p,(close-@p)/@p,0),null) chr, @p:=a.close p from (select * from ff_stock_cf_w4 where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+") order by close_date) a, (select @p:=null) b) a order by close_date desc")
    else:
        r = cache_charts(ss)
        if not r:
            return JsonResponse({})
        s1 = ''
        for x in ['h','l','m']:
            for w in [7, 14, 30, 60, 90, 180]:
                s1 += ", sum(if(d="+str(w)+","+x+",0)) " + x + str(w)
        rawsql = "select * from (select a.*, if(@p and @p>0,if(close<>@p,(close-@p)/@p,0),null) chr, @p:=a.close p from ( \
                  select a.close_date, any_value(a.close) close, max(if(high>h,d,0)) hh, max(if(close>h,d,0)) ch, min(if(close>m,d,999)) cc, min(if(close<m,d,999)) ccl, max(if(low<l,d,0)) ll, max(if(close<l,d,0)) cl \
                  "+s1+" from ( \
                  select b.close_date, any_value(7) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l, avg(a.close) m from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+")) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 7 group by b.close_date \
                  union select b.close_date, any_value(14) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l, avg(a.close) m from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+")) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 14 group by b.close_date \
                  union select b.close_date, any_value(30) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l, avg(a.close) m from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+")) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 30 group by b.close_date \
                  union select b.close_date, any_value(60) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l, avg(a.close) m from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+")) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 60 group by b.close_date \
                  union select b.close_date, any_value(90) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l, avg(a.close) m from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+")) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 90 group by b.close_date \
                  union select b.close_date, any_value(180) d, any_value(b.close) close, any_value(b.high) high, any_value(b.low) low, max(a.high) h, min(a.low) l, avg(a.close) m from ff_stock_all a, (select close, high, low, close_date from ff_stock_all where symbol='"+ss+"' and close_date>=date_sub(now(), interval "+close_interval+")) b where a.symbol='"+ss+"' and datediff(b.close_date,a.close_date) BETWEEN 1 AND 180 group by b.close_date \
                  ) a group by close_date ) a, (select @p:=null) b) a order by close_date desc"
        s = runsql(rawsql)
    s = s[:-1]
    m_list = [int(k[1:]) for k in s[0].keys() if k[0]=='m']
    m_list.sort()

    b = []
    for t in s:
        #e = {"close_date": t['close_date'], "open": round(t['open'],2), "high": round(t['high'],2), "low": round(t['low'],2), "close": round(t['close'],2)}
        e = {"close_date": t['close_date'], "close": round(t['close'],2)}
        try:
            e['chp'] = round(t['chr']*100,2)
        except:
            e['chp'] = None
        c = []
        
        # keys
        # targets: 'b':both ceiling and floor on both close or extrema
        #          'bc':both ceiling and floor on close only
        #          'm':moving average (using variable mat as the window length)
        
        # closing price breaking
        if len(c) < ns:
            if t['ch'] > 0 and target in ['b','bc']:
                c.append({'color': 'success', 'content': 'Closed above '+str(t['ch'])+'-day high'})
            elif t['cl'] > 0 and target in ['b','bc']:
                c.append({'color': 'danger', 'content': 'Closed below '+str(t['cl'])+'-day low'})

        # daily extrema breaking
        if len(c) < ns:
            if t['hh'] > 0 and t['hh'] > t['ch'] and t['hh'] >= t['ll'] and target in ['b']:
                c.append({'color': 'success', 'content': 'Daily high above '+str(t['hh'])+'-day high'})
            elif t['ll'] > 0 and t['ll'] > t['cl'] and t['ll'] > t['hh'] and target in ['b']:
                c.append({'color': 'danger', 'content': 'Daily low below '+str(t['ll'])+'-day low'})

        # moving average breaking
        if len(c) < ns and target in ['mu','md'] and mat in m_list:
            if t['close'] > t['m'+str(mat)] and target in ['mu'] and e['chp']:
                c.append({'color': 'info', 'content': 'Closed above '+str(mat)+'-day moving average'})
            elif t['close'] < t['m'+str(mat)] and target in ['md'] and e['chp']:
                c.append({'color': 'info', 'content': 'Closed below '+str(mat)+'-day moving average'})

        # moving average breaking on all windows
        if target in ['mua', 'mda']:
            for i,m in enumerate(m_list):
                if len(c) < ns:
                    if t['close'] > t['m'+str(m)] and target=='mua' and e['chp']:
                        c.append({'color': 'info'+str(i), 'content': 'Closed above '+str(m)+'-day moving average', 'url':'/fb/dme/'+ss+'/mu'+str(m)+'/'})
                    if t['close'] < t['m'+str(m)] and target=='mda' and e['chp']:
                        c.append({'color': 'info'+str(i), 'content': 'Closed below '+str(m)+'-day moving average', 'url':'/fb/dme/'+ss+'/md'+str(m)+'/'})
        
        e['events'] = c
        b.append(e)
        
    return JsonResponse({'bits': b})



def get_stype_from_status(request, stype, sfunc, ss, qI = 90):
    request.path = "/api/v1/famebits/"+stype+"/"+ss+"/"
    j = globals()[sfunc](request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    if not R:
        return None
    if R["I"] >= qI:
        if stype in ['chg','cfp']:
            return stype + ('u' if IEX_cache[ss]['chg']>0 else 'd')
        elif stype=='vol':
            if R['z'] > 0:
                return stype
        else:
            return stype
    return None
            
def get_stats_and_sentences(j, ss, day_desc, day_desc2, C, B, use_SP500=False, latest=False):
    # user_SP500: flag for using SP500 as no historical event combination for this stock
    # latest: flag for passing j as the latest event
    WIN = {'2 days': [j['a_u_2d'] if j['a_u_2d'] else 0, j['a_d_2d'] if j['a_d_2d'] else 0, j['n_2d'] if j['n_2d'] else 0, int(j['n_u_2d']) if j['n_u_2d'] else 0], 
           '1 week': [j['a_u_1w'] if j['a_u_1w'] else 0, j['a_d_1w'] if j['a_d_1w'] else 0, j['n_1w'] if j['n_1w'] else 0, int(j['n_u_1w']) if j['n_u_1w'] else 0],
           '2 weeks': [j['a_u_2w'] if j['a_u_2w'] else 0, j['a_d_2w'] if j['a_d_2w'] else 0, j['n_2w'] if j['n_2w'] else 0, int(j['n_u_2w']) if j['n_u_2w'] else 0],
           '1 month': [j['a_u_1m'] if j['a_u_1m'] else 0, j['a_d_1m'] if j['a_d_1m'] else 0, j['n_1m'] if j['n_1m'] else 0, int(j['n_u_1m']) if j['n_u_1m'] else 0],
           '2 months': [j['a_u_2m'] if j['a_u_2m'] else 0, j['a_d_2m'] if j['a_d_2m'] else 0, j['n_2m'] if j['n_2m'] else 0, int(j['n_u_2m']) if j['n_u_2m'] else 0]
           }
    for k in WIN.keys():
        WIN[k].append(WIN[k][2] - WIN[k][3])
    WIN_nu = {i:WIN[i][3] for i in WIN.keys()}
    WIN_nd = {i:WIN[i][4] for i in WIN.keys()}
    ku = max(WIN_nu, key=WIN_nu.get)
    kd = max(WIN_nd, key=WIN_nd.get)
    
    C['term'] = kd if WIN_nd[kd] > WIN_nu[ku] else ku
    C['term_short'] = C['term'][0] + C['term'][2]
    C['times'] = WIN[kd][4] if WIN_nd[kd] > WIN_nu[ku] else WIN[ku][3]
    C['outof'] = WIN[kd][2] if WIN_nd[kd] > WIN_nu[ku] else WIN[ku][2]
    C['chg'] = round(abs((WIN[kd][1] if WIN_nd[kd] > WIN_nu[ku] else WIN[ku][0])*100),2)
    C['chgSign'] = "-" if WIN_nd[kd] > WIN_nu[ku] else "+"
    C['target'] = "SP500" if use_SP500 else "self"
    C['td'] = day_desc
    if use_SP500:
        B.append(str(round(C['times']*100/C['outof'])) + "% of the time an SP500 stock went " + ("up" if C['chgSign']=="+" else "down") + " in " + C['term'] + " after the day " + day_desc)
        B.append("For an average of " + str(C['chg']) + "% " + ("gain" if C['chgSign']=="+" else "loss") + " over " + C['term'])
    elif C['times'] > 1:
        B.append("During the past 6 months, " + str(C['times']) + " out of " + str(C['outof']) + " times " + ss + " went " + ("up" if C['chgSign']=="+" else "down") + " in " + C['term'] + " after the day " + day_desc)
        B.append("For an average of " + str(C['chg']) + "% " + ("gain" if C['chgSign']=="+" else "loss") + " over " + C['term'])
    elif latest:
        WIN2 = {'2 days;up':abs(j['a_u_2d']) if j['a_u_2d'] else 0,
                '2 days;down':abs(j['a_d_2d']) if j['a_d_2d'] else 0,
                '1 week;up':abs(j['a_u_1w']) if j['a_u_1w'] else 0,
                '1 week;down':abs(j['a_d_1w']) if j['a_d_1w'] else 0,
                '2 weeks;up':abs(j['a_u_2w']) if j['a_u_2w'] else 0,
                '2 weeks;down':abs(j['a_d_2w']) if j['a_d_2w'] else 0,
                '1 month;up':abs(j['a_u_1m']) if j['a_u_1m'] else 0,
                '1 month;down':abs(j['a_d_1m']) if j['a_d_1m'] else 0,
                '2 months;up':abs(j['a_u_2m']) if j['a_u_2m'] else 0,
                '2 months;down':abs(j['a_d_2m']) if j['a_d_2m'] else 0,
                }
        k2 = max(WIN2, key=WIN2.get)
        B.append("After the last " + day_desc + " day for " + ss + ", it went " + k2.split(";")[1] + " over the next " + k2.split(";")[0] + " for " + str(round(WIN2[k2]*100,2)) + "% " + ("gain" if k2.split(";")[1]=="up" else "loss"))
        B.append("That day was {dt:%A} {dt:%b} {dt.day}, {dt.year}".format(dt=j['latest']) )
        return
    else:
        B.append(ss + " went " + ("up" if C['chgSign']=="+" else "down") + " in " + C['term'] + " once after the day " + day_desc)
        B.append("That incurred " + str(C['chg']) + "% " + ("gain" if C['chgSign']=="+" else "loss") + " over that " + C['term'] )
    #print(WIN)
    
    RNG = {'1 week;up': [j['n_d5'] if j['n_d5'] else 0, j['n_u_d5'] if j['n_u_d5'] else 0, j['n_u_5'] if j['n_u_5'] else 0],
           '2 weeks;up': [j['n_d10'] if j['n_d10'] else 0, j['n_u_d10'] if j['n_u_d10'] else 0, j['n_u_10'] if j['n_u_10'] else 0],
           }
    RNG['1 week;down'] = [RNG['1 week;up'][0], (RNG['1 week;up'][0]-RNG['1 week;up'][1]) if RNG['1 week;up'][1] else RNG['1 week;up'][0], (RNG['1 week;up'][0]-RNG['1 week;up'][2]) if RNG['1 week;up'][2] else RNG['1 week;up'][0]]
    RNG['2 weeks;down'] = [RNG['2 weeks;up'][0], (RNG['2 weeks;up'][0]-RNG['2 weeks;up'][1]) if RNG['2 weeks;up'][1] else RNG['2 weeks;up'][0], (RNG['2 weeks;up'][0]-RNG['2 weeks;up'][2]) if RNG['2 weeks;up'][2] else RNG['2 weeks;up'][0]]
    for k in RNG.keys():
        RNG[k].append(RNG[k][1]/RNG[k][0]) 
        RNG[k].append(RNG[k][2]/RNG[k][0])
    RNG_x = {i:RNG[i][4] for i in RNG.keys()}
    kx = max(RNG_x, key=RNG_x.get)
    B.append(("SP500 stocks" if use_SP500 else ss) + " went " + kx.split(";")[1] + " " + str(round(RNG[kx][4]*100)) + "% of the days in " + kx.split(";")[0] + " after the " + day_desc2 + " day")
    # This seems redundant from UI
    #RNG_y = {i:RNG[i][3] for i in RNG.keys()}
    #ky = max(RNG_y, key=RNG_y.get)
    #B.append(str(round(RNG[ky][4]*100)) + "% of the days in " + ky.split(";")[0] + " the share price was " + ("higher" if ky.split(";")[1]=='up' else "lower") + " than the daily closing price of that " + day_desc2 + " day")
    #print(RNG)
    
    # wipe out actual counts for use_SP500 case
    if use_SP500:
        C['times'] = 0
        C['outof'] = 0
    return

STYPE_FUNCTIONS = {'cfp': 'famebits_ceilfloor',
                   'chg': 'famebits_changerate',
                   'pfl': 'famebits_pricefluc',
                   'vol': 'famebits_volume'
                  }
STYPE_UD_DESC   = {'cfpu': "beating 90d high",
                   'cfpd': "beating 90d low",
                   'chgu': "with large jump",
                   'chgd': "with large drop",
                   'pfl' : "having high flux",
                   'vol' : "having high volume",
                   }
STYPE_SP = """select max(dateb) latest, count(1) n, count(close2d) n_2d, count(close1w) n_1w, count(close2w) n_2w, count(close1m) n_1m, count(close2m) n_2m
, sum(if(chr2d>0,1,0)) n_u_2d, avg(if(chr2d>0,chr2d,null)) a_u_2d, avg(if(chr2d<0,chr2d,null)) a_d_2d
, sum(if(chr1w>0,1,0)) n_u_1w, avg(if(chr1w>0,chr1w,null)) a_u_1w, avg(if(chr1w<0,chr1w,null)) a_d_1w
, sum(if(chr2w>0,1,0)) n_u_2w, avg(if(chr2w>0,chr2w,null)) a_u_2w, avg(if(chr2w<0,chr2w,null)) a_d_2w
, sum(if(chr1m>0,1,0)) n_u_1m, avg(if(chr1m>0,chr1m,null)) a_u_1m, avg(if(chr1m<0,chr1m,null)) a_d_1m
, sum(if(chr2m>0,1,0)) n_u_2m, avg(if(chr2m>0,chr2m,null)) a_u_2m, avg(if(chr2m<0,chr2m,null)) a_d_2m
, count(chrd1)+count(chrd2)+count(chrd3)+count(chrd4)+count(chrd5) n_d5
, count(chrd1)+count(chrd2)+count(chrd3)+count(chrd4)+count(chrd5)+count(chrd6)+count(chrd7)+count(chrd8)+count(chrd9)+count(chrd10) n_d10
, sum(if(chrd1>0,1,0)+if(chrd2>0,1,0)+if(chrd3>0,1,0)+if(chrd4>0,1,0)+if(chrd5>0,1,0)) n_u_d5
, sum(if(chrd1>0,1,0)+if(chrd2>0,1,0)+if(chrd3>0,1,0)+if(chrd4>0,1,0)+if(chrd5>0,1,0)+if(chrd6>0,1,0)+if(chrd7>0,1,0)+if(chrd8>0,1,0)+if(chrd9>0,1,0)+if(chrd10>0,1,0)) n_u_d10
, sum(if(chrd1>0,1,0)+if(chr12>0,1,0)+if(chr23>0,1,0)+if(chr34>0,1,0)+if(chr45>0,1,0)) n_u_5
, sum(if(chrd1>0,1,0)+if(chr12>0,1,0)+if(chr23>0,1,0)+if(chr34>0,1,0)+if(chr45>0,1,0)+if(chr56>0,1,0)+if(chr67>0,1,0)+if(chr78>0,1,0)+if(chr89>0,1,0)+if(chr910>0,1,0)) n_u_10
from $SRCSUB
"""
SRC_STYPE = "ff_stock_fameon_w11 where symbol='$SYMBOL' and stype='$STYPE'"
SRC_SSTYPE = "ff_stock_fameon_w12 where symbol='$SYMBOL' and sstype='$SSTYPE'"
SRC_SSTYPE_L = "(select * from ff_stock_fameon_w12 where symbol='$SYMBOL' and sstype='$SSTYPE' order by dateb desc limit 1) a"
STYPE_NS = """select max(dateb) latest, count(1) n, count(close2d) n_2d, count(close1w) n_1w, count(close2w) n_2w, count(close1m) n_1m, count(close2m) n_2m
, sum(if(chr2d>0,1,0)) n_u_2d, avg(if(chr2d>0,chr2d,null)) a_u_2d, avg(if(chr2d<0,chr2d,null)) a_d_2d
, sum(if(chr1w>0,1,0)) n_u_1w, avg(if(chr1w>0,chr1w,null)) a_u_1w, avg(if(chr1w<0,chr1w,null)) a_d_1w
, sum(if(chr2w>0,1,0)) n_u_2w, avg(if(chr2w>0,chr2w,null)) a_u_2w, avg(if(chr2w<0,chr2w,null)) a_d_2w
, sum(if(chr1m>0,1,0)) n_u_1m, avg(if(chr1m>0,chr1m,null)) a_u_1m, avg(if(chr1m<0,chr1m,null)) a_d_1m
, sum(if(chr2m>0,1,0)) n_u_2m, avg(if(chr2m>0,chr2m,null)) a_u_2m, avg(if(chr2m<0,chr2m,null)) a_d_2m
, count(chrd1)+count(chrd2)+count(chrd3)+count(chrd4)+count(chrd5) n_d5
, count(chrd1)+count(chrd2)+count(chrd3)+count(chrd4)+count(chrd5)+count(chrd6)+count(chrd7)+count(chrd8)+count(chrd9)+count(chrd10) n_d10
, sum(if(chrd1>0,1,0)+if(chrd2>0,1,0)+if(chrd3>0,1,0)+if(chrd4>0,1,0)+if(chrd5>0,1,0)) n_u_d5
, sum(if(chrd1>0,1,0)+if(chrd2>0,1,0)+if(chrd3>0,1,0)+if(chrd4>0,1,0)+if(chrd5>0,1,0)+if(chrd6>0,1,0)+if(chrd7>0,1,0)+if(chrd8>0,1,0)+if(chrd9>0,1,0)+if(chrd10>0,1,0)) n_u_d10
, sum(if(chrd1>0,1,0)+if(chr12>0,1,0)+if(chr23>0,1,0)+if(chr34>0,1,0)+if(chr45>0,1,0)) n_u_5
, sum(if(chrd1>0,1,0)+if(chr12>0,1,0)+if(chr23>0,1,0)+if(chr34>0,1,0)+if(chr45>0,1,0)+if(chr56>0,1,0)+if(chr67>0,1,0)+if(chr78>0,1,0)+if(chr89>0,1,0)+if(chr910>0,1,0)) n_u_10
from (
select a.* 
, (close2d-closeb)/closeb chr2d, (close1w-closeb)/closeb chr1w, (close2w-closeb)/closeb chr2w, (close1m-closeb)/closeb chr1m, (close2m-closeb)/closeb chr2m
, (closed1-closeb)/closeb chrd1, (closed2-closeb)/closeb chrd2, (closed3-closeb)/closeb chrd3, (closed4-closeb)/closeb chrd4, (closed5-closeb)/closeb chrd5, (closed6-closeb)/closeb chrd6, (closed7-closeb)/closeb chrd7, (closed8-closeb)/closeb chrd8, (closed9-closeb)/closeb chrd9, (closed10-closeb)/closeb chrd10
, (closed2-closed1)/closed1 chr12, (closed3-closed2)/closed2 chr23, (closed4-closed3)/closed3 chr34, (closed5-closed4)/closed4 chr45, (closed6-closed5)/closed5 chr56, (closed7-closed6)/closed6 chr67, (closed8-closed7)/closed7 chr78, (closed9-closed8)/closed8 chr89, (closed10-closed9)/closed9 chr910
from (
select a.*, b.close closeb, c2d.close close2d, c1w.close close1w, c2w.close close2w, c1m.close close1m, c2m.close close2m, d1.close closed1, d2.close closed2, d3.close closed3, d4.close closed4, d5.close closed5, d6.close closed6, d7.close closed7, d8.close closed8, d9.close closed9, d10.close closed10
from ($CORESUB) a 
inner join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date and b.rn>0) b on a.rn=b.rn
left join (select a.close, b.close_date from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_fameon_w20 b where a.close_date=b.date2d) c2d on a.dateb=c2d.close_date
left join (select a.close, b.close_date from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_fameon_w20 b where a.close_date=b.date1w) c1w on a.dateb=c1w.close_date
left join (select a.close, b.close_date from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_fameon_w20 b where a.close_date=b.date2w) c2w on a.dateb=c2w.close_date
left join (select a.close, b.close_date from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_fameon_w20 b where a.close_date=b.date2d) c1m on a.dateb=c1m.close_date
left join (select a.close, b.close_date from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_fameon_w20 b where a.close_date=b.date2d) c2m on a.dateb=c2m.close_date
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d1 on a.rn=d1.rn+1
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d2 on a.rn=d2.rn+2
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d3 on a.rn=d3.rn+3
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d4 on a.rn=d4.rn+4
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d5 on a.rn=d5.rn+5
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d6 on a.rn=d6.rn+6
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d7 on a.rn=d7.rn+7
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d8 on a.rn=d8.rn+8
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d9 on a.rn=d9.rn+9
left join (select a.close, b.rn from (select * from ff_stock_all where symbol='$SYMBOL') a, ff_stock_w40 b where a.close_date=b.close_date) d10 on a.rn=d10.rn+10
) a ) a
"""
SUB_STYPE = "select a.*, b.rn from (select if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)) stype, date(batched) dateb, max(batched) maxb, count(1) n from ff_status_scan where symbol='$SYMBOL' group by symbol, if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)), date(batched)) a, ff_stock_w40 b where a.dateb=b.close_date and stype='$STYPE'"
SUB_SSTYPE = "select a.*, b.rn from (select dateb, group_concat(stype order by stype) sstype from (select if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)) stype, date(batched) dateb, max(batched) maxb, count(1) n from ff_status_scan where symbol='$SYMBOL' group by symbol, if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)), date(batched)) a group by dateb) a, ff_stock_w40 b where a.dateb=b.close_date and sstype='$SSTYPE'"
SUB_SSTYPE_L = "select a.*, b.rn from (select dateb, group_concat(stype order by stype) sstype from (select if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)) stype, date(batched) dateb, max(batched) maxb, count(1) n from ff_status_scan where symbol='$SYMBOL' group by symbol, if(stype='chg',if(changePct>0,'chgu','chgd'),if(stype='cfp',if(changePct>0,'cfpu','cfpd'),stype)), date(batched)) a group by dateb) a, ff_stock_w40 b where a.dateb=b.close_date and b.rn>0 and sstype='$SSTYPE' limit 1"
CND_STYPE = "stype='$STYPE'"
CND_SSTYPE = "sstype='$SSTYPE'"

@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_ahead", group="famebits_ahead", nlrate="60/m",rate="240/m")
@cache_api_internal(refresh_rate_in_seconds=300)
def famebits_ahead(request, ss="", ns=0):
    if not table_exist("ff_stock_fameon_w20"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    is_SP500 = ss in get_SP500()
    cache_IEX(ss)
    if not ss in IEX_cache:
        return JsonResponse({})

    S = []
    B = []
    C = {"I": 0}
    tmp = request.path
    for stype in STYPE_FUNCTIONS.keys():
        s = get_stype_from_status(request, stype, STYPE_FUNCTIONS[stype], ss)
        if s:
            S.append(s)
    request.path = tmp
    if not S:
        if ns > 0:
            request.path = "/api/v1/famebits/chg/"+ss+"/"+str(ns)+"/"
            j = famebits_changerate(request, ss=ss, ns=ns)
            R = json.loads(j.content.decode('utf-8'))
            return JsonResponse({'bits': R['bits']})
        else:
            return JsonResponse(C)
    
    sclause = " or ".join(["stype='"+s+"'" for s in S])
    if is_SP500:
        R = runsql("select bin, stype, cnt from ff_stock_fameon_w13 where symbol='"+ss+"' and ("+sclause+") order by cnt desc")
    else:
        R = runsql("select a.bin, b.stype, b.cnt from (select cnt, max(bin) bin from ff_stock_fameon_w13 group by cnt) a, (select stype, count(1) cnt from ff_stock_fameon_w1 where symbol='"+ss+"' and ("+sclause+") group by stype order by cnt desc) b where a.cnt=b.cnt")
    for idx, r in enumerate(R):
        C['I'] = r['bin']
        stype  = r['stype']
        rawsql = STYPE_SP.replace("$SRCSUB",SRC_STYPE).replace("$SYMBOL",ss).replace("$STYPE",stype) if is_SP500 else STYPE_NS.replace("$CORESUB",SUB_STYPE).replace("$SYMBOL",ss).replace("$STYPE",stype)
        j = runsql(rawsql)
        j = j[0]
        if j['n']>0 and j['n_2d']>0:
            get_stats_and_sentences(j, ss, STYPE_UD_DESC[stype], STYPE_UD_DESC[stype].split(" ",1)[1], C, B)
            sstype = ",".join(S)
            ssdesc = [STYPE_UD_DESC[s] for s in S]
            ssdesc = ", ".join(ssdesc[:-1]) + " and " + ssdesc[-1]
            ssdesc2 = [STYPE_UD_DESC[s].split(" ",1)[1] for s in S]
            ssdesc2 = ", ".join(ssdesc2[:-1]) + " and " + ssdesc2[-1]
            if len(S) > 1 and idx == 0:
                g = runsql(STYPE_SP.replace("$SRCSUB",SRC_SSTYPE).replace("$SYMBOL",ss).replace("$SSTYPE",sstype) if is_SP500 
                           else STYPE_NS.replace("$CORESUB",SUB_SSTYPE).replace("$SYMBOL",ss).replace("$SSTYPE",sstype))
                g = g[0]
                if g['n']>0 and g['n_2d']>0:
                    get_stats_and_sentences(g, ss, ssdesc, ssdesc2, {}, B)
                    break
            if j['n']>1:
                if len(S) == 1:
                    ssdesc2 = STYPE_UD_DESC[stype].split(" ",1)[1] + " (only)"
                h = runsql(STYPE_SP.replace("$SRCSUB",SRC_SSTYPE_L).replace("$SYMBOL",ss).replace("$SSTYPE",sstype) if is_SP500
                           else STYPE_NS.replace("$CORESUB",SUB_SSTYPE_L).replace("$SYMBOL",ss).replace("$SSTYPE",sstype))[0]
                if h['n']>0 and h['n_2d']>0:
                    get_stats_and_sentences(h, ss, ssdesc2, "", {}, B, latest=True)
    if not B:
        sstype = ",".join(S)
        rawsql = STYPE_SP.replace("$SRCSUB","ff_stock_fameon_w12 where sstype='$SSTYPE'").replace("$SSTYPE",sstype)
        j = runsql(rawsql)[0]
        if j['n']>0 and j['n_2d']>0:
            if len(S) > 1:
                ssdesc = [STYPE_UD_DESC[s] for s in S]
                ssdesc = ", ".join(ssdesc[:-1]) + " and " + ssdesc[-1]
                ssdesc2 = [STYPE_UD_DESC[s].split(" ",1)[1] for s in S]
                ssdesc2 = ", ".join(ssdesc2[:-1]) + " and " + ssdesc2[-1]
            else:
                ssdesc = STYPE_UD_DESC[S[0]]
                ssdesc2 = STYPE_UD_DESC[S[0]].split(" ",1)[1]
            get_stats_and_sentences(j, '', ssdesc, ssdesc2, C, B, use_SP500=True)

    if ns == 0:
        return JsonResponse(C)
        
    return JsonResponse({'bits': B})









@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_sense0", group="famebits_sense0", nlrate="2/m",rate="12/m")
@cache_api_internal(refresh_rate_in_seconds=3600)
def famebits_sense_symbol_0(request, ss="", sense_raw=[], sense_interval="3 month", return_json=True):
    if not check_SP500_and_table(ss, "ff_finnews_f0"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    
    if not sense_raw:
        sense_raw = runsql("select * from ff_finnews_f0 where symbol='"+ss+"' and dest_date>date_sub(curdate(),interval "+sense_interval+") order by dest_date desc limit 1")
        if not sense_raw:
            return JsonResponse({})
    current = sense_raw[0]
    sense_drift, _ = get_rarity_quantifier_single(min(100, 50+2*abs(current['dense_diff'])), "gain" if current['dense_diff']>0 else "loss")
    sense_drift = "little drift" if sense_drift == "normal" else sense_drift
    sense_desc, _ = get_rarity_descriptor_single(50 + abs(current['dense_sense']-50), 'positive' if current['dense_sense']>50 else 'negative')
    sense_desc = 'neutral' if sense_desc=='normal' else sense_desc
    rd = {
          "sense_drift": sense_drift.capitalize(),
          "sense_desc": sense_desc.capitalize(),
          }
    if return_json:
        return JsonResponse(rd)
    else:
        return rd





@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_sense", group="famebits_sense", nlrate="2/m",rate="12/m")
@cache_api_internal(refresh_rate_in_seconds=3600)
def famebits_sense_symbol(request, ss="", sense_interval="3 month", sense_doc_interval="1 month", sense_doc_limit=5):
    # Cannot be extended to non-SP500
    if not check_SP500_and_table(ss, "ff_finnews_f0"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    
    sense_raw = runsql("select * from ff_finnews_f0 where symbol='"+ss+"' and dest_date>date_sub(curdate(),interval "+sense_interval+") order by dest_date desc")
    if not sense_raw:
        return JsonResponse({})
    sense0 = famebits_sense_symbol_0(request, ss=ss, sense_raw=sense_raw, return_json=False)
    
    """
    current = sense_raw[0]
    sense_drift, _ = get_rarity_quantifier_single(min(100, 50+2*abs(current['dense_diff'])), "gain" if current['dense_diff']>0 else "loss")
    sense_drift = "little drift in sentiments" if sense_drift == "normal" else (sense_drift + " in sentimental confidence")
    sense_desc, _ = get_rarity_descriptor_single(current['dense_sense'], 'positive' if current['dense_sense']>50 else 'negative')
    sense_desc = 'neutral' if sense_desc=='normal' else sense_desc
    """
    dense_points = [{k: i[k] for k in ('dest_date', 'dense_sense')} for i in sense_raw]
    #sense_docs = runsql("select iex_id id, published, bin_diff, iex_source source, iex_title title, iex_related related, article_url url, article_255 from ff_finnews_f2 where symbol='"+ss+"' and published>date_sub(curdate(), interval "+sense_doc_interval+") order by published desc limit "+str(sense_doc_limit))
    sense_docs = runsql("select a.iex_id id, any_value(a.published) published, any_value(a.bin_diff) bin_diff, any_value(a.iex_source) source, any_value(iex_title) title, any_value(iex_related) related, any_value(article_url) url, group_concat(sentence SEPARATOR '. ') abstract from (select * from ff_finnews_f2 where symbol='"+ss+"' and published>date_sub(curdate(), interval "+sense_doc_interval+") order by published desc limit "+str(sense_doc_limit)+") a, ff_finnews_f3 b where a.iex_id=b.iex_id and b.key_id<3 group by a.iex_id order by published desc")
    for d in sense_docs:
        d['related'] = [s for s in d['related'].split(",") if len(s)<6 and s.upper()!=ss]
        f, _ = get_rarity_quantifier_single(50+abs(d['bin_diff'])/2, "bump" if d['bin_diff']>0 else "drag")
        d['contribution'] = "neutral" if f == "normal" else f
        d['url'] = "/re?s="+ss+"&v=fh_symbol_doc&t=news&u="+d['url']
    rd = {"symbol": ss,
          "sense_drift": sense0['sense_drift'],
          "sense_desc": sense0['sense_desc'],
          "dense_points": dense_points,
          "sense_docs": sense_docs,
          }
    return JsonResponse(rd)


def famebits_sense_symbol_more(request, ss=""):
    return famebits_sense_symbol(request, ss=ss, sense_doc_limit=20)



@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_sense", group="famebits_sense", nlrate="2/m",rate="12/m")
@cache_api_internal(refresh_rate_in_seconds=14400)
def famebits_sense_symboldoc(request, ss="", iex_id=0):
    # Cannot be extended to non-SP500
    if not check_SP500_and_table(ss, "ff_finnews_f2"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    
    #symbol_doc = runsql("select a.*, c.zero, if(bin>zero,50*(bin-zero)/(100-zero),50*(bin-zero)/zero) bin_zero, b.iex_title, b.published, b.iex_source, b.iex_related, b.article_url from (select * from ff_finnews_f2 where symbol='"+ss+"' and iex_id='"+str(iex_id)+"') a inner join (select bin-min_con/(max_con-min_con) zero from ff_finnews_b7 where min_con<0 and max_con>0) c left join ff_finnews_iex b on a.iex_id=b.iex_id limit 1")
    symbol_doc = runsql("select a.*, c.zero, if(bin>zero,50*(bin-zero)/(100-zero),50*(bin-zero)/zero) bin_zero from (select * from ff_finnews_f2 where symbol='"+ss+"' and iex_id='"+str(iex_id)+"') a inner join (select bin-min_con/(max_con-min_con) zero from ff_finnews_b7 where min_con<0 and max_con>0) c")
    if not symbol_doc:
        return JsonResponse({})
    symbol_doc = symbol_doc[0]
    focus_sense, _ = get_rarity_descriptor_single(50+abs(symbol_doc['bin_diff'])/2, "positive" if symbol_doc['bin_diff']>0 else "negative")
    focus_sense = "neutral" if focus_sense == "normal" else focus_sense
    global_sense, _ = get_rarity_descriptor_single(50+abs(symbol_doc['bin_zero']), "positive" if symbol_doc['bin_zero']>0 else "negative")
    global_sense = "neutral" if global_sense == "normal" else global_sense
    rd = {"symbol": symbol_doc['symbol'],
          "iex_id": symbol_doc['iex_id'],
          "title": symbol_doc['iex_title'],
          "published": symbol_doc['published'].strftime("%a %I:%M%p, %b %d %Y").lstrip("0").replace(" 0", " "),
          "source": symbol_doc['iex_source'],
          "url": "/re?s="+ss+"&v=fb_sendoc&t=news&u="+symbol_doc['article_url'],
          "dest_date": symbol_doc['dest_date'],
          "global_sense": global_sense.capitalize(),
          "focus_sense": focus_sense.capitalize(),
          "related": [r for r in symbol_doc['iex_related'].split(",") if len(r)<6],
          }
    return JsonResponse(rd)

@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_sense", group="famebits_sense", nlrate="2/m",rate="12/m")
@cache_api_internal(refresh_rate_in_seconds=14400)
def famebits_sense_doc(request, iex_id="", n_sentences=5, max_sentences=5, additional=""):
    # Cannot be extended to non-SP500
    if not table_exist("ff_finnews_f3") or not table_exist("ff_finnews_f4"):
        return JsonResponse({})
    
    if n_sentences > max_sentences:
        n_sentences = max_sentences 
    sentences = runsql("select * from ff_finnews_f3 where iex_id='"+str(iex_id)+"'")
    if not sentences:
        return JsonResponse({})
    sentences_by_weight = sorted(sentences, key=lambda k: k['key_weight'])
    if len(sentences_by_weight) >= n_sentences:
        key_cut = sentences_by_weight[::-1][n_sentences-1]['key_weight']
    else:
        key_cut = sentences_by_weight[0]['key_weight']
    sentences = [s['sentence'] for s in sentences if s['key_weight']>=key_cut]
    if additional.lower() == "wrap":
        keywords = runsql("select * from ff_finnews_f4 where iex_id='"+str(iex_id)+"'")
        if not keywords:
            return JsonResponse({"bits": sentences})
        K = {}
        for k in keywords:
            K[k['word']] = k['key_weight']
        wrapped_sentences = []
        for s in sentences:
            W = s.split()
            wrapped = []
            for w in W:
                for k in K.keys():
                    if k in w.lower() and k not in wrapped:
                        v = str(int(255*(K[k]**(0.5)/2+0.5)))
                        s = s.replace(w, "<span style='color:rgb("+v+","+v+","+v+")'>"+w+"</span>")
                        wrapped.append(k)
            wrapped_sentences.append("<span style='color:rgb(128,128,128)'>"+s+"</span>")
        return JsonResponse({"bits": wrapped_sentences})
        #print(sentences)
    return JsonResponse({"bits": sentences})


@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_sense", group="famebits_sense", nlrate="2/m",rate="12/m")
@cache_api_internal(refresh_rate_in_seconds=14400)
def famebits_sense_symboldoc_track(request, ss="", iex_id=0):
    # Cannot be extended to non-SP500
    if not check_SP500_and_table(ss, "ff_finnews_f5"):
        return JsonResponse({})
    ss = ss.upper().replace('-','.')
    p = runsql("select * from ff_finnews_f5 where symbol='"+ss+"' and iex_id='"+str(iex_id)+"'")
    if not p:
        return JsonResponse({})
    p = p[0]
    rl = []
    if p['close_s']:
        rl.append({"date":p['date_same'], "date_desc":"published date", "close":p['close_s'], "chgPercent":round(p['chg_sameday']*100,2)})
    if p['close_1d']:
        rl.append({"date":p['date_1d'], "date_desc":"1 market day after published", "close":p['close_1d'], "chgPercent":round(p['chg_1d']*100,2)})
    if p['close_2d']:
        rl.append({"date":p['date_2d'], "date_desc":"2 market days after published", "close":p['close_2d'], "chgPercent":round(p['chg_2d']*100,2)})
    if p['close_1w']:
        rl.append({"date":p['date_1w'], "date_desc":"1 week after published", "close":p['close_1w'], "chgPercent":round(p['chg_1w']*100,2)})
    if p['close_2w']:
        rl.append({"date":p['date_2w'], "date_desc":"2 weeks after published", "close":p['close_2w'], "chgPercent":round(p['chg_2w']*100,2)})
    if p['close_1m']:
        rl.append({"date":p['date_1m'], "date_desc":"1 month after published", "close":p['close_1m'], "chgPercent":round(p['chg_1m']*100,2)})
    if p['close_2m']:
        rl.append({"date":p['date_2m'], "date_desc":"2 months after published", "close":p['close_2m'], "chgPercent":round(p['chg_2m']*100,2)})
    if rl:
        return JsonResponse({"bits": rl})
    else:
        return JsonResponse({})




























def get_sector_move(spy_chg, CUT_RATIO=0.8, NEED_RATIO=0.5, MIN_MOVE_PCT=0.8, SPY_CUT=0.005):
    b = ''
    if not table_exist("ff_status_scan_w4"):
        return b
    S = runsql("select * from ff_status_scan_w4 order by marketchgPct desc")
    if not S:
        return b
    max_chg = S[0]['marketchgPct']
    min_chg = S[-1]['marketchgPct']
    strong_max = False
    strong_min = False
    to_add = []
    if S[1]['marketchgPct'] < NEED_RATIO*max_chg and S[1]['marketchgPct'] > 0 and spy_chg > -SPY_CUT*2:
        strong_max = True
        to_add.append("max")
    if S[-2]['marketchgPct'] > NEED_RATIO*min_chg and S[-2]['marketchgPct'] < 0 and spy_chg < SPY_CUT*2:
        strong_min = True
        to_add.append("min")
    if S[2]['marketchgPct'] < CUT_RATIO*max_chg and S[1]['marketchgPct'] > 0 and max_chg > MIN_MOVE_PCT and "max" not in to_add and spy_chg > -SPY_CUT and max_chg>-min_chg/2:
        to_add.append("max")
    if S[-3]['marketchgPct'] > CUT_RATIO*min_chg and S[-2]['marketchgPct'] < 0 and -min_chg > MIN_MOVE_PCT and "min" not in to_add and spy_chg < SPY_CUT and min_chg<-max_chg/2:
        to_add.append("min")
    t_max = ''
    t_min = ''
    if "max" in to_add:
        t_max = S[0]['sector']+" sector" if S[1]['marketchgPct']<CUT_RATIO*max_chg else S[0]['sector']+" and "+S[1]['sector']+" sectors"
        t_max += " strongly" if strong_max else ""
    if "min" in to_add:
        t_min = S[-1]['sector']+" sector" if S[-2]['marketchgPct']>CUT_RATIO*min_chg else S[-1]['sector']+" and "+S[-2]['sector']+" sectors"
        t_min += " strongly" if strong_min else ""
    if spy_chg > 0:
        #b = 'Carried by '+t_max+(' and dragged by '+t_min if t_min and t_max[-7:]!='sectors' else '') if t_max else ('Dragged by '+t_min if t_min else '')
        b = 'Carried by '+t_max+(', and dragged by '+t_min if t_min and strong_min else '') if t_max else ('Dragged by '+t_min if t_min else '')
    else:
        #b = 'Dragged by '+t_min+(' and carried by '+t_max if t_max and t_min[-7:]!='sectors' else '') if t_min else ('Carried by '+t_max if t_max else '')
        b = 'Dragged by '+t_min+(', and carried by '+t_max if t_max and strong_max else '') if t_min else ('Carried by '+t_max if t_max else '')
    return b






def get_trust_traded(R_TIME_BEND=1/2):
    B = runsql("select * from ff_status_scan_w1 order by rn limit 1")[0]
    t_batched = eastern.localize(B['batched'])
    t_enow    = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)
    t_diff    = t_enow - t_batched
    t_diff_nb = (t_diff.days * 86400 + t_diff.seconds) // 3600
    t_traded  = (t_enow.hour + t_enow.minute/60) - 9.5
    if t_diff_nb < 8 and t_traded >= 0 and t_traded < 7:
        r_trust = 0.3 + 0.7 *  math.pow(min(t_traded/6.5,1), R_TIME_BEND)
    else:
        r_trust = 1
    return r_trust, t_traded, t_batched

def get_index_descriptor(i, r_trust):
    c1 = ''
    if i > 0.03:
        c1 = ("soars" if r_trust < 1 else "rocketed")
    elif i > 0.02:
        c1 = ("blooms" if r_trust < 1 else "roared")
    elif i > 0.01:
        c1 = ("takes off" if r_trust < 1 else "took off")
    elif i > 0.005:
        c1 = ("trends up" if r_trust < 1 else "moved up")
    elif i < -0.03:
        c1 = ("dives" if r_trust < 1 else "sank")
    elif i < -0.02:
        c1 = ("diminishes" if r_trust < 1 else "faded")
    elif i < -0.01:
        c1 = ("drops" if r_trust < 1 else "stumbled")
    elif i < -0.005:
        c1 = ("tumbles" if r_trust < 1 else "moved down")
    return c1


def famebits_marketbits_rich(request, ns=0):
    """
    b = []
    try:
        j = famebits_marketbits(request, ns=ns)
        j = json.loads(j.content)
        b = j['bits']
        for i,bb in enumerate(b):
            bb, f_hassymbol = wrap_symbol_url(bb, objtag="a", objclass="text-warning", objurl="/fh/$SYMBOL/", sametab=False)
            if f_hassymbol:
                b[i] = bb
            else:
                bb, f_withfamer = wrap_famer_url(bb, objtag="a", objclass="text-warning", sametab=False)
                if f_withfamer:
                    b[i] = bb
                else:
                    b[i] = wrap_sector_url(bb, objtag="a", objclass="text-warning", sametab=False)
    except Exception as e:
        print(e)
        if b:
            return JsonResponse({'bits': b})
        else:
            return j
    return JsonResponse({'bits': b})
    """
    return famebits_marketbits(request, ns=ns, wrap_url=True)

N_UD_THRESH = 10
N_UD_THRESH_ = 3
# TODO: should use NLTK to convert to past tense
# https://stackoverflow.com/questions/3753021/using-nltk-and-wordnet-how-do-i-convert-simple-tense-verb-into-its-present-pas
@getUser()
@ratelimittrylogin(nlgroup="tryfamebits_marketbits", group="famebits_marketbits", nlrate="6/m",rate="60/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_marketbits(request, ns=0, wrap_url=False, n_symbol=10, N_DEMO_STOCKS=30, T_VERBAGE=5, MARKETCAP_TH_RATIO=0.7, MARKETCAP_TH=20000000000, N_TOLD_INDI=2):
    if not table_exist("ff_status_scan_w2"):
        return JsonResponse({})
    
    cache_IEX("SPY")
    if "SPY" not in IEX_cache:
        return JsonResponse({})
    spy_chg = IEX_cache["SPY"]['chg']


    b = []
    SCOUNT = runsql("select * from ff_status_scan_w2")
    #B = runsql("select * from ff_status_scan_w1 order by rn limit 1")[0]
    S = deepcopy(STYPE_LIST)
    for s in S:
        if s['ftype'] == "f66":
            s['cnt'] = 20
        elif s['sch'] == "b":
            s['cnt'] = sum([i['n'] for i in SCOUNT if i['stype']==s['stype']])
        else:
            idx = next((i for i,d in enumerate(SCOUNT) if d['stype']==s['stype'] and d['ch']==s['sch']), -1)
            if idx >=0 :
                s['cnt'] = SCOUNT[idx]['n']
            else:
                s['cnt'] = 0
        s.pop('stype', None)
        s.pop('sclause', None)
        s.pop('sch', None)
    if ns == 0:
        return JsonResponse({'bits': S})

    F = [i['stype'] for i in SCOUNT]
    #n_target  = len(get_SP500())
    n_target  = len(get_nonSP500())
    r_trust, t_traded, t_batched = get_trust_traded()

    B = runsql("select * from ff_status_scan_w1 where n_symbol>="+str(n_symbol)+" order by rn limit 1")[0]
    t_info = eastern.localize(B['batched'])
    t_diff = t_batched - t_info
    t_diff_hr_batch = (t_diff.days * 86400 + t_diff.seconds) // 3600
    if t_diff_hr_batch > 16:
        outdated_useful_scan = True
    else:
        outdated_useful_scan = False


    c  = "Market"
    c1 = get_index_descriptor(spy_chg, r_trust)
    c2 = ''
    c3 = ''
    u  = 0
    d  = 0
    r_chg = 0
    state_flipflop = False
    booked = []
    told   = []

    if ('chg' in F) and not outdated_useful_scan:
        u = next((i['n'] for i in SCOUNT if i['stype'] == 'chg' and i['ch'] == 'u'),0)
        d = next((i['n'] for i in SCOUNT if i['stype'] == 'chg' and i['ch'] == 'd'),0)
        r_chg = u / (d + 0.0001) 
        if sum([i['n'] for i in SCOUNT if i['stype']=='chg']) > r_trust * 0.2 * n_target:
            if r_chg > N_UD_THRESH:
                c2 = ("fiercely" if R(0.5) else "overwhelmingly")  if c1 else "climbed"
            elif r_chg < 1 / N_UD_THRESH:
                c2 = ("soundly" if R(0.5) else "completely") if c1 else "fell"
            else:
                c2 = "" if c1 else ("trembles" if r_trust < 1 else "trembled")
        elif sum([i['n'] for i in SCOUNT if i['stype']=='chg']) < r_trust * 0.02 * n_target:
            c2 = "quietly" if c1 else ("sleeps" if r_trust < 1 else "slept")
        else:
            c2 = "" if c1 else ("calms" if r_trust<0.5 else ("stabilized" if R(0.3) else ("calmed" if R(0.3) else "converged") ) )
            if t_traded < T_VERBAGE and r_trust < 1:
                c2 = c2.replace("ed","ing")

        if c1:
            C_LIST = runsql("select a.symbol, a.marketcap, a.changePct, (log10(a.marketCap)-9)*(log10(abs(a.changePct*100)+1)) w_mc from ff_status_scan a, (select batched as max_batched from ff_status_scan_w1 where n_symbol>="+str(n_symbol)+" order by rn limit 1) b where a.batched=b.max_batched and stype='chg' and changePct"+("<" if spy_chg<0 else ">")+"0 order by infov desc, marketcap desc limit 20")
            C_LIST = [c for c in C_LIST if c['symbol'] not in BLOCKED_STOCKS]
            #C_SORT = sorted(C_LIST, key=lambda k: k['marketcap'], reverse=True)
            C_SORT = sorted(C_LIST, key=lambda k: k['w_mc'], reverse=True)
            ct = [i['symbol'] for i in C_SORT[:3]]
            if ct:
                booked += ct
                c3 = " and ".join(ct).replace(" and", ",", 1)
                c3 = (", following " if spy_chg<0 else ", led by ") + c3
    
    if c1 or c2:
        c = "Market " + c1 + (" " if c1 and c2 else "") + c2 + c3
    else:
        if t_traded < T_VERBAGE and r_trust < 1:
            c = "Trading started"
        else:
            c = "Market quiet"
            if r_trust > 0.9 and r_trust < 1:
                c += " toward close"
    b.append(c)
    # early report after trading started, before meaningful scan comes in
    if outdated_useful_scan:
        return JsonResponse({'bits': b})

    if len(b) < ns and (u > r_trust*0.1*n_target or d > r_trust*0.1*n_target):
        if spy_chg>0:
            if r_chg > N_UD_THRESH:
                _ = ("soars" if r_trust<1 else "soared") if R(0.5) else ("rises" if r_trust<1 else "rose")
                b.append(str(u) + " major stocks " + _ + (" significantly" if R(0.7) else ""))
            #elif r_chg > N_UD_THRESH_ and u>r_trust*0.1* n_target:
            elif u > r_trust * 0.08 * n_target:
                if u>r_trust * 0.2 * n_target:
                    qfer = "Many"
                else:
                    qfer = "Some"
                b.append((qfer + " major stocks with large jump") if R(0.5) else (qfer +" "+("gain" if r_trust<1 else "gained")+" a lot"))
        else:
            if r_chg < 1/N_UD_THRESH:
                _ = ("tank" if r_trust<1 else "tanked") if R(0.5) else ("sink" if r_trust<1 else "sank")
                b.append(str(d) + " major stocks " + _ + (" significantly" if R(0.4) else ""))
            #elif r_chg < 1/N_UD_THRESH_ and d>r_trust*0.1* n_target:
            elif d > r_trust * 0.08 * n_target:
                if d>r_trust * 0.2 * n_target:
                    qfer = "Many"
                else:
                    qfer = "Some"
                b.append((qfer + " major stocks with heavy drop") if R(0.5) else (qfer +" "+("fall" if r_trust<1 else "fell")+" a lot"))
    
    if len(b) < ns:
        n_pfl = sum([i['n'] for i in SCOUNT if i['stype']=='pfl'])
        if n_pfl > n_target * 0.1 * r_trust:
            c = str(n_pfl) + (" major stocks" if len(b)<2 else "") + " fluctuated" + (" heavily" if R(0.5) else (" severely" if R(0.5) else ""))
            u = next((i['n'] for i in SCOUNT if i['stype'] == 'pfl' and i['ch'] == 'u'),0)
            d = next((i['n'] for i in SCOUNT if i['stype'] == 'pfl' and i['ch'] == 'd'),0)
            r_chg = u / (d + 0.0001)
            if r_chg > N_UD_THRESH:
                c += (", with "+str(u) if u<n_pfl else " and all") + (" going up" if r_trust<1 else " went up")
            elif r_chg > N_UD_THRESH_:
                c += " with most" + (" going up" if r_trust<1 else " went up")
            elif r_chg < 1 / N_UD_THRESH:
                c += (", with "+str(d) if d<n_pfl else " and all") + (" going down" if r_trust<1 else " went down")
            elif r_chg < 1 / N_UD_THRESH_:
                c += " with most" + (" going down" if r_trust<1 else " went down")
            b.append(c)
        
    if len(b) < ns:
        u = next((i['n'] for i in SCOUNT if i['stype'] == 'cfp' and i['ch'] == 'u'),0)
        d = next((i['n'] for i in SCOUNT if i['stype'] == 'cfp' and i['ch'] == 'd'),0)
        if u > d and u > n_target * 0.08 * r_trust:
            b.append(str(u) + (" major stocks" if len(b)<2 else "") + " " + ("trading" if r_trust<1 else "traded") + " above 90-day high")
        elif u < d and d > n_target * 0.08 * r_trust:
            b.append(str(d) + (" major stocks" if len(b)<2 else "") + " " + ("trading" if r_trust<1 else "traded") + " below 90-day low")

    if len(b) < ns:
        bb = get_sector_move(spy_chg)
        if bb:
            b.append(bb)

    
    C_LIST = runsql("select a.* from ff_status_scan a, (select batched as max_batched from ff_status_scan_w1 where n_symbol>="+str(n_symbol)+" order by rn limit 1) b where a.batched=b.max_batched order by infov desc, marketcap desc limit "+str(N_DEMO_STOCKS))
    C_LIST = [s for s in C_LIST if s['symbol'] not in BLOCKED_STOCKS]
    n_list = len(C_LIST)
    n_told = len(list(set([i['stype'] for i in C_LIST])))
    if n_list:
        C_SORT = sorted(C_LIST, key=lambda k: k['marketcap'], reverse=True)
        th = max( C_SORT[ int(n_list*MARKETCAP_TH_RATIO) ]['marketcap'], MARKETCAP_TH)
        for i in C_LIST:
            if len(b) >= ns or len(told) >= n_told or len(told) >= N_TOLD_INDI:
                break
            if i['marketcap'] >= th and i['symbol'] not in booked and i['stype'] not in told:
                ctx = json.loads(i['context'].replace("'",'"'))
                if i['stype'] == "chg":
                    if c3 and len(b)<2 or state_flipflop:
                        c4 = i['rarity'].capitalize() + " " + (str(round(abs(ctx['chg'])*100,2))+"% " if r_trust==1 else "") + ("loss" if i['changePct']<0 else "gain") + " by " + i['symbol']
                        state_flipflop = False
                    else:
                        if r_trust < 1:
                            c4 = i['symbol'] + " " + ctx['move'] + " " + str(round(abs(ctx['chg'])*100,2)) + "%"
                        else:
                            JS = ("rally" if "extreme" in i['rarity'] else ("jump" if "very" in i['rarity'] else "gain")) if i['changePct']>0 else ("crash" if "extreme" in i['rarity'] else ("dive" if "very" in i['rarity'] else "drop"))
                            c4 = i['symbol'] + " had " + i['rarity'] + " " + str(round(abs(ctx['chg'])*100,2)) + "% " + JS
                        state_flipflop = True
                    b.append(c4)
                elif i['stype'] == "vol":
                    if c3 and len(b)<2 or state_flipflop:
                        c4 = i['rarity'].capitalize() + " volume on " + i['symbol']
                        state_flipflop = False
                    else:
                        c4 = i['symbol'] + (" with " if R(0.5) else " traded on ") + i['rarity'] + " volume"
                        state_flipflop = True
                    b.append(c4)
                elif i['stype'] == "pfl":
                    if c3 and len(b)<2 or state_flipflop:
                        c4 = i['rarity'].capitalize() + " flux on " + i['symbol']
                        state_flipflop = False
                    else:
                        c4 = i['symbol'] + " with " + i['rarity'] + " flux"
                        state_flipflop = True
                    b.append(c4)
                elif i['stype'] == "cfp":
                    c4 = i['symbol'] + " " + ctx['target'] + " " + ctx['move']
                    b.append(c4)
                booked.append(i['symbol'])
                told.append(i['stype'])
    
    #b.append("Testing sector using Communication Services sector")
    if wrap_url:
        for i,bb in enumerate(b):
            bb, f_hassymbol = wrap_symbol_url(bb, objtag="a", objclass="text-warning", objurl="/fh/$SYMBOL/", sametab=False)
            if f_hassymbol:
                b[i] = bb
            else:
                bb, f_withfamer = wrap_famer_url(bb, objtag="a", objclass="text-warning", sametab=False)
                if f_withfamer:
                    b[i] = bb
                else:
                    b[i] = wrap_sector_url(bb, objtag="a", objclass="text-warning", sametab=False)
    return JsonResponse({'bits': b})



@getUser()
@cache_api_internal(refresh_rate_in_seconds=60)
def famebits_sectorbits(request, sec="", wrap_url=False, ns=10, UD_SMOOTH=5):
    sec = assure_sec(sec)
    if not sec:
        return JsonResponse({})
    q = runsql("select * from ff_status_scan_w6 where sector='"+sec+"'")
    if not q:
        return JsonResponse({})
    q = q[0]
    
    r_trust, t_traded, _ = get_trust_traded()
    c = get_index_descriptor(q['marketchgPct']/100, r_trust)
    c = (c if c else "quiet")
    
    b = []
    b.append(sec + " sector " + c + (" with " + str(abs(q['marketchgPct'])) + "% " + ("loss" if q['marketchgPct']<0 else "gain") if q['marketchgPct']!=0 else ""))
    
    top3 = ['first','second','third']
    if len(b)<ns:
        c = runsql("select sector from ff_status_scan_w6 order by marketchgPct" + (" desc" if q['cm']>0 else ""))
        c = [i['sector'] for i in c[:3]]
        if sec in c:
            i = c.index(sec)
            b.append("That "+("ranks " if r_trust<1 else "ranked ") + top3[i] + " in percentage " +("gain" if q['cm']>0 else "loss")+ " among all sectors")

    if len(b)<ns:
        c = (str(q['n_u']) if q['cm']>0 else str(q['n_d'])) + " of " + str(q['cnt']) + " major component stocks " + ("go " if r_trust<1 else "went ") + ("up " if q['cm']>0 else "down ") + "for a total sector " + ("gain " if q['cm']>0 else "loss ") + "of " + human_format(abs(q['cm']))
        b.append(c)

    if len(b)<ns:
        c = runsql("select sector from ff_status_scan_w6 order by cm" + (" desc" if q['cm']>0 else ""))
        c = [i['sector'] for i in c[:3]]
        if sec in c:
            i = c.index(sec)
            b.append("That " + ("is" if r_trust<1 else "was") + " top "+str(i+1)+" in total market value " + ("gain" if q['cm']>0 else "loss") + " over sectors")
    
    if len(b)<ns:
        E = runsql("select * from ff_status_scan_w5 where sector='"+sec+"' order by s_ratio desc")
        if E:
            c = []
            for e in E:
                if e['stype']=='chg':
                    if e['n_u']/(e['n_d']+UD_SMOOTH) > 1:
                        c.append(str(e['n_u']) + " with very large gain")
                    elif e['n_d']/(e['n_u']+UD_SMOOTH) > 1:
                        c.append(str(e['n_d']) + " with very large loss")
                elif e['stype']=='vol':
                    c.append(str(e['n']) + " traded on very high volume")
                elif e['stype']=='pfl':
                    c.append(str(e['n']) + " fluctuated heavily")
                elif e['stype']=='cfp' and (q['marketchgPct']>0 and e['n_u']>0 or q['marketchgPct']<0 and e['n_d']>0):
                    c.append( (str(e['n_u']) if q['marketchgPct']>0 else str(e['n_d']))  + " quoted " + ("above 90-day high" if q['marketchgPct']>0 else "below 90-day low") )
            if c:
                c0 = " and ".join(c).replace(" and",",",len(c)-2)
                b.append(c0)

    if len(b)<ns:
        c = ''
        if q['marketchgPct'] > 0 :
            M = runsql("select * from ff_status_scan_w7 where sector='"+sec+"' and marketeff>0 order by marketeff desc")
            if M:
                M = [m for m in M if m['symbol'] not in BLOCKED_STOCKS]
                M = [m['symbol'] for m in M[:3]]
                m = " and ".join(M).replace(" and",",",len(M)-2)
                c = "Led by " + m
        else:
            M = runsql("select * from ff_status_scan_w7 where sector='"+sec+"' and marketeff<0 order by marketeff")
            if M:
                M = [m for m in M if m['symbol'] not in BLOCKED_STOCKS]
                M = [m['symbol'] for m in M[:3]]
                m = " and ".join(M).replace(" and",",",len(M)-2)
                c = "Dragged by " + m
        if c:
            b.append(c)
    
    if len(b)<ns:
        if q['marketchgPct'] > 0 :
            N = runsql("select * from ff_status_scan_w7 where sector='"+sec+"' and marketeff>0 order by changePct desc")
            if N:
                N = [m for m in N if m['symbol'] not in BLOCKED_STOCKS]
                N = [m['symbol'] for m in N[:3] if m['symbol'] not in M]
                if N:
                    n = " and ".join(N).replace(" and",",",len(N)-2)
                    b.append("Biggest winner" + (("s are" if r_trust<1 else "s were") if len(N)>1 else (" is" if r_trust<1 else " was")) + " " + n)
        else:
            N = runsql("select * from ff_status_scan_w7 where sector='"+sec+"' and marketeff<0 order by changePct")
            if N:
                N = [m for m in N if m['symbol'] not in BLOCKED_STOCKS]
                N = [m['symbol'] for m in N[:3] if m['symbol'] not in M]
                if N:
                    n = " and ".join(N).replace(" and",",",len(N)-2)
                    b.append("Biggest loser" + (("s are" if r_trust<1 else "s were") if len(N)>1 else (" is" if r_trust<1 else " was")) + " " + n)

    if wrap_url:
        for i,bb in enumerate(b):
            bb, _ = wrap_symbol_url(bb, objtag="a", objclass="text-warning", objurl="/fh/$SYMBOL/", sametab=False)
            b[i] = bb

    return JsonResponse({'bits': b})


def famebits_sectorbits_rich(request, sec="", ns=10):
    """
    b = []
    try:
        j = famebits_sectorbits(request, sec=sec, ns=ns)
        j = json.loads(j.content)
        j = j['bits']
        for i in j:
            bb, _ = wrap_symbol_url(i, objtag="a", objclass="text-warning", objurl="/fh/$SYMBOL/", sametab=False)
            b.append(bb)
    except Exception as e:
        print(e)
        if b:
            return JsonResponse({'bits': b})
        else:
            return j
    return JsonResponse({'bits': b})
    """
    return famebits_sectorbits(request, sec=sec, ns=ns, wrap_url=True)





























from ff_app.defs import STYPE_LIST, STYPE_LIST_MAX_ROWS
STYPE_SQL  = "select @rn:=@rn+1 rn, a.* from (select a.symbol, a.marketcap, a.updated, round(a.infov) infov from ff_status_scan a, (select batched as max_batched from ff_status_scan_w1 where n_symbol>=$N_SYMBOL order by rn limit 1) b where a.batched=b.max_batched and stype='$STYPE' $SCLAUSE order by round(infov) desc, marketcap desc limit $MAXROWS) a, (select @rn:=0) b"

@getUser()
@ratelimittrylogin(nlgroup="tryfamelists_famer", group="famelists_famer", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=300)
def famelist_famerscan(request, n_symbol=20, ftype="chg", max_rows=STYPE_LIST_MAX_ROWS):
    if not table_exist("ff_status_scan"):
        return JsonResponse({})
    ftype = ftype.lower()
    f = [i['ftype'] for i in STYPE_LIST]
    if ftype not in f:
        return JsonResponse({})
    e = next(i for i in STYPE_LIST if i['ftype'] == ftype)
    s = STYPE_SQL.replace("$N_SYMBOL", str(n_symbol))
    s = s.replace("$STYPE", e['stype'])
    s = s.replace("$SCLAUSE", e['sclause'])
    s = s.replace("$MAXROWS", str(max_rows))
    symbol_list = runsql(s)
    rd = {"symbol_list": symbol_list, 
          "famer_api": ftype,
          }
    return JsonResponse(rd)


@getUser()
@ratelimittrylogin(nlgroup="tryfamelists_famer", group="famelists_famer", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=1800)
def famelist_famerf66(request, d=0, n=50):
    terms = runsql("select d, term from ff_stock_w42 group by d, term order by d")
    if d and d not in [i['d'] for i in terms]:
        d = 7
    if d:
        symbol_list = runsql("select a.* from (select rn+1 rn, symbol, dp from ff_stock_w42 where d="+str(d)+" order by rn limit "+str(n)+") a order by rn")
    else:
        symbol_list = runsql("select a.* from (select * from ff_stock_w43 limit "+str(n)+") a order by rn")
    for t in terms:
        s = t['term'].split()
        t['short'] = s[0]+s[1][0]
    term = terms[ [i['d'] for i in terms].index(d) ]['term'] if d else "Fame66"
    rd = {"symbol_list":symbol_list,
          "terms": terms,
          "term":  term,
          "d": d,
          }
    return JsonResponse(rd)


@getUser()
@ratelimittrylogin(nlgroup="tryfamelists_famer", group="famelists_famer", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=1800)
def famelist_famersense(request, n=50, hard_max=100, hard_min=10):
    if not table_exist("ff_finnews_f0"):
        return JsonResponse({})
    if n > hard_max:
        n = hard_max
    if n < hard_min:
        n = hard_min
    #symbol_list = runsql("select symbol, dest_date, dense_diff from ff_finnews_f0 order by abs(dense_diff) desc limit "+str(n))
    symbol_list = runsql("select symbol, dest_date, dense_diff from ff_finnews_f0 where dest_date=(select max(dest_date) from ff_finnews_f0) order by abs(dense_diff) desc limit "+str(n))
    for i, s in enumerate(symbol_list):
        s['rn'] = i+1
    rd = {"symbol_list":symbol_list,
          }
    return JsonResponse(rd)





@getUser()
@ratelimittrylogin(nlgroup="tryfamelist_overall", group="famelist_overall", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=1800)
def famelist_overall(request, n=10):
    symbol_list = get_overall_list(request, n)
    rd = {"symbol_list":symbol_list,
          "n": n,
          }
    return JsonResponse(rd)



@getUser()
@ratelimittrylogin(nlgroup="tryfamelist_overalldetail", group="famelist_overall", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=60)
def famelist_overalldetail(request, n=10, start=1):
    if not table_exist("ff_status_scan_o4"):
        return famelist_overalldetail_(request, n)
    rows = runsql("select * from ff_status_scan_o4 where rn>=" + str(start) + " and rn<" + str(start+n))
    result_list = []
    cur_symbol = ''
    cur_dict = {}
    for row in rows:
        if row['symbol'] != cur_symbol:
            if cur_dict:
                result_list.append(cur_dict)
            cur_dict = {"rn": row['rn'], "symbol": row['symbol'], "w_micd": row['w_micd'] }
            cur_symbol = row['symbol']
        ctx = json.loads(row['context'].replace("'",'"'))
        #if row['stype'] == 'f6c':
        #    v = [dict(zip(["label","value"], m)) for m in zip(["6 months","3 months","1 month","2 weeks","1 week","2 days"], ctx)]
        #    d = {"key": cur_symbol, "values": v}
        if row['stype'] == 'f66':
            v = [dict(zip(["label","value"], m)) for m in zip(["6 months","3 months","1 month","2 weeks","1 week","2 days"], ctx['c_diff'])]
            d = {"key": cur_symbol, "values": v}
            cur_dict['f6cinfo'] = d
            v = [dict(zip(["pr","range","c_diff"], m)) for m in zip(ctx["pr"], ["6 months","3 months","1 month","2 weeks","1 week","2 days"], ctx['c_diff'])]
            d = {"bits": v}
        elif row['stype'] == 'f6w':
            d = {"labels": ["6 months","3 months","1 month","2 weeks","1 week","2 days"], "datasets": [ctx]}
        else:
            d = ctx
        cur_dict[row['stype']+'info'] = d
    result_list.append(cur_dict)

    rd = {"symbol_list": result_list,
          "n": n,
          "start": start
          }
    return JsonResponse(rd)

@getUser()
@ratelimittrylogin(nlgroup="tryfamelist_overalldetail", group="famelist_overall", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=1800)
def famelist_overalldetail_(request, n=10):
    symbol_list = get_overall_list(request, n)
    result_list = []
    for symbol in symbol_list:
        ss = symbol["symbol"]
        # do operation
        # chg
        tmp = request.path
        request.path = "/api/v1/famebits/chg/"+ss+"/"
        j = famebits_changerate(request, ss=ss, ns=0)
        R = json.loads(j.content.decode('utf-8'))
        symbol["chginfo"] = R

        #cfp
        request.path = "/api/v1/famebits/cfp/"+ss+"/"
        j = famebits_ceilfloor(request, ss=ss, ns=0)
        R = json.loads(j.content.decode('utf-8'))
        symbol["cfpinfo"] = R
        
        #vol
        request.path = "/api/v1/famebits/vol/"+ss+"/"
        j = famebits_volume(request, ss=ss, ns=0)
        R = json.loads(j.content.decode('utf-8'))
        symbol["volinfo"] = R

        #pfl
        request.path = "/api/v1/famebits/pfl/"+ss+"/"
        j = famebits_pricefluc(request, ss=ss, ns=0)
        R = json.loads(j.content.decode('utf-8'))
        symbol["pflinfo"] = R

        #f6w
        request.path = "/api/v1/fame66/w52/"+ss+"/"
        j = fame66_w52_support(request, ss=ss)
        R = json.loads(j.content.decode('utf-8'))
        symbol["f6winfo"] = R

        #f66
        request.path = "/api/v1/famebits/f66/"+ss+"/"
        j = famebits_fame66(request, ss=ss, ns=0)
        R = json.loads(j.content.decode('utf-8'))
        symbol["f66info"] = R

        #ahd
        request.path = "/api/v1/famebits/ahd/"+ss+"/"
        j = famebits_ahead(request, ss=ss, ns=0)
        R = json.loads(j.content.decode('utf-8'))
        symbol["ahdinfo"] = R
        
        request.path = tmp
        result_list.append(symbol)

    rd = {"symbol_list": result_list,
          "n": n,
          }
    return JsonResponse(rd)






@getUser()
def my_watchlist(request):
    symbol_list = get_watched_symbols(request)
    return JsonResponse({'symbols':[i['symbol'] for i in symbol_list]})


@getUser()
def my_recentlist(request, n_max=10, hard_max=100, hard_min=1):
    if n_max > hard_max:
        n_max = hard_max
    if n_max < hard_min:
        n_max = hard_min
    symbol_list = get_recent_symbols(request, n_max)
    return JsonResponse({'symbols':[i['symbol'] for i in symbol_list]})






@cache_api_internal(refresh_rate_in_seconds=1800)
def misc_SP500(request):
    return JsonResponse({'SP500_list': get_SP500()})


@cache_api_internal(refresh_rate_in_seconds=1800)
def misc_nonSP(request):
    return JsonResponse({'symbol_list': get_nonSP500()})


@getUser()
@ratelimittrylogin(nlgroup="trymobile_get_stock_info", group="mobile_stock", nlrate="5/m",rate="20/m")
def add_stock_to_history(request, ss):
    return JsonResponse({'result': 'success'})


















@getUser()
#@ratelimittrylogin(nlgroup="trycache_onebig_symbol", group="cache_onebig_symbol", nlrate="5/m",rate="20/m")
@cache_api_internal(refresh_rate_in_seconds=600)
def cache_onebig_symbol(request, ss=""):
    ss = ss.upper().replace('-','.')
    cache_IEX(ss)
    if not ss in IEX_cache:
        return JsonResponse({})

    rd = {"symbol":ss}

    # do operation
    # chg
    tmp = request.path
    request.path = "/api/v1/famebits/chg/"+ss+"/"
    j = famebits_changerate(request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    rd["chginfo"] = R

    #cfp
    request.path = "/api/v1/famebits/cfp/"+ss+"/"
    j = famebits_ceilfloor(request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    rd["cfpinfo"] = R
    
    #vol
    request.path = "/api/v1/famebits/vol/"+ss+"/"
    j = famebits_volume(request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    rd["volinfo"] = R

    #pfl
    request.path = "/api/v1/famebits/pfl/"+ss+"/"
    j = famebits_pricefluc(request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    rd["pflinfo"] = R

    #f6w
    request.path = "/api/v1/fame66/w52/"+ss+"/"
    j = fame66_w52_support(request, ss=ss)
    R = json.loads(j.content.decode('utf-8'))
    rd["f6winfo"] = R

    #f66
    request.path = "/api/v1/famebits/f66/"+ss+"/"
    j = famebits_fame66(request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    rd["f66info"] = R

    #ahd
    request.path = "/api/v1/famebits/ahd/"+ss+"/"
    j = famebits_ahead(request, ss=ss, ns=0)
    R = json.loads(j.content.decode('utf-8'))
    rd["ahdinfo"] = R

    request.path = tmp

    return JsonResponse(rd)


