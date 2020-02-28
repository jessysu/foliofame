import sys
sys.path.append("/django")

import os
from django.core.cache import caches
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'


# reference http://niwinz.github.io/django-redis/latest/
def delete_all_related(pattern):
    try:
        caches["cache_redis"].delete_pattern(pattern)
    except:
        return False
    return True


def delete_key(key):
    try:
        caches["cache_redis"].delete(key)
    except:
        return False
    return True


def insert(key, value, ttl=None):
    # ttl: time to leave(seconds). if you want to keep it persistent, don't insert anyting
    try:
        caches["cache_redis"].set(key, value, timeout=None)
    except:
        return True
    return False


def query(key):    
    try:
        return caches["cache_redis"].get(key)
    except:
        return None


def query_related_keys(pattern):
    try:
        return caches["cache_redis"].keys(pattern)
    except:
        return None

