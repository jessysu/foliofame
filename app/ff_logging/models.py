from django.contrib.auth.models import User
from django.db import models

# Create your models here.
class ClickLog(models.Model):
    uid = models.ForeignKey(User, null=True,  blank = True, on_delete=models.CASCADE, db_column='uid')
    session_key = models.CharField(null=True,  blank = True, max_length=40)
    request_dt = models.DateTimeField(auto_now=False)
    request_ip = models.GenericIPAddressField()
    request_view = models.CharField(max_length=40)
    symbol = models.CharField(max_length=10)
    dest_type = models.CharField(max_length=40)
    dest_url = models.URLField(max_length=255)


class BesteverSessionLog(models.Model):
    uid = models.ForeignKey(User, null=True,  blank = True, on_delete=models.CASCADE, db_column='uid')
    session_key = models.CharField(null=True,  blank = True, max_length=40)
    request_dt = models.DateTimeField(auto_now=False)
    request_ip = models.GenericIPAddressField()
    request_path = models.URLField(max_length=255)
    symbol = models.CharField(max_length=10)
    d = models.IntegerField()


class HindsightRequestLog(models.Model):
    uid = models.ForeignKey(User, null=True,  blank = True, on_delete=models.CASCADE, db_column='uid')
    session_key = models.CharField(null=True,  blank = True, max_length=40)
    request_dt = models.DateTimeField(auto_now=False)
    request_path = models.URLField(max_length=255)
    request_view = models.CharField(max_length=45)
    rid_source = models.CharField(max_length=45)
    rid_id = models.CharField(max_length=255)
    ds = models.DateTimeField(auto_now=False)
    de = models.DateTimeField(auto_now=False)
    symbol = models.CharField(max_length=10)


class ViewLog(models.Model):
    uid = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, db_column='uid')
    session_key = models.CharField(null=True, blank=True, max_length=40)
    request_dt = models.DateTimeField(auto_now=False)
    request_ip = models.GenericIPAddressField()
    request_path = models.URLField(max_length=255)
    request_view = models.URLField(max_length=50)
    symbol = models.CharField(max_length=10, null=True, blank=True)

    device = models.CharField(max_length=20)
    is_touch = models.NullBooleanField(null=True, blank=True)
    is_bot = models.NullBooleanField(null=True, blank=True)
    browser_family = models.CharField(max_length=30, null=True, blank=True)
    browser_version = models.CharField(max_length=10, null=True, blank=True)
    os_family = models.CharField(max_length=30, null=True, blank=True)
    os_version = models.CharField(max_length=10, null=True, blank=True)
    device_family = models.CharField(max_length=30, null=True, blank=True)

    ud1 = models.CharField(max_length=10, null=True, blank=True)
    ud2 = models.CharField(max_length=100, null=True, blank=True)


    class Meta:
        indexes = [
            models.Index(fields=['uid']),
            models.Index(fields=['symbol']),
            models.Index(fields=['request_view']),
            models.Index(fields=['request_dt', 'symbol', 'uid']),
            models.Index(fields=['request_path']),
        ]


class ApiLog(models.Model):
    uid = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, db_column='uid')
    session_key = models.CharField(null=True, blank=True, max_length=40)
    request_dt = models.DateTimeField(auto_now=False)
    request_ip = models.GenericIPAddressField()
    request_path = models.URLField(max_length=255)
    request_api = models.URLField(max_length=50)
    api_version = models.URLField(max_length=10)
    symbol = models.CharField(max_length=10, null=True, blank=True)

    device = models.CharField(max_length=20)
    is_touch = models.NullBooleanField(null=True, blank=True)
    is_bot = models.NullBooleanField(null=True, blank=True)
    browser_family = models.CharField(max_length=30, null=True, blank=True)
    browser_version = models.CharField(max_length=10, null=True, blank=True)
    os_family = models.CharField(max_length=30, null=True, blank=True)
    os_version = models.CharField(max_length=10, null=True, blank=True)
    device_family = models.CharField(max_length=30, null=True, blank=True)

    ud1 = models.CharField(max_length=10, null=True, blank=True)
    ud2 = models.CharField(max_length=100, null=True, blank=True)


    class Meta:
        indexes = [
            models.Index(fields=['uid']),
            models.Index(fields=['symbol']),
            models.Index(fields=['api_version']),
            models.Index(fields=['request_api']),
            models.Index(fields=['request_dt', 'symbol', 'uid']),
            models.Index(fields=['request_path']),
        ]