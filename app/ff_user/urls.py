from django.conf.urls import url, include
from ff_user import apis
from django.views.decorators.csrf import csrf_exempt
from rest_social_auth import views as SocialAuthViews

import rest_social_auth.views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordChangeView,
    PasswordChangeDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.urls import reverse_lazy, path
from django.views.generic import TemplateView
from registration.backends.model_activation import views as register_views
from registration.forms import RegistrationFormUniqueEmail
from ff_user.views import (
    SocialTokenOnlyAuthView,
    SocialTokenUserAuthView,
    SocialSessionAuthView,
    SocialJWTOnlyAuthView,
    SocialJWTUserAuthView,
)

urlpatterns = [

    #normal login, web
    url(r'^login/$', LoginView.as_view(template_name='accounts/login.html'), name='login'),
    url(r'^logout/$', LogoutView.as_view(next_page=reverse_lazy('login')), name='logout'),

    url(r'^password_change/$',
        PasswordChangeView.as_view(template_name='accounts/password_change_form.html'),
        name='password_change'),
    url(r'^password_change/done/$',
        PasswordChangeDoneView.as_view(template_name='accounts/password_change_done.html'),
        name='password_change_done'),

    url(r'^password_reset/$',
        PasswordResetView.as_view(template_name='accounts/password_reset_form.html', html_email_template_name="accounts/password_reset_email.html"),
        name='password_reset'),
    url(r'^password_reset/done/$',
        PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done'),
    url(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'),
        name='password_reset_confirm'),
    url(r'^reset/done/$',
        PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
        name='password_reset_complete'),


    # normal registration, web
    url(r'^activate/complete/$',
        TemplateView.as_view(
            template_name='registration/activation_complete.html'
        ),
        name='registration_activation_complete'),
    # The activation key can make use of any character from the
    # URL-safe base64 alphabet, plus the colon as a separator.
    url(r'^activate/(?P<activation_key>[-:\w]+)/$',
        register_views.ActivationView.as_view(),
        name='registration_activate'),
    url(r'^register/$',
        register_views.RegistrationView.as_view(form_class=RegistrationFormUniqueEmail),
        name='registration_register'),
    url(r'^register/complete/$',
        TemplateView.as_view(
            template_name='registration/registration_complete.html'
        ),
        name='registration_complete'),
    url(r'^register/closed/$',
        TemplateView.as_view(
            template_name='registration/registration_closed.html'
        ),
        name='registration_disallowed'),


    # social authentication, web
    url(r'^social/', include('social_django.urls', namespace='social')),


    # social rest api, login/register, mobile
    # copy from https://github.com/st4lk/django-rest-social-auth
    # returns token + user_data

    # url(r'^social_mobile/token_user/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
    #     SocialTokenUserAuthView.as_view(),
    #     name='login_social_token_user'),
    #
    # # returns token only
    # url(r'^social_mobile/token/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
    #     SocialTokenOnlyAuthView.as_view(),
    #     name='login_social_token'),
    #
    # url(r'^social/session/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
    #     SocialSessionAuthView.as_view(),
    #     name='login_social_session'),
    #
    # url(r'^social/jwt_user/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
    #     SocialJWTUserAuthView.as_view(),
    #     name='login_social_jwt_user'),
    #
    # # returns jwt only
    # url(r'^social/jwt/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
    #     SocialJWTOnlyAuthView.as_view(),
    #     name='login_social_jwt'),

    # returns token + user_data
    url(r'^api/v1/social_mobile/token_user/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
        SocialAuthViews.SocialTokenUserAuthView.as_view(),
        name='login_social_token_user'),

    # returns token only
    url(r'^api/v1/social_mobile/token/(?:(?P<provider>[a-zA-Z0-9_-]+)/?)?$',
        csrf_exempt(SocialAuthViews.SocialTokenOnlyAuthView.as_view()),
        name='login_social_token'),

    # normal rest register
    path(r'api/v1/mobile/register/', apis.api_normal_register, name='rest_register'),

    # normal rest api token
    url(r'^api/v1/mobile/user_token/', apis.RestAuthToken.as_view()),


]


