
from django.shortcuts import render, redirect
from django.contrib import messages

from ff_app.utils import runsql, table_exist, get_SP500
from ff_app.defs import STYPE_LIST, STYPE_LIST_MAX_ROWS
from ff_app.views_my import get_watched_symbols
from ratelimit.decorators import ratelimittrylogin

STYPE_SQL = "select @rn:=@rn+1 rn, a.* from (select a.symbol, a.marketcap, a.updated, round(a.infov) infov from ff_status_scan a, (select batched as max_batched from ff_status_scan_w1 where n_symbol>=$N_SYMBOL order by rn limit 1) b where a.batched=b.max_batched and stype='$STYPE' $SCLAUSE order by round(infov) desc, abs(changePct) desc limit $MAXROWS) a, (select @rn:=0) b"
AHEAD_SQL = "select @rn:=@rn+1 rn, a.* from (select symbol, marketcap, round(infov) infov from ff_status_scan_o4 where stype='ahd' and infov>50 order by infov desc, marketcap desc limit $MAXROWS) a, (select @rn:=0) b"
@ratelimittrylogin(nlgroup="tryfamer", group="famer", nlrate="7/m",rate="20/m")
def famer_scan(request, n_symbol=20, page_size=5, ftype="ahd", max_rows=STYPE_LIST_MAX_ROWS):
    if not table_exist("ff_status_scan"):
        return redirect("/")
    ftype = ftype.lower()
    f = [i['ftype'] for i in STYPE_LIST]
    if ftype not in f:
        return redirect("/fmr/")
    e = next(i for i in STYPE_LIST if i['ftype'] == ftype)
    if e['stype'] == 'ahd':
        if not table_exist("ff_status_scan_o4"):
            return redirect("/")
        s = AHEAD_SQL.replace("$MAXROWS", str(max_rows))
    else:
        s = STYPE_SQL.replace("$N_SYMBOL", str(n_symbol))
        s = s.replace("$STYPE", e['stype'])
        s = s.replace("$SCLAUSE", e['sclause'])
        s = s.replace("$MAXROWS", str(max_rows))
    symbol_list = runsql(s)
    W = [i['symbol'] for i in get_watched_symbols(request)]
    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
        r['bid'] = int((r['rn']-1) / page_size)
        r['w'] = r['symbol'] in W
    rd = {"symbol_list": symbol_list, 
          "ftype": ftype,
          "stype": e['stype'],
          "url_stype": ('dme' if e['stype']=='cfp' else e['stype']),
          "ftype_name": e['name'],
          "ftype_desc": e['desc'],
          "STYPE_LIST": STYPE_LIST,
          "SP500": get_SP500(),
          "max_bid": int((len(symbol_list)-1)/page_size)
          }
    return render(request, 'famers/famers_list.html', rd)



@ratelimittrylogin(nlgroup="tryfamer", group="famer", nlrate="7/m",rate="20/m")
def fame66list(request, ss="", d=0, n=50, page_size=5):
    #if not request.user.is_authenticated:
    #    messages.warning(request, 'Events and tips are disabled for non-<a href="/accounts/login/?next='+request.path+'">login</a> users.')
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
    W = [i['symbol'] for i in get_watched_symbols(request)]
    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
        r['bid'] = int((r['rn']-1) / page_size)
        r['w'] = r['symbol'] in W
    for t in terms:
        s = t['term'].split()
        t['short'] = s[0]+s[1][0]
    term = terms[ [i['d'] for i in terms].index(d) ]['term'] if d else "Fame66"
    rs = {"symbol_list":symbol_list,
          "terms": terms,
          "term":  term,
          "d": d,
          "SP500": get_SP500(),
          "STYPE_LIST": STYPE_LIST,
          "ftype": 'f66',
          "max_bid": int((n-1)/page_size)
          }
    return render(request, 'famers/famers_f66.html', rs)

