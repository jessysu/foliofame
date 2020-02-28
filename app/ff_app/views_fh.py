from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse

from ff_app.views import assure_session
from ff_app.utils import runsql, table_exist, get_SP500, human_format, assure_ss
from ff_app.apis import cache_IEX, get_cache_IEX, get_rarity_quantifier_single, get_rarity_descriptor_single
from ff_app.views_my import get_recent_symbols

from ratelimit.decorators import ratelimittrylogin


"""
def get_lastss(request, lastn="6"):
    sk = request.session._session_key
    if len(sk)>30 and len(sk)<=40:
        uid =  request.user.id if request.user.is_authenticated else 0
        rawsql = "select a.symbol, a.d from ff_logging_besteversessionlog a, \
                  (select symbol, max(request_dt) mdt from ff_logging_besteversessionlog where session_key='"+sk+"' or uid='"+str(uid)+"' group by symbol) b \
                  where (a.session_key='"+sk+"' or a.uid='"+str(uid)+"') and a.symbol=b.symbol and a.request_dt=b.mdt order by request_dt desc limit "+lastn
        last_ss = runsql(rawsql)
        last_ss = last_ss[1:]
        for i in last_ss:
            i['symbol'] = i['symbol'].upper().replace('-','.')
            i['sym_id'] = i['symbol'].replace('.','-')
    else:
        last_ss = []
    return last_ss
"""
def get_lastss(request, n_max=6):
    last_ss = get_recent_symbols(request, n_max=n_max)
    for i in last_ss:
        i['symbol'] = i['symbol'].upper().replace('-','.')
        i['sym_id'] = i['symbol'].replace('.','-')
    if last_ss:
        last_ss = last_ss[1:]
    return last_ss


@ratelimittrylogin(nlgroup="tryfh_sector", group="fh_sector", nlrate="2/m",rate="10/m")
def fh_sector(request, return_json=False):
    if not table_exist("ff_status_scan_w6"):
        return redirect("/")
    sec_list = runsql("select * from ff_status_scan_w6 order by marketchgPct desc")
    sense_list = []
    if table_exist("ff_finnews_f1"):
        sense_list = runsql("select sector, count(1) n, sum(if(dense_diff>=0,1,0)) n_u, sum(if(dense_diff<0,1,0)) n_d, round(sum(dense_sense*marketcap)/sum(marketcap),2) sector_sense, round(sum(dense_diff*marketcap)/sum(marketcap),2) sense_drift from ff_finnews_f1 a, (select max(dest_date) max_dest_date from ff_finnews_f1) b where a.dest_date=b.max_dest_date group by sector")

    for r in sec_list:
        r['worth'] = "$" + human_format(r['sm'])
        r['change'] = ("-" if r['cm']<0 else "+") + "$" + human_format(abs(r['cm']))
        r['netmove'] = "$" + human_format(r['am'])
        r['netmovepct'] = round(r['am']/r['sm']*100,2)
        e = next((i for i in sense_list if i['sector'] == r['sector']), None)
        r['sense_up'] = e['n_u'] if e else None
        r['sense_down'] = e['n_d'] if e else None
        r['sense_drift'] = e['sense_drift'] if e else None
        r['sector_sense'] = e['sector_sense'] if e else None
        if e:
            g = min(100, 50+abs(e['sense_drift']*10))
            g, _ = get_rarity_quantifier_single(g, 'gain' if e['sense_drift']>0 else 'loss' )
            r['sense_drift_desc'] = 'little drift' if g=='normal' else g
            g = min(100, 50 + abs(e['sector_sense']-50) * 2)
            g, _ = get_rarity_descriptor_single(g, 'positive' if e['sector_sense']>50 else 'negative')
            r['sector_sense_desc'] = 'neutral' if g=='normal' else g
        else:
            r['sense_drift_desc'] = None
            r['sector_sense_desc'] = None
    if return_json:
        return JsonResponse({'sec_list': sec_list})
    assure_session(request)
    last_ss = get_lastss(request)
    rd = {'sec_list': sec_list, 'last_ss' : last_ss}
    return render(request, 'famehub/famehub_sector.html', rd)

def fh_sector_json(request):
    return fh_sector(request, return_json=True)

@ratelimittrylogin(nlgroup="tryfh_symbol", group="fh_symbol", nlrate="5/m",rate="30/m")
def fh_symbol(request, ss="", lastn="6", rd_only=False):
    ss = assure_ss(request, ss)
    SP = get_SP500()
    is_SP500 = ss in SP
    if ss and not is_SP500:
        r = cache_IEX(ss)
        if not r:
            messages.warning(request, 'No data for symbol '+ss)
            ss = ''

    assure_session(request)
    last_ss = get_lastss(request, lastn)
    watching = 0

    cn = ''
    if ss:
        meta = get_cache_IEX(ss)
        if 'companyName' in meta:
            cn = meta['companyName']

    if ss:
        if request.user.is_authenticated:
            uid = request.user.id
            a = runsql("select action from ff_app_watchlist where uid="+str(uid)+" and symbol='"+ss+"' order by request_dt desc limit 1")
            if a:
                if a[0]['action'] == 'add':
                    watching = 1
    rd = {"ss": ss, "is_SP500": is_SP500, "SP500": SP, "last_ss": last_ss, "watching": watching, "companyName":cn}
    if rd_only:
        return rd
    return render(request, 'famehub/famehub.html', rd)




@ratelimittrylogin(nlgroup="tryfh_symbol", group="fh_symbol", nlrate="5/m",rate="30/m")
def fh_sense(request, ss="", lastn=6):
    rd = fh_symbol(request, ss, lastn, rd_only=True)
    return render(request, 'famehub/famehub_sense.html', rd)
