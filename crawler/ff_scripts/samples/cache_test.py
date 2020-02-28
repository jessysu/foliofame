from util_cache import *

insert("foo", "foov")
insert("foo1", "foov1")
insert("foo2", "foov2")

print(query("foo1"))

print(query_related_keys("foo*"))

for key in query_related_keys("foo*"):
    print(query(key))

delete_all_related("foo*")
print(query_related_keys("foo*"))

"""
sys.path.append("/django")

import os
from django.core.cache import caches
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

caches["cache_redis"].set("foo", "value", timeout=25)
caches["cache_redis"].set("foo1", "value1", timeout=25)
caches["cache_redis"].set("foo2", "value2", timeout=25)
caches["cache_redis"].set("foo3", "value3", timeout=25)
caches["cache_redis"].set("foo4", "value4", timeout=25)
print(caches["cache_redis"].get("foo11"))

print(next(caches["cache_redis"].iter_keys("foo*")))
print(next(caches["cache_redis"].iter_keys("foo*")))

keys = caches["cache_redis"].iter_keys("foo*")

print(next(keys))
print(next(keys))
print(next(keys))
print(next(keys))
print(next(keys))


try:
    while True:
        print(next(keys))
except Exception as e:
    print(e)
"""
