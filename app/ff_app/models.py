from django.contrib.auth.models import User
from django.db import models

# Create your models here.
class WatchList(models.Model):
    uid = models.ForeignKey(User, null=True,  blank = True, on_delete=models.CASCADE, db_column='uid')
    request_dt = models.DateTimeField(auto_now=False)
    request_ip = models.GenericIPAddressField()
    request_view = models.CharField(max_length=40)
    symbol = models.CharField(max_length=10)
    action = models.CharField(max_length=10)

    class Meta:
        indexes = [
            models.Index(fields=['uid','symbol','request_dt','action']),
        ]

class UserPref(models.Model):
    uid = models.ForeignKey(User, null=True,  blank = True, on_delete=models.CASCADE, db_column='uid')
    updated = models.DateTimeField(auto_now=False)
    updated_path = models.CharField(max_length=50, null=True)
    pref = models.CharField(max_length=30)
    choice = models.CharField(max_length=30)
    memo = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['uid','pref']),
        ]

