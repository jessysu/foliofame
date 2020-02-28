from django.http import HttpResponse
from django.shortcuts import redirect

from ratelimit.utils import is_authenticated


def rate_limit_error(request, rlexcept):
    # temporary solution, use api to check if the request is rest api
    if "api" in request.path or is_authenticated(request.user) is True:
        return HttpResponse(status=429)
    else:
        return redirect("/accounts/login/?next=" + request.path)