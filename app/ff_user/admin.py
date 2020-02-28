from django.contrib import admin
from ff_user.models import DjangoAdminAccessIPWhitelist

# Register your models here.

admin.site.register(DjangoAdminAccessIPWhitelist)
