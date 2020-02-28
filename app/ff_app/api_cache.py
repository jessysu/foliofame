
from django.http import HttpRequest

from functools import wraps
import datetime, pytz

utc = pytz.timezone('UTC')

API_cache = {}

def check_api_cache(request, refresh_rate_in_seconds=60):
    enow = utc.localize(datetime.datetime.utcnow())
    if request.path in API_cache:
        if 'lastUpdate' in API_cache[request.path]:
            d = enow - API_cache[request.path]['lastUpdate']
            e = d.days * 86400 + d.seconds
            if e < refresh_rate_in_seconds:
                return API_cache[request.path]['cached']
    return False
            
def write_api_cache(request, data):
    enow = utc.localize(datetime.datetime.utcnow())
    API_cache[request.path] = {'lastUpdate': enow, 'cached': data}
    return


# DO NOT USE:
# If the API is expected to response differently according to different users
# DO NOT USE:
# For API responses differently to logged-in user verses anonymous user
def cache_api_internal(refresh_rate_in_seconds=60):
    def decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kw):
            if isinstance(args[0], HttpRequest):
                request = args[0]
            else:
                request = args[1]
            c = check_api_cache(request, refresh_rate_in_seconds)
            if c:
                #print("using cached: "+request.path)
                return c
            #print("calling real api: "+request.path)
            f = fn(*args, **kw)
            write_api_cache(request, f)
            #print("stored to cache: "+request.path)
            #print(f)
            return f
        return _wrapped
    return decorator




FN_cache = {}

def check_fn_cache(fn, refresh_rate_in_seconds=60):
    enow = utc.localize(datetime.datetime.utcnow())
    if fn in FN_cache:
        if 'lastUpdate' in FN_cache[fn]:
            d = enow - FN_cache[fn]['lastUpdate']
            e = d.days * 86400 + d.seconds
            if e < refresh_rate_in_seconds:
                return FN_cache[fn]['cached']
    return False

def write_fn_cache(fn, data):
    enow = utc.localize(datetime.datetime.utcnow())
    FN_cache[fn] = {'lastUpdate': enow, 'cached': data}
    return

def cache_fn_internal(refresh_rate_in_seconds=60):
    def decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kw):
            c = check_fn_cache(fn.__name__, refresh_rate_in_seconds)
            if c:
                #print("using cached: "+request.path)
                return c
            #print("calling real api: "+request.path)
            f = fn(*args, **kw)
            write_fn_cache(fn.__name__, f)
            #print("stored to cache: "+request.path)
            #print(f)
            return f
        return _wrapped
    return decorator
