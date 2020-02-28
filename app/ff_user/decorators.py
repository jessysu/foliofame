from functools import wraps

from rest_framework.authtoken.models import Token



def getUser():
    def decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kw):
            # print(args[0].META)
            # print(Token.objects.get(key=args[0].META["HTTP_AUTHORIZATION"].split()[1]).user)
            if "HTTP_AUTHORIZATION" in args[0].META:
                ss = args[0].META["HTTP_AUTHORIZATION"].split()
                if len(ss) == 2:
                    try:
                        _token = Token.objects.get(key=ss[1])
                        args[0].user = _token.user
                    except Exception as e:
                        pass
            # print(args[0].user)
            f = fn(*args, **kw)
            return f
        return _wrapped
    return decorator