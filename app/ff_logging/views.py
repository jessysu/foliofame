from django.http import HttpResponse
from django.shortcuts import render, redirect

from ratelimit.utils import is_authenticated
from .models import ClickLog, BesteverSessionLog, HindsightRequestLog, ViewLog, ApiLog
from django.utils import timezone
import datetime, pytz
from django.urls import resolve

# Create your views here.
def log_ff_external_clicks(request, s="", v="", t="", u=""):
    # cur = connection.cursor()
    # cur.execute("insert into ff_click_log ( \
    #              uid, \
    #              request_dt, \
    #              request_ip, \
    #              request_view, \
    #              symbol, \
    #              dest_type, \
    #              dest_url \
    #              ) values (%s, %s, %s, %s, %s, %s, %s)",
    #              (request.user.id,
    #              datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #              request.META.get('REMOTE_ADDR',''),
    #              v,
    #              s,
    #              t,
    #              u))

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ipaddress = ""
    if x_forwarded_for:
        ipaddress = x_forwarded_for.split(',')[-1].strip()
    else:
        ipaddress = request.META.get('REMOTE_ADDR')

    o_clicklog = ClickLog(
        uid = request.user if request.user.is_authenticated else None,
        session_key = request.session._session_key,
        request_dt = timezone.now(),
        request_ip = ipaddress,
        request_view = v,
        symbol = s.upper(),
        dest_type = t,
        dest_url = u
    )
    o_clicklog.save()
    return

def log_bestever_session(request, ss="", d=180):
    # cur = connection.cursor()
    # cur.execute("insert into ff_bestever_session_log ( \
    #              session_key, \
    #              request_dt, \
    #              request_ip, \
    #              request_path, \
    #              symbol, \
    #              d \
    #              ) values (%s, %s, %s, %s, %s, %s)",
    #              (request.session._session_key,
    #              datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #              request.META.get('REMOTE_ADDR',''),
    #              request.get_full_path()[:255],
    #              ss,
    #              d))
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ipaddress = ""
    if x_forwarded_for:
        ipaddress = x_forwarded_for.split(',')[-1].strip()
    else:
        ipaddress = request.META.get('REMOTE_ADDR')

    o_bsLog = BesteverSessionLog(
        uid = request.user if request.user.is_authenticated else None,
        session_key = request.session._session_key,
        request_dt = timezone.now(),
        request_ip = ipaddress,
        request_path = request.get_full_path()[:255],
        symbol = ss.upper(),
        d = d
    )
    o_bsLog.save()
    return


def log_hindsight_request(request, ld="", ds="", de="", ss=""):
    # cur = connection.cursor()
    # cur.execute("insert into ff_hindsight_request_log ( \
    #              request_dt, \
    #              request_path, \
    #              request_view, \
    #              rid_source, \
    #              rid_id, \
    #              ds, \
    #              de, \
    #              symbol \
    #              ) values (%s, %s, %s, %s, %s, %s, %s, %s)",
    #              (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #              request.get_full_path()[:255],
    #              ld,
    #              'anonymous:ip',
    #              request.META.get('REMOTE_ADDR',''),
    #              ds,
    #              de,
    #              ss))
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ipaddress = ""
    if x_forwarded_for:
        ipaddress = x_forwarded_for.split(',')[-1].strip()
    else:
        ipaddress = request.META.get('REMOTE_ADDR')

    o_hirLog = HindsightRequestLog(
        uid=request.user if request.user.is_authenticated else None,
        session_key=request.session._session_key,
        request_dt = timezone.now(),
        request_path = request.get_full_path()[:255],
        request_view = ld,
        rid_source = 'anonymous:ip',
        rid_id = ipaddress,
        ds=pytz.utc.localize(ds),
        de=pytz.utc.localize(de),
        symbol = ss.upper()
    )
    o_hirLog.save()
    return


def rate_limit_logging(request, *args, **kwargs):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ipaddress = ""
    if x_forwarded_for:
        ipaddress = x_forwarded_for.split(',')[-1].strip()
    else:
        ipaddress = request.META.get('REMOTE_ADDR')

    _device = None
    _is_touch = None
    _is_bot = None
    _browser_family = None
    _browser_version = None
    _os_family = None
    _os_version = None
    _device_family = None

    if hasattr(request, 'user_agent') and request.user_agent is not None:
        _device=""
        if request.user_agent.is_mobile:
            _device = "mobile" if _device is None or len(_device) == 0 else _device+" mobile"
        if request.user_agent.is_tablet:
            _device = "tablet" if _device is None or len(_device) == 0 else _device + " tablet"
        if request.user_agent.is_pc:
            _device = "pc" if _device is None or len(_device) == 0 else _device + " pc"
        _is_touch = request.user_agent.is_touch_capable
        _is_bot = request.user_agent.is_bot
        _browser_family = request.user_agent.browser.family
        _browser_version = request.user_agent.browser.version_string
        _os_family = request.user_agent.os.family
        _os_version = request.user_agent.os.version_string
        _device_family = request.user_agent.device.family

    rp = request.get_full_path()[:255]
    rs = rp.split('/')
    is_api = False
    ss = None
    if "ss" in kwargs:
        ss = kwargs["ss"]
        ss = ss.upper().replace('-','.')
    if len(rs) > 3:
        if rs[1].lower() == 'api':
            is_api = True
    if len(rs) >=5 and rs[1].lower() == 'api' and rs[3] == 'stock' and rs[4] == 'tohistory':
        # mobile api use api/v1/stock/tohistory to log symbol to ViewLog
        is_api = False

    if is_api:
        o_apiLog = ApiLog(
            uid=request.user if request.user.is_authenticated else None,
            session_key=request.session._session_key,
            request_dt=timezone.now(),
            request_ip=ipaddress,
            request_path=rp,
            request_api=resolve(request.path_info).url_name,
            api_version=rs[2][:10],
            symbol= ss,
            device=_device,
            is_touch=_is_touch,
            is_bot=_is_bot,
            browser_family=_browser_family,
            browser_version=_browser_version,
            os_family=_os_family,
            os_version=_os_version,
            device_family=_device_family
        )
        o_apiLog.save()
    else:
        o_viewLog = ViewLog(
            uid=request.user if request.user.is_authenticated else None,
            session_key=request.session._session_key,
            request_dt=timezone.now(),
            request_ip=ipaddress,
            request_path=rp,
            request_view=resolve(request.path_info).url_name,
            symbol= ss,
            device=_device,
            is_touch=_is_touch,
            is_bot=_is_bot,
            browser_family=_browser_family,
            browser_version=_browser_version,
            os_family=_os_family,
            os_version=_os_version,
            device_family=_device_family
        )
        o_viewLog.save()
    return
