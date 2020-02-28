
from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib import messages
from django.urls import resolve
from django.utils import timezone

from ff_app.utils import runsql, get_SP500, assure_ss, standardize_ss, IEX_validator_single
from ff_app.models import WatchList, UserPref
import pytz

from ff_app.defs import USER_PREFS
from ff_user.decorators import getUser
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@getUser()
def watchlist_entry(request, s="", action="", max_watch=30):
    s = assure_ss(request, s)
    action = action.lower()
    if action != "add" and action != "drop":
        return JsonResponse({"success": False, "message": "Invalid action"})
    if request.method != "POST" or not request.user.is_authenticated:
        return JsonResponse({"success": False, "message": "Invalid method or user not logged in"})
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ipaddress = ""
    if x_forwarded_for:
        ipaddress = x_forwarded_for.split(',')[-1].strip()
    else:
        ipaddress = request.META.get('REMOTE_ADDR')
    request_view = request.POST.get("view","")

    watching = [i['symbol'] for i in get_watched_symbols(request)]
    if action == "add":
        if not s:
            return JsonResponse({"message":"Empty symbol"})
        if s not in get_SP500() and not IEX_validator_single(s):
            return JsonResponse({"message":"Invalid symbol "+s})
        if len(watching) >= max_watch:
            return JsonResponse({"message":"Reached maximum " + str(max_watch) + " of watched symbols. Drop some"})
    else:
        # action == "drop"
        if s not in watching:
            return JsonResponse({"message":"Not watching "+s})
    

    o_watchlist = WatchList(
        uid = request.user if request.user.is_authenticated else None,
        request_dt = timezone.now(),
        request_ip = ipaddress,
        request_view = request_view,
        symbol = s,
        action = action
    )
    o_watchlist.save()
    return JsonResponse({"message":"Succeeded"})


def user_pref_update(request, item="", choice=""):
    if not item or not choice:
        return JsonResponse({"success": False, "error": "Invalid submission"})
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Non-registered user"})
    if item not in [i['item'] for i in USER_PREFS]:
        return JsonResponse({"success": False, "error": "Invalid preference item"})
    I = next(i for i in USER_PREFS if i['item'] == item)
    if choice not in I['choices']:
        return JsonResponse({"success": False, "error": "Invalid preference choice"})
    if UserPref.objects.filter(uid=request.user, pref=item).exists():
        UserPref.objects.filter(uid=request.user, pref=item).update(choice = choice, 
                                                                    updated = timezone.now(), 
                                                                    updated_path = resolve(request.path_info).url_name)
    else:
        o_UserPref = UserPref(
            uid = request.user,
            updated = timezone.now(),
            pref = item,
            choice = choice,
            memo = ''
            )
        o_UserPref.save()
    return JsonResponse({"success": True, "message":"Succeeded"})




def get_default_list():
    return [
            {'symbol': 'AAPL', 'watching': 0}, 
            {'symbol': 'AMZN', 'watching': 0}, 
            {'symbol': 'FB', 'watching': 0}, 
            {'symbol': 'GOOG', 'watching': 0}, 
            {'symbol': 'MSFT', 'watching': 0}
    ]

def get_watched_symbols(request):
    if not request.user.is_authenticated:
        return []
    symbol_list = runsql("select a.symbol, request_dt, 1 watching from ff_app_watchlist a, (select symbol, max(request_dt) mrdt from ff_app_watchlist where uid="+str(request.user.id)+" group by symbol) b \
                          where a.uid="+str(request.user.id)+" and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add' order by symbol")
    for s in symbol_list:
        s['symbol'] = standardize_ss(s['symbol'])
    return symbol_list

def get_recent_symbols(request, n_max=10):
    if not request.user.is_authenticated:
        return []
    symbol_list = runsql("select a.*, if(b.symbol is null,0,1) watching from \
                          (select symbol, max(request_dt) request_dt from ff_logging_viewlog where uid="+str(request.user.id)+" and symbol is not null group by symbol order by request_dt desc limit "+str(n_max)+") a left join \
                          (select a.symbol, request_dt from ff_app_watchlist a, (select symbol, max(request_dt) mrdt from ff_app_watchlist where uid="+str(request.user.id)+" group by symbol) b \
                            where a.uid="+str(request.user.id)+" and a.symbol=b.symbol and a.request_dt=b.mrdt and a.action='add') \
                          b on a.symbol=b.symbol order by request_dt desc")
    for s in symbol_list:
        s['symbol'] = standardize_ss(s['symbol'])
    return symbol_list




def my_recent_quotes(request, ss="", n="10", default_list=False):
    if not request.user.is_authenticated:
        return redirect("/")
    # symbol_list contains info on which symbols are watched
    symbol_list = get_recent_symbols(request)
    if not symbol_list:
        symbol_list = get_default_list()
        default_list = True
    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
    rs = {"symbol_list":symbol_list, "SP500": get_SP500(), "default_list": default_list}
    return render(request, 'my/my_quotes.html', rs)


def my_watch_quotes(request, ss="", n_warning = 100):
    if not request.user.is_authenticated:
        return redirect("/")
    symbol_list = get_watched_symbols(request)
    if not symbol_list:
        messages.warning(request, 'Watchlist empty.')
        return redirect("/my/recent/quotes/")
    if len(symbol_list) > n_warning:
        messages.warning(request, 'Watchlist longer than '+str(n_warning)+'. Some features are disabled.')
    for r in symbol_list:
        r['sym_id'] = r['symbol'].replace('.','-')
    rs = {"symbol_list":symbol_list, "SP500": get_SP500()}
    return render(request, 'my/my_quotes.html', rs)


