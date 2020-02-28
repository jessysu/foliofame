from django.contrib.auth import get_user_model
from django.db.models import Q
from social_core.exceptions import AuthException

User = get_user_model()

from social_core.pipeline.user import get_username
def check_email_username_exists(backend, details, uid, user=None, *args, **kwargs):
    provider = backend.name

    # check if social user exists to allow logging in (not sure if this is necessary)
    social = backend.strategy.storage.user.get_social_auth(provider, uid)
    # check if given email is in use
    exists = User.objects.filter(
        Q(username__iexact=details.get('username', '')) | Q(email__iexact=details.get('email', ''))
    ).exists()

    # user is not logged in, social profile with given uid doesn't exist
    # and email is in use
    if not user and not social and exists:
        raise AuthException(backend)
