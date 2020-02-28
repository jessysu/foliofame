from __future__ import absolute_import

from functools import wraps
import socket

from django.http import HttpRequest
from django.shortcuts import redirect

from ff_logging.views import rate_limit_logging
from ratelimit import ALL, UNSAFE
from ratelimit.exceptions import Ratelimited
from ratelimit.utils import is_ratelimited, is_authenticated


__all__ = ['ratelimit']


def ratelimit(group=None, key=None, rate=None, method=ALL, block=False):
    def decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kw):
            # Work as a CBV method decorator.
            if isinstance(args[0], HttpRequest):
                request = args[0]
            else:
                request = args[1]
            request.limited = getattr(request, 'limited', False)
            ratelimited = is_ratelimited(request=request, group=group, fn=fn,
                                         key=key, rate=rate, method=method,
                                         increment=True)
            if ratelimited and block:
                raise Ratelimited()
            return fn(*args, **kw)
        return _wrapped
    return decorator


ratelimit.ALL = ALL
ratelimit.UNSAFE = UNSAFE


def ratelimittrylogin(nlgroup=None, group=None, nlrate=None, rate=None, redirecturl=None, method=ALL):
    def decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kw):
            # Work as a CBV method decorator.
            if isinstance(args[0], HttpRequest):
                request = args[0]
            else:
                request = args[1]
            request.limited = getattr(request, 'limited', False)

            rate_limit_logging(request, *args, **kw)
            
            # rule-out exempt
            if check_bypassed_rules(request):
                #print("ruled-out")
                return fn(*args, **kw)

            # whitelist
            if check_bypassed_ip(request):
                #print("whitelisted")
                return fn(*args, **kw)

            if is_authenticated(request.user) is False \
                    and is_ratelimited(request=request, group=nlgroup, fn=fn,
                                       key="ip", rate=nlrate, method=method,
                                       increment=True):

                if redirecturl is None:
                    # return redirect("/accounts/login/?next="+request.path)
                    raise Ratelimited()
                else:
                    return redirect("/accounts/login/?next="+redirecturl)
            if is_authenticated(request.user) is True \
                    and is_ratelimited(request=request, group=group, fn=fn,
                                       key="user", rate=rate, method=method,
                                       increment=True):

                raise Ratelimited()
            return fn(*args, **kw)
        return _wrapped
    return decorator




#TODO: maybe make this into config file
WHITELIST_IPS = [
    '127.0.0.1',
    '73.239.243.8',
    '70.95.86.138'
    ]
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def check_bypassed_ip(request):
    ip = get_client_ip(request)
    if ip in WHITELIST_IPS:
        return True
    else:
        return False

def check_bypassed_rules(request):
    p = request.path.split('/')
    # bypass all level-0 FameBits
    if 'famebits' in p and not p[-2].isdigit():
        return True

    return False



