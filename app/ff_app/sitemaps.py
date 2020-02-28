from django.contrib import sitemaps
from django.urls import reverse

from ff_app.utils import get_SP500

class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = 'daily'
    def items(self):
        #return ['index', 'about', 'famelist']
        return ['index', 'about', 'famer_scan', 'famer_f66', 'fh_sector']
    def location(self, item):
        return reverse(item)

class URLSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = 'daily'
    def items(self):
        famelist = ['/fl/2/', '/fl/7/', '/fl/14/', '/fl/30/', '/fl/90/', '/fl/180/']
        famehub = get_SP500()
        famehub = ['/fh/'+f+'/' for f in famehub]
        #return famelist + famehub
        return famehub
    def location(self, item):
        return item
