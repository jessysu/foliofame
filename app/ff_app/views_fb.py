
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse

from ff_app.views import is_watching
from ff_app.defs import DME_SCOPES, BLOCKED_STOCKS, STYPE_LIST
from ff_app.utils import runsql, assure_sec, human_format, assure_ss, get_SP500, table_exist
from ff_app.apis import cache_IEX, get_rarity_quantifier_single, get_rarity_descriptor_single
from ff_app.views_my import get_watched_symbols
from copy import deepcopy
from ratelimit.decorators import ratelimittrylogin


# TODO: add redirect url
@ratelimittrylogin(nlgroup="tryfb_vol", group="fb_vol", nlrate="4/m",rate="20/m")
def fb_vol(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
        ss = ''
    watching = is_watching(request, ss) if ss else False
    ob = next(i for i in STYPE_LIST if i['ftype'] == 'vol')
    return render(request, 'famebits/fb_volume.html', {'ss': ss, 'watching': watching, 'ob': ob})

# TODO: add redirect url
@ratelimittrylogin(nlgroup="tryfb_pfl", group="fb_pfl", nlrate="4/m",rate="20/m")
def fb_pfl(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
        ss = ''
    watching = is_watching(request, ss) if ss else False
    ob = next(i for i in STYPE_LIST if i['ftype'] == 'pfl')
    return render(request, 'famebits/fb_pricefluc.html', {'ss': ss, 'watching': watching, 'ob': ob})

@ratelimittrylogin(nlgroup="tryfb_chg", group="fb_chg", nlrate="4/m",rate="20/m")
def fb_chg(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
    watching = is_watching(request, ss) if ss else False
    ob = next(i for i in STYPE_LIST if i['ftype'] == 'chg')
    return render(request, 'famebits/fb_changerate.html', {'ss': ss, 'watching': watching, 'ob': ob})

@ratelimittrylogin(nlgroup="tryfb_cfp", group="fb_cfp", nlrate="4/m",rate="20/m")
def fb_cfp(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
        ss = ''
    watching = is_watching(request, ss) if ss else False
    ob = next(i for i in STYPE_LIST if i['ftype'] == 'cfp')
    return render(request, 'famebits/fb_ceilfloor.html', {'ss': ss, 'watching': watching, 'ob': ob})

@ratelimittrylogin(nlgroup="tryfb_dme", group="fb_dme", nlrate="4/m",rate="20/m")
def fb_dme(request, ss="", scope="extrema", ns=1):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ ss if ss else "")
        ss = ''
    if scope not in [i['scope'] for i in DME_SCOPES]:
        scope = 'extrema'
    watching = is_watching(request, ss) if ss else False
    if ss:
        d = deepcopy(DME_SCOPES)
        for i in d:
            i['api_url'] =  i['api_url'].replace('$SS',ss).replace('$NS',str(ns))
        e = next(i for i in d if i['scope'] == scope)
        ob = next(i for i in STYPE_LIST if i['ftype'] == 'cfp')
    else:
        d = []
        e = {'api_url':'','desc':''}
        ob = ''
    return render(request, 'famebits/fb_dailymoveevents.html', {'ss': ss, 'watching': watching, 'DME_SCOPES':d, 'scope':scope, 'api_url':e['api_url'], 'desc':e['desc'], 'ob': ob})

# TODO: add redirect url
@ratelimittrylogin(nlgroup="tryfb_f66", group="fb_f66", nlrate="4/m",rate="20/m")
def fb_f66(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
        ss = ''
    watching = is_watching(request, ss) if ss else False
    ob = next(i for i in STYPE_LIST if i['ftype'] == 'f66')
    return render(request, 'famebits/fb_fame66.html', {'ss': ss, 'watching': watching, 'ob': ob})

# TODO: add redirect url
@ratelimittrylogin(nlgroup="tryfb_f6s", group="fb_f6s", nlrate="4/m",rate="20/m", redirecturl="/")
def fb_f6s(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
        ss = ''
    watching = is_watching(request, ss) if ss else False
    ob = next(i for i in STYPE_LIST if i['ftype'] == 'f66')
    return render(request, 'famebits/fb_fame66sent.html', {'ss': ss, 'watching': watching, 'ob': ob})

# TODO: add redirect url
@ratelimittrylogin(nlgroup="tryfb_bel", group="fb_bel", nlrate="4/m",rate="20/m")
def fb_bel(request, ss=""):
    ss = assure_ss(request, ss)
    if ss and ss not in get_SP500():
        messages.warning(request, 'Non-SP500 stocks are not supported for BestEver')
        ss = ''
    watching = is_watching(request, ss) if ss else False
    return render(request, 'famebits/fb_besteverlist.html', {'ss': ss, 'watching': watching})

# TODO: add redirect url
@ratelimittrylogin(nlgroup="tryfb_bes", group="fb_bes", nlrate="4/m",rate="20/m")
def fb_bes(request, ss=""):
    ss = assure_ss(request, ss)
    if ss and ss not in get_SP500():
        messages.warning(request, 'Non-SP500 stocks are not supported for BestEver')
        ss = ''
    watching = is_watching(request, ss) if ss else False
    return render(request, 'famebits/fb_besteversent.html', {'ss': ss, 'watching': watching})

@ratelimittrylogin(nlgroup="tryfb_bel", group="fb_bel", nlrate="4/m",rate="20/m")
def fb_ahd(request, ss=""):
    ss = assure_ss(request, ss)
    r = cache_IEX(ss)
    if not r:
        messages.warning(request, 'Failed in analyzing the symbol '+ss if ss else "")
        ss = ''
    watching = is_watching(request, ss) if ss else False
    return render(request, 'famebits/fb_fameahead.html', {'ss': ss, 'watching': watching})


@ratelimittrylogin(nlgroup="tryfb_sendoc", group="fb_sendoc", nlrate="4/m",rate="20/m")
def fb_sendoc(request, ss="", iex_id=""):
    ss = assure_ss(request, ss)
    rd = {}
    if ss and ss not in get_SP500():
        messages.warning(request, 'Non-SP500 stocks are not supported for Fame Sense')
        # return redirect
    else:
        rd['ss'] = ss
    if not table_exist('ff_finnews_f2') or not table_exist('ff_finnews_f3') or  not table_exist('ff_finnews_f4'):
        messages.warning(request, 'Fame Sense temporarily offline')
        # return redirect
    else:
        check_sym = runsql("select a.*, b.iex_related, b.iex_title, b.article_url from (select * from ff_finnews_f2 where symbol='"+ss+"' and iex_id='"+str(iex_id)+"') a, ff_finnews_iex b where a.iex_id=b.iex_id limit 1")
        if not check_sym:
            messages.warning(request, 'Fame Sense has not processed that document')
        else:
            rd['iex_id'] = iex_id
            rd['title']  = check_sym[0]['iex_title']
            rd['url']  = "/re?s="+ss+"&v=fb_sendoc&t=iexnews&u="+check_sym[0]['article_url']
    rd['watching'] = is_watching(request, ss) if ss else False
    return render(request, 'famebits/fb_sense_doc.html', rd)


@ratelimittrylogin(nlgroup="tryfb_sec", group="fb_sec", nlrate="4/m",rate="20/m")
def fb_sec(request, sec="", page_size=5, sense_interval="3 month", return_json=False):
    sec = assure_sec(sec)
    if not sec:
        messages.warning(request, 'Not a valid sector')
        messages.warning(request, 'Choose from <a href="/fh/">a list of sectors</a>.')
        return render(request, 'famebits/fb_sector.html', {'sec':sec})
    symbol_list = runsql("select @rn:=@rn+1 rn, a.* from (select a.*, b.sm, round(a.marketcap/b.sm*100) marketshare from ff_status_scan_w7 a, ff_status_scan_w6 b where a.sector='"+sec+"' and a.sector=b.sector order by marketabs desc) a, (select @rn:=0) b")
    symbol_list = [s for s in symbol_list if s['symbol'] not in BLOCKED_STOCKS]
    W = [i['symbol'] for i in get_watched_symbols(request)]
    sense_lsit = []
    sense_points = []
    if table_exist("ff_finnews_f1"):
        sense_list = runsql("select symbol, dense_sense, condense_sense, dense_diff, ifnull(dcon_bin,50) dcon_bin, marketcap from ff_finnews_f1 a, (select max(dest_date) max_dest_date from ff_finnews_f1) b where a.sector='"+sec+"' and a.dest_date=b.max_dest_date")
        sense_points = runsql("select dest_date, sum(marketcap) marketcap, round(sum(dense_sense*marketcap)/sum(marketcap),2) sector_sense, round(sum(dense_diff*marketcap)/sum(marketcap),2) sense_drift from ff_finnews_f1 where sector='"+sec+"' and dest_date>=date_sub(curdate(), interval "+sense_interval+") group by dest_date")

    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
        r['bid'] = int((r['rn']-1) / page_size)
        r['contrib_abs'] = human_format(abs(r['marketabs'])) 
        r['contrib_sign'] = ("-" if r['changePct'] < 0 else "+")
        r['wt'] = ("~"+str(int(r['marketshare'])) if r['marketshare']>=1 else "<1")
        r['w'] = r['symbol'] in W
        e = next((i for i in sense_list if i['symbol'] == r['symbol']), None)
        if e:
            g, _ = get_rarity_quantifier_single(min(100, 50+2*abs(e['dense_diff'])), "gain" if e['dense_diff']>0 else "loss")
            r['sense_drift'] = 'little drift' if g=='normal' else g
            r['sense_drift_b4color'] = 'secondary' if g=='normal' else ('success' if e['dense_diff']>0 else 'danger')
            g, _ = get_rarity_descriptor_single(50 + abs(e['dense_sense']-50), 'positive' if e['dense_sense']>50 else 'negative')
            r['sense_desc'] = 'neutral' if g=='normal' else g
            r['sense_desc_b4color'] = 'secondary' if g=='normal' else ('success' if e['dense_sense']>50 else 'danger')
            
    rd = {'sec': sec, 
          'symbol_list': symbol_list,
          'sense_points': sense_points, 
          "max_bid": int((len(symbol_list)-1)/page_size)
          }
    if return_json:
        return JsonResponse(rd)
    else:
        return render(request, 'famebits/fb_sector.html', rd)


def fb_sec_json(request, sec="", page_size=5):
    sec = assure_sec(sec)
    if not sec:
        return JsonResponse({})
    return fb_sec(request, sec=sec, page_size=page_size, return_json=True)
    

@ratelimittrylogin(nlgroup="tryfb_secsense", group="fb_secsense", nlrate="4/m",rate="20/m")
def fb_secsense(request, sec="", page_size=5, return_json=False):
    sec = assure_sec(sec)
    if not sec:
        messages.warning(request, 'Not a valid sector')
        messages.warning(request, 'Choose from <a href="/fh/">a list of sectors</a>.')
        return render(request, 'famebits/fb_sector.html', {'sec':sec})
    #symbol_list = runsql("select @rn:=@rn+1 rn, a.* from (select symbol, dense_sense, condense_sense, dense_diff, ifnull(dcon_bin,50) dcon_bin, marketcap from ff_finnews_f1 where sector='"+sec+"' order by abs(dcon_bin-50) desc) a, (select @rn:=0) b")
    symbol_list = runsql("select @rn:=@rn+1 rn, a.* from (select symbol, dense_sense, condense_sense, dense_diff, ifnull(dcon_bin,50) dcon_bin, marketcap from ff_finnews_f1 a, (select max(dest_date) max_dest_date from ff_finnews_f1) b where a.sector='"+sec+"' and a.dest_date=b.max_dest_date order by abs(dense_sense) desc) a, (select @rn:=0) b")
    #symbol_list = [s for s in symbol_list if s['symbol'] not in BLOCKED_STOCKS]
    W = [i['symbol'] for i in get_watched_symbols(request)]
    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
        r['bid'] = int((r['rn']-1) / page_size)
        r['marketcap'] = human_format(abs(r['marketcap'])) 
        r['w'] = r['symbol'] in W
        g, _ = get_rarity_quantifier_single(min(100, 50+2*abs(r['dense_diff'])), "gain" if r['dense_diff']>0 else "loss")
        r['sense_drift'] = 'little drift' if g=='normal' else g
        r['sense_drift_b4color'] = 'secondary' if g=='normal' else ('success' if r['dense_diff']>0 else 'danger')
        g, _ = get_rarity_descriptor_single(50 + abs(r['dense_sense']-50), 'positive' if r['dense_sense']>50 else 'negative')
        r['sense_desc'] = 'neutral' if g=='normal' else g
        r['sense_desc_b4color'] = 'secondary' if g=='normal' else ('success' if r['dense_sense']>50 else 'danger')
    rd = {'sec': sec, 
          'symbol_list': symbol_list, 
          "max_bid": int((len(symbol_list)-1)/page_size)
          }
    if return_json:
        return JsonResponse(rd)
    else:
        return render(request, 'famebits/fb_sectorsense.html', rd)


def fb_secsense_json(request, sec="", page_size=5):
    sec = assure_sec(sec)
    if not sec:
        return JsonResponse({})
    return fb_secsense(request, sec=sec, page_size=page_size, return_json=True)
