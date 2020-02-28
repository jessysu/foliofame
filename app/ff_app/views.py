
import re, datetime, time, random
from copy import deepcopy
from dateutil.relativedelta import relativedelta
from django.db import connection
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.validators import URLValidator
from ratelimit.decorators import ratelimit, ratelimittrylogin

from ff_app.defs import BLOCKED_STOCKS
from ff_app.utils import runsql, table_exist, get_SP500
from ff_app.api_cache import cache_api_internal

from ff_logging.views import (
    log_ff_external_clicks,
    log_bestever_session,
    log_hindsight_request)




def get_rank(r):
    R = list("ABCDE")
    S = ['+','','-']
    q = r // 20
    if q > 14:
        o = "F"
    else:
        o = R[int(q // 3)] + S[int(q % 3)]
    return o


def assure_session(request):
    if not request.session.exists(request.session._session_key):
        request.session.create()
        # use cookieconsent.js in base.html instead
        #messages.warning(request, 'We use cookies to distinguish you from other users of the site. By continue using the site, you agree to our <a href="/about/">terms of service</a>.')
    return


def is_watching(request, ss):
    assure_session(request)
    sk = request.session._session_key
    if len(sk)>30 and len(sk)<=40:
        uid =  request.user.id if request.user.is_authenticated else 0

    watching = 0
    if request.user.is_authenticated:
        a = runsql("select action from ff_app_watchlist where uid="+str(uid)+" and symbol='"+ss+"' order by request_dt desc limit 1")
        if a:
            if a[0]['action'] == 'add':
                watching = 1
    return watching




def generate_ranged_query():
    cdt = datetime.datetime.now() - datetime.timedelta(hours=22)
    rq = []
    rq.append({"term": "3 years", "link":"/hsm/?ds="+(cdt-relativedelta(years=3)).strftime("%m/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "2 years", "link":"/hsm/?ds="+(cdt-relativedelta(years=2)).strftime("%m/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "1 year", "link":"/hsm/?ds="+(cdt-relativedelta(years=1)).strftime("%m/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "6 months", "link":"/hsd/?ds="+(cdt-relativedelta(months=6)).strftime("%m/%d/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%d/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "3 months", "link":"/hsd/?ds="+(cdt-relativedelta(months=3)).strftime("%m/%d/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%d/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "1 month", "link":"/hsd/?ds="+(cdt-relativedelta(months=1)).strftime("%m/%d/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%d/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "2 weeks", "link":"/hsd/?ds="+(cdt-relativedelta(days=14)).strftime("%m/%d/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%d/%Y&ss=").replace("/","%2F")})
    rq.append({"term": "1 week", "link":"/hsd/?ds="+(cdt-relativedelta(days=7)).strftime("%m/%d/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%d/%Y&ss=").replace("/","%2F")})
    return rq[::-1]

def generate_ytd_query():
    cdt = datetime.datetime.now() - datetime.timedelta(hours=22)
    return {"term_long":"year-to-date", "term_short":"YTD", "link":"/hsd/?ds="+cdt.strftime("01/01/%Y&de=").replace("/","%2F")+cdt.strftime("%m/%d/%Y&ss=").replace("/","%2F")}


@cache_api_internal(refresh_rate_in_seconds=60)
def get_overall_list(request, n=10, time_factor=2, rand_scale=10, mature_hour=15, minimal_scan_symbols=20):
    statuses = []
    if table_exist("ff_status_scan") and table_exist("ff_status_scan_w1"):
        # deterministic news value
        rawsql = "select symbol, stype, rarity, context, infov, w_mic from (select a.*, @rn:=if(@s=symbol,@rn+1,0) rn, @s:=symbol s from (select a.symbol, marketCap, updated, scanned, stype, rarity, context, infov, (log10(marketCap)-9)*(infov-90)*(log10(abs(changePct*10000))) w_mic from ff_status_scan a, ff_status_scan_w1 b where a.batched=b.max_batched order by w_mic desc limit "+str(n*3)+") a, (select @s:='',@rn:=0) b order by marketCap desc, w_mic desc) a where rn=0 order by w_mic desc limit "+str(n)
        # with news aging
        rawsql = "select symbol, stype, infov, w_micd from \
                  (select a.*, td+w_mic*md w_micd, @rn:=if(@s=symbol,@rn+1,0) rn, @s:=symbol s from \
                  (select a.symbol, marketCap, updated, scanned, stype, rarity, context, infov, if(stype='vol',if(md>1,1,md),1) md, if(td>"+str(time_factor)+","+str(time_factor)+",td)*rand()*"+str(rand_scale)+" td, (log10(marketCap)-9)*(infov-90)*(log10(abs(changePct*10000))) w_mic from \
                    (select a.*, (hour(updated)*60+minute(updated))/"+str(mature_hour*60)+" md, if(timestampdiff(minute,batched,utc_timestamp())<200,0,(timestampdiff(minute,batched,utc_timestamp())-200)/480) td from ff_status_scan a) a, \
                      (select batched as max_batched from ff_status_scan_w1 where n_symbol>="+str(minimal_scan_symbols)+" order by rn limit 1) b where a.batched=b.max_batched order by w_mic desc limit "+str(n*3)+") a, \
                    (select @s:='',@rn:=0) b order by marketCap desc, w_micd desc \
                  ) a where rn=0 order by w_micd desc limit "+str(n+len(BLOCKED_STOCKS))
        try:
            statuses = runsql(rawsql)
            statuses = [s for s in statuses if s['symbol'] not in BLOCKED_STOCKS]
            statuses = statuses[:n]
            counter  = 0
            for s in statuses:
                counter += 1
                s['rn'] = counter
        except Exception as e:
            statuses = []
    return statuses





def redirect_external(request):
    s = request.GET.get("s", "") # symbol
    v = request.GET.get("v", "") # view
    t = request.GET.get("t", "") # url type
    u = request.GET.get("u", "") # url
    validate = URLValidator()
    try:
        validate(u)
        # assure_log()
        assure_session(request)
        log_ff_external_clicks(request, s, v, t, u)
    except Exception as e:
        pass
    return redirect(u)


def error_404(request):
    data = {}
    return render(request, '404.html', data)


def index(request):
    assure_session(request)
    is_text = True
    if request.user.is_authenticated and table_exist("ff_app_userpref"):
        q = runsql("select * from ff_app_userpref where uid = "+str(request.user.id)+" and pref = 'home_block'")
        if len(q):
            is_text = q[0]['choice']=='txt'
    return render(request, 'home.html', {"SP500": get_SP500(), "is_text": is_text})


@ratelimittrylogin(nlgroup="tryfamelist", group="famelist", nlrate="7/m",rate="20/m")
def famelist(request, ss="", d=0, n=50, page_size=5):
    if not request.user.is_authenticated:
        messages.warning(request, 'Events and tips are disabled for non-<a href="/accounts/login/?next='+request.path+'">login</a> users.')
    terms = runsql("select d, term from ff_stock_w42 group by d, term order by d")
    if d and d not in [i['d'] for i in terms]:
        return redirect("/fl/")
    if not request.user.is_authenticated:
        if d:
            symbol_list = runsql("select a.*, b.security, b.sector from (select rn+1 rn, symbol, dp from ff_stock_w42 where d="+str(d)+" order by rn limit "+str(n)+") a, ff_scan_symbols b where a.symbol=b.symbol order by rn")
        else:
            symbol_list = runsql("select a.*, b.security, b.sector from (select * from ff_stock_w43 limit "+str(n)+") a, ff_scan_symbols b where a.symbol=b.symbol order by rn")
    else:
        if d:
            symbol_list = runsql("select a.*, b.security, b.sector, if(c.symbol is null,0,1) watching from (select rn+1 rn, symbol, dp from ff_stock_w42 where d="+str(d)+" order by rn limit "+str(n)+") a inner join \
                                  ff_scan_symbols b on a.symbol=b.symbol left join \
                                  (select a.symbol, request_dt from ff_app_watchlist a, (select symbol, max(request_dt) mrdt from ff_app_watchlist where uid="+str(request.user.id)+" group by symbol) b \
                                    where a.uid="+str(request.user.id)+" and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add') \
                                  c on a.symbol=c.symbol order by rn")
        else:
            symbol_list = runsql("select a.*, b.security, b.sector, if(c.symbol is null,0,1) watching from (select * from ff_stock_w43 limit "+str(n)+") a inner join \
                                  ff_scan_symbols b on a.symbol=b.symbol left join \
                                  (select a.symbol, request_dt from ff_app_watchlist a, (select symbol, max(request_dt) mrdt from ff_app_watchlist where uid="+str(request.user.id)+" group by symbol) b \
                                    where a.uid="+str(request.user.id)+" and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add') \
                                  c on a.symbol=c.symbol order by rn")
    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
        r['bid'] = int((r['rn']-1) / page_size)
    for t in terms:
        s = t['term'].split()
        t['short'] = s[0]+s[1][0]
    term = terms[ [i['d'] for i in terms].index(d) ]['term'] if d else "Fame66"
    rs = {"symbol_list":symbol_list, "terms": terms, "term":  term, "d": d,
          "SP500": get_SP500(), "max_bid": int((n-1)/page_size)}
    return render(request, 'famelist.html', rs)

#@ratelimittrylogin(nlgroup="tryabout", group="about", nlrate="2/m",rate="100/m", redirecturl="/about/")
def about(request):
    return render(request, 'about.html', {})


    
def hindsight_monthly(request, ds="", de="", ss="", maxyear=5):
    to_be_redir = False
    if not ds:
        ds = request.GET.get('ds', '')
    if not de:
        de = request.GET.get('de', '')
    if not ss:
        ss = request.GET.get('ss', '').upper()
    maxD = datetime.datetime.now() - datetime.timedelta(hours=22)
    if maxD.weekday()>4:
        maxD -= datetime.timedelta(days=1)
        if maxD.weekday()>4:
            maxD -= datetime.timedelta(days=1)
    hard_min = datetime.datetime.now() - relativedelta(years=maxyear)
    SminD = hard_min.strftime("%m/%Y")
    EmaxD = maxD.strftime("%m/%Y")

    r = re.compile('\d{2}/\d{4}')
    if not ds or not r.match(ds) or len(ds)!=7:
        to_be_redir = True
        random_years = random.choice(list(range(1,6)))
        ds = (datetime.datetime.now() - relativedelta(years=random_years)).strftime("%m/%Y")
        messages.warning(request, 'Showing the top stock symbols during the last <strong>'+str(random_years)+'</strong> years.')
    if not de or not r.match(de) or len(de)!=7:
        to_be_redir = True
        messages.warning(request, 'Not a valid end date - reset end date to last trading day')
        de = maxD.strftime("%m/%Y")
    if not to_be_redir:
        if datetime.datetime.strptime(de,"%m/%Y") > maxD :
            to_be_redir = True
            de = maxD.strftime("%m/%Y")
            messages.warning(request, 'Showing the top stocks up to current time only.')
        if datetime.datetime.strptime(ds,"%m/%Y") < datetime.datetime.strptime(hard_min.strftime("%m/%Y"),"%m/%Y") :
            to_be_redir = True
            ds = hard_min.strftime("%m/%Y")
            messages.warning(request, 'Showing the top stock symbols during the last <strong>'+str(maxyear)+'</strong> years only.')
        while not runsql("select count(1) cnt from ff_stock_w2 where close_month='"+(datetime.datetime.strptime(de,"%m/%Y")).strftime("%Y%m")+"'")[0]['cnt']:
            to_be_redir = True
            de = (datetime.datetime.strptime(de,"%m/%Y") - relativedelta(months=1)).strftime("%m/%Y")
        if datetime.datetime.strptime(ds,"%m/%Y") >= datetime.datetime.strptime(de,"%m/%Y"):
            to_be_redir = True
            ds = (datetime.datetime.strptime(de,"%m/%Y") - relativedelta(months=1)).strftime("%m/%Y")
    if len(ss) > 5 or ss not in get_SP500():
        to_be_redir = True
        ss = ""
    if to_be_redir:
        return redirect("/hsm/?ds="+ds.replace("/","%2F")+"&de="+de.replace("/","%2F")+"&ss="+ss)
    EminD = ds
    SmaxD = de
    _ds = ds.replace('/','')
    _ds = _ds[2:] + _ds[:2]
    _de = de.replace('/','')
    _de = _de[2:] + _de[:2]
    es = datetime.datetime.strptime(ds,"%m/%Y")
    ee = datetime.datetime.strptime(de,"%m/%Y")
    sy = es.year == ee.year

    assure_session(request)
    log_hindsight_request(request, ld="/hsm/", ds=es, de=ee, ss=ss)

    if not request.user.is_authenticated:
        rawsql = "select a.*, security, sector, c.close l_close, c.d l_diff, c.dp l_dp from ( \
                  select a.* from (select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w3 where start_month='"+_ds+"' and end_month='"+_de+"' order by rn limit 10) a \
                  union \
                  select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w3 where start_month='"+_ds+"' and end_month='"+_de+"' and symbol='"+ss+"' \
                  ) a inner join ff_scan_symbols b on a.symbol=b.symbol left join ff_stock_w41 c on a.symbol=c.symbol order by rn"
    else:
        rawsql = "select a.*, security, sector, c.close l_close, c.d l_diff, c.dp l_dp, if(d.symbol is null,0,1) watching from ( \
                  select a.* from (select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w3 where start_month='"+_ds+"' and end_month='"+_de+"' order by rn limit 10) a \
                  union \
                  select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w3 where start_month='"+_ds+"' and end_month='"+_de+"' and symbol='"+ss+"' \
                  ) a inner join ff_scan_symbols b on a.symbol=b.symbol left join ff_stock_w41 c on a.symbol=c.symbol left join \
                  (select a.symbol, request_dt from ff_app_watchlist a, (select symbol, max(request_dt) mrdt from ff_app_watchlist where uid="+str(request.user.id)+" group by symbol) b \
                    where a.uid="+str(request.user.id)+" and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add') \
                  d on a.symbol=d.symbol order by rn"
    symbol_list = runsql(rawsql)
    pr = ""
    for i in symbol_list:
        i['sym_id'] = i['symbol'].replace('.','-')
        if i['symbol'] == ss:
            pr = get_rank(i['rn'])
    rawsql = "select a.*, c_min, round((close-c_min)/c_min*100,2) gp, rn from ff_stock a, ff_stock_w2 c, \
              (select a.* from (select rn, symbol from ff_stock_w3 where start_month='"+_ds+"' and end_month='"+_de+"' order by rn limit 10) a union \
              select rn, symbol from ff_stock_w3 where start_month='"+_ds+"' and end_month='"+_de+"' and symbol='"+ss+"' \
              ) b where a.symbol=b.symbol and DATE_FORMAT(a.close_date, '%Y%m') >= '"+_ds+"' and DATE_FORMAT(a.close_date, '%Y%m') <= '"+_de+"' \
              and b.symbol=c.symbol and c.close_month = '"+_ds+"' and mod(day(close_date),5)=1"
    symbol_line = runsql(rawsql)
    for s in symbol_line:
        s['close_date'] = 1000*time.mktime(s['close_date'].timetuple())
    rs = {"SminD": SminD, "EminD": EminD, "SmaxD": SmaxD, "EmaxD": EmaxD,
          "es": es, "ee": ee, "sy": sy,
          "ds": ds, "de": de, "ss": ss, 
          "symbol_list": symbol_list, "symbol_line": symbol_line, 
          "pr": pr, "SP500": get_SP500(), "rq": generate_ranged_query(), "ytd": generate_ytd_query()
          }
    return render(request, 'hindsight_monthly.html', rs)
    



def hindsight_daily(request, ds="", de="", ss=""):
    to_be_redir = False
    if not ds:
        ds = request.GET.get('ds', '')
    if not de:
        de = request.GET.get('de', '')
    if not ss:
        ss = request.GET.get('ss', '').upper()
    maxD = datetime.datetime.now() - datetime.timedelta(hours=22)
    if maxD.weekday()>4:
        maxD -= datetime.timedelta(days=1)
        if maxD.weekday()>4:
            maxD -= datetime.timedelta(days=1)
    minD = datetime.datetime.now()-datetime.timedelta(days=180)
    if minD.weekday()>4:
        minD += datetime.timedelta(days=1)
        if minD.weekday()>4:
            minD += datetime.timedelta(days=1)
    hard_min = datetime.datetime.now() - relativedelta(months=7)
    hard_max = datetime.datetime.now() - relativedelta(months=6)
    SminD = minD.strftime("%m/%d/%Y")
    EminD = minD.strftime("%m/%d/%Y")
    SmaxD = maxD.strftime("%m/%d/%Y")
    EmaxD = maxD.strftime("%m/%d/%Y")
    
    r = re.compile('\d{2}/\d{2}/\d{4}')
    if not de or not r.match(de) or len(de)!=10:
        to_be_redir = True
        de = maxD.strftime("%m/%d/%Y")
    if not ds or not r.match(ds) or len(ds)!=10:
        to_be_redir = True
        daydiff = ((datetime.datetime.now()- datetime.timedelta(hours=19)) - datetime.datetime.strptime(de,"%m/%d/%Y")).days
        choices = [i for i in [7,14,21,30,60,90,120,180,210] if i>=daydiff]
        random_days = random.choice(choices)
        ds = (datetime.datetime.now() - relativedelta(days=random_days)).strftime("%m/%d/%Y")
    if not to_be_redir:
        if datetime.datetime.strptime(de,"%m/%d/%Y") < hard_max :
            to_be_redir = True
            de = hard_max.strftime("%m/%d/%Y")
            messages.warning(request, 'The end date needs to be within the last <strong>6</strong> months. Fixed.')
        if datetime.datetime.strptime(de,"%m/%d/%Y") > maxD :
            to_be_redir = True
            de = maxD.strftime("%m/%d/%Y")
            messages.warning(request, 'Showing the top stocks up to current time only.')
        if datetime.datetime.strptime(ds,"%m/%d/%Y") < hard_min :
            ds = (datetime.datetime.strptime(ds,"%m/%d/%Y")).strftime("%m/%Y")
            de = (datetime.datetime.strptime(de,"%m/%d/%Y")).strftime("%m/%Y")
            messages.warning(request, 'Changed to monthly resolution for period longer than 6 months.')
            return redirect("/hsm/?ds="+ds.replace("/","%2F")+"&de="+de.replace("/","%2F")+"&ss="+ss)
        while not runsql("select count(1) cnt from ff_stock_w4 where close_date='"+(datetime.datetime.strptime(de,"%m/%d/%Y")).strftime("%Y-%m-%d")+"'")[0]['cnt']:
            to_be_redir = True
            de = (datetime.datetime.strptime(de,"%m/%d/%Y") - relativedelta(days=1)).strftime("%m/%d/%Y")
        if datetime.datetime.strptime(ds,"%m/%d/%Y") > datetime.datetime.strptime(de,"%m/%d/%Y"):
            to_be_redir = True
            ds = de
        while not runsql("select count(1) cnt from ff_stock_w4 where close_date='"+(datetime.datetime.strptime(ds,"%m/%d/%Y")).strftime("%Y-%m-%d")+"'")[0]['cnt']:
            to_be_redir = True
            ds = (datetime.datetime.strptime(ds,"%m/%d/%Y") + relativedelta(days=1)).strftime("%m/%d/%Y")
    if len(ss) > 5 or ss not in get_SP500():
        to_be_redir = True
        ss = ""
    if to_be_redir:
        return redirect("/hsd/?ds="+ds.replace("/","%2F")+"&de="+de.replace("/","%2F")+"&ss="+ss)
    EminD = ds
    SmaxD = de
    _ds = ds.replace('/','-')
    _ds = _ds[6:] + "-" + _ds[:5]
    _de = de.replace('/','-')
    _de = _de[6:] + "-" + _de[:5]
    es = datetime.datetime.strptime(ds,"%m/%d/%Y")
    ee = datetime.datetime.strptime(de,"%m/%d/%Y")
    sy = es.year == ee.year
    
    _ds = str(runsql("select max(close_date) ds from ff_stock_w40 where close_date<'"+_ds+"'")[0]['ds'])

    assure_session(request)
    log_hindsight_request(request, ld="/hsd/", ds=datetime.datetime.strptime(ds,"%m/%d/%Y"), de=datetime.datetime.strptime(de,"%m/%d/%Y"), ss=ss)

    if not request.user.is_authenticated:
        rawsql = "select a.*, security, sector, c.close l_close, c.d l_diff, c.dp l_dp from ( \
                  select a.* from (select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w5 where start_date='"+_ds+"' and end_date='"+_de+"' order by rn limit 10) a \
                  union \
                  select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w5 where start_date='"+_ds+"' and end_date='"+_de+"' and symbol='"+ss+"' \
                  ) a inner join ff_scan_symbols b on a.symbol=b.symbol left join ff_stock_w41 c on a.symbol=c.symbol order by rn"
    else:
        rawsql = "select a.*, security, sector, c.close l_close, c.d l_diff, c.dp l_dp, if(d.symbol is null,0,1) watching from ( \
                  select a.* from (select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w5 where start_date='"+_ds+"' and end_date='"+_de+"' order by rn limit 10) a \
                  union \
                  select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w5 where start_date='"+_ds+"' and end_date='"+_de+"' and symbol='"+ss+"' \
                  ) a inner join ff_scan_symbols b on a.symbol=b.symbol left join ff_stock_w41 c on a.symbol=c.symbol left join \
                  (select a.symbol, request_dt from ff_app_watchlist a, (select symbol, max(request_dt) mrdt from ff_app_watchlist where uid="+str(request.user.id)+" group by symbol) b \
                    where a.uid="+str(request.user.id)+" and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add') \
                  d on a.symbol=d.symbol order by rn"
    symbol_list = runsql(rawsql)
    pr = ""
    for i in symbol_list:
        i['sym_id'] = i['symbol'].replace('.','-')
        if i['symbol'] == ss:
            pr = get_rank(i['rn'])
    rawsql = "select a.*, round((a.close-c.low)/c.low*100,2) gp, rn from ff_stock a use index (ff_stock_i1), ff_stock_w4 c, \
              (select a.* from (select rn, symbol from ff_stock_w5 where start_date='"+_ds+"' and end_date='"+_de+"' order by rn limit 10) a union \
              select rn, symbol from ff_stock_w5 where start_date='"+_ds+"' and end_date='"+_de+"' and symbol='"+ss+"' \
              ) b where a.symbol=b.symbol and a.close_date >= '"+_ds+"' and a.close_date <= '"+_de+"' \
              and b.symbol=c.symbol and c.close_date = '"+_ds+"'"
    symbol_line = runsql(rawsql)
    for s in symbol_line:
        s['close_date'] = 1000*time.mktime(s['close_date'].timetuple())
    rs = {"SminD":SminD, "EminD":EminD, "SmaxD":SmaxD, "EmaxD":EmaxD,
          "ds": ds, "de": de, "ss": ss,
          "es": es, "ee": ee, "sy": sy,
          "symbol_list": symbol_list, "symbol_line": symbol_line, 
          "pr":pr, "SP500":get_SP500(), "rq": generate_ranged_query(), "ytd": generate_ytd_query()
          }
    return render(request, 'hindsight_daily.html', rs)



def bestever(request, ss="", d="180", lastn="11"):
    if not ss or len(ss)>5:
        if len(ss)>5:
            messages.warning(request, 'Invalid stock symbol.')
        try:
            raw_sql = "select symbol from ff_stock_w43 where rn<20 order by rand() limit 1"
            ss = runsql(raw_sql)[0]['symbol']
            messages.warning(request, 'Showing one of the top performing stock recently: <b>'+ss+'</b>')
            return redirect("/be/"+ss+"/30/")
        except:
            messages.warning(request, 'Bestever cannot find any good performing stock recently.')
            return redirect("/")
    ss = ss.upper()
    
    if d.isdigit():
        d = int(d)
        if d > 365:
            messages.warning(request, 'Only showing quotes for up to the past 365 days.')
            return redirect("/be/"+ss+"/365/")
        if d <= 0:
            d = 1
    else:
        d = 180
    cdt = datetime.datetime.now() - datetime.timedelta(hours=19)
    ds = runsql("select max(close_date) ds from ff_stock_w40 a, (select max(close_date) m from ff_stock_w40) b where datediff(b.m,a.close_date)>="+str(d))[0]['ds']
    de = runsql("select max(close_date) de from ff_stock_w40")[0]['de']
    rawsql = "select close_date, high, low, close, volume from ff_stock where symbol='"+ss+"' and close_date>'"+ds.strftime("%Y-%m-%d")+"'"
    symbol_line = runsql(rawsql)
    if len(symbol_line) == 0:
        messages.warning(request, 'No data for the stock symbol <b>'+ss+'</b>')
        return redirect("/be/")
    while not runsql("select count(1) cnt from ff_stock_w4 where close_date='"+ds.strftime("%Y-%m-%d")+"'")[0]['cnt']:
        ds += relativedelta(days=1)
    while not runsql("select count(1) cnt from ff_stock_w4 where close_date='"+de.strftime("%Y-%m-%d")+"'")[0]['cnt']:
        de -= relativedelta(days=1)
    for s in symbol_line:
        s['close_date'] = 1000*time.mktime(s['close_date'].timetuple())

    if d < 210:
        rawsql = "select a.*, security, sector, subsec, hq, c.close l_close, c.d l_diff, c.dp l_dp from ( \
                  select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w5 where start_date='"+ds.strftime("%Y-%m-%d")+"' and end_date='"+de.strftime("%Y-%m-%d")+"' and symbol='"+ss+"' \
                  ) a inner join ff_scan_symbols b on a.symbol=b.symbol left join ff_stock_w41 c on a.symbol=c.symbol order by rn"
    else:
        rawsql = "select a.*, security, sector, subsec, hq, c.close l_close, c.d l_diff, c.dp l_dp from ( \
                  select rn+1 rn, symbol, round(c_diff*100,2) c_diff from ff_stock_w3 where start_month='"+ds.strftime("%Y%m")+"' and end_month='"+de.strftime("%Y%m")+"' and symbol='"+ss+"' \
                  ) a inner join ff_scan_symbols b on a.symbol=b.symbol left join ff_stock_w41 c on a.symbol=c.symbol order by rn"
    symbol_desc = runsql(rawsql)
    if len(symbol_desc) == 0:
        return redirect("/be/")
    symbol_desc = symbol_desc[0]
    symbol_desc['pr'] = get_rank(symbol_desc['rn'])

    assure_session(request)
    log_bestever_session(request, ss=ss, d=d)

    symbol_best = runsql("select * from ff_stock_best where symbol='"+ss+"'")
    best_terms = []
    for s in symbol_best:
        if s['rg'][:2] in [b['rg'][:2] for b in best_terms]:
            continue
        i = re.split('(\D+)',s['rg'])
        s['base_val'] = int(i[0])
        s['base_unit'] = i[1]
        s['best_val'] = int(i[2])
        s['best_unit'] = i[3]
        s['pr'] = get_rank(s['rn'])
        s['same_year'] = s['start'].year == s['end'].year
        if i[3] == 'm':
            s['url'] = '/hsm/?ds='+s['start'].strftime("%m/%Y").replace("/","%2F")+"&de="+s['end'].strftime("%m/%Y").replace("/","%2F")+"&ss="+ss
            s['url_range'] = '/hsm/?ds='+(cdt-relativedelta(years=s['base_val'])).strftime("%m/%Y").replace("/","%2F")+"&de="+cdt.strftime("%m/%Y").replace("/","%2F")+"&ss="+ss
        else:
            s['url'] = '/hsd/?ds='+s['start'].strftime("%m/%d/%Y").replace("/","%2F")+"&de="+s['end'].strftime("%m/%d/%Y").replace("/","%2F")+"&ss="+ss
            s['url_range'] = '/hsm/?ds='+(cdt-relativedelta(months=s['base_val'])).strftime("%m/%Y").replace("/","%2F")+"&de="+cdt.strftime("%m/%Y").replace("/","%2F")+"&ss="+ss
        s['c_diff'] = int(100*s['c_diff'])
        best_terms.append(s)
    symbol_terms = runsql("select term, d, df, dp, rn from ff_stock_w42 where symbol='"+ss+"' order by d")
    for s in symbol_terms:
        s['rn'] = get_rank(s['rn'])
    symbol_smry = runsql("select * from ff_stock_w43 where symbol='"+ss+"'")[0]

    # previous viewed symbols
    sk = request.session._session_key
    if len(sk)>30 and len(sk)<=40:
        uid =  request.user.id if request.user.is_authenticated else 0
        # rawsql = "select a.symbol, a.d from ff_logging_besteversessionlog a, \
        #           (select symbol, max(request_dt) mdt from ff_logging_besteversessionlog where session_key='"+sk+"' group by symbol) b \
        #           where a.session_key='"+sk+"' and a.symbol=b.symbol and a.request_dt=b.mdt order by request_dt desc limit "+lastn
        rawsql = "select a.symbol, a.d from ff_logging_besteversessionlog a, \
                  (select symbol, max(request_dt) mdt from ff_logging_besteversessionlog where session_key='"+sk+"' or uid='"+str(uid)+"' group by symbol) b \
                  where (a.session_key='"+sk+"' or a.uid='"+str(uid)+"') and a.symbol=b.symbol and a.request_dt=b.mdt order by request_dt desc limit "+lastn

        last_ss = runsql(rawsql)
        last_ss = last_ss[1:]
        for i in last_ss:
            i['sym_id'] = i['symbol'].replace('.','-')
    else:
        last_ss = []
    watching = 0
    if request.user.is_authenticated:
        a = runsql("select action from ff_app_watchlist where uid="+str(uid)+" and symbol='"+ss+"' order by request_dt desc limit 1")
        if a:
            if a[0]['action'] == 'add':
                watching = 1
    
    # volume
    rawsql = "select volume, avg_volume, std_volume, z_volume, minmin_z, maxmax_z, bin from ff_stock_vol_w8 where symbol = '"+ss+"'"
    vol_context = runsql(rawsql)[0]
    rawsql = "select * from ff_stock_vol_w4"
    vol_bins = runsql(rawsql)
    
    rd = {'d': d, "ds": ds, "de": de, 'ss': ss, 
          'symbol_desc': symbol_desc, 'symbol_line': symbol_line, 
          'symbol_terms': symbol_terms, 'symbol_smry': symbol_smry, 
          'best_terms': best_terms, "SP500": get_SP500(), "last_ss": last_ss, "watching": watching,
          'vol_context': vol_context, 'vol_bins': vol_bins
         }
    return render(request, 'symbol_landing.html', rd)

