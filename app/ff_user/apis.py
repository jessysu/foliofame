from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
import json
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from django.views.decorators.csrf import csrf_exempt

User = get_user_model()

from registration.models import RegistrationManager, RegistrationProfile


@csrf_exempt
def api_normal_register(request):
    if request.method != 'POST':
        return HttpResponse('Unauthorized', status=401)
    # 1. create user
    # 2. send activation code
    # 3. response
    json_data = json.loads(request.body)
    if "username" not in json_data or "email" not in json_data or "password" not in json_data:
        return HttpResponse('Invalid Input', status=400)

    new_user = RestRegistrationManager().rest_create_inactive_user(json_data
                                                                   , site=get_current_site(request))
    if new_user is None:
        return HttpResponse('Username or email existc, please change it', status=400)

    return JsonResponse({'status': "created"
                            , "info": json_data["username"]
                                      + " is created, Please check your info to activate your account"})


# normal rest api token
class RestAuthToken(ObtainAuthToken):

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email
        })


class RestRegistrationManager():
    @transaction.atomic
    def rest_create_inactive_user(self, data, site, send_email=True):
        # new_user = form.save(commit=False)

        if len(User.objects.filter(Q(username__iexact=data["username"]) | Q(email__iexact=data["email"]))) > 0:
            return None

        new_user = User.objects.create_user(data["username"]
                                            , data["email"]
                                            , data["password"]
                                            )
        new_user.is_active = False
        new_user.save()

        registration_profile = RegistrationProfile.objects.create_profile(new_user)

        if send_email:
            registration_profile.send_activation_email(site)

        return new_user

