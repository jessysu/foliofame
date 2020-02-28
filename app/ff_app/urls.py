from django.conf.urls import url
from django.urls import path
from django.contrib.sitemaps.views import sitemap

from ff_app import views
from ff_app import apis
from ff_app import views_my, views_fb, views_fmr, views_fh
from ff_app.sitemaps import StaticViewSitemap, URLSitemap

urlpatterns = [

    url(r'^404$', views.error_404, name='404'),

    #url(r'^be/(?P<ss>.*)/(?P<d>.*)/$', views.bestever, name='bestever'),
    #url(r'^be/(?P<ss>.*)/', views.bestever, name='bestever'),
    #url(r'^be/', views.bestever, name='bestever'),
    path(r'fh/', views_fh.fh_sector, name='fh_sector'),
    path(r'fh/sector/', views_fh.fh_sector, name='fh_sector'),
    path(r'fh/sense/<ss>/', views_fh.fh_sense, name='fh_sense'),
    path(r'fh/<ss>/', views_fh.fh_symbol, name='fh_symbol'),
    path(r'fmr/f66/<int:d>/', views_fmr.fame66list, name='famer_f66'),
    path(r'fmr/f66/', views_fmr.fame66list, name='famer_f66'),
    path(r'fmr/<ftype>/', views_fmr.famer_scan, name='famer_scan'),
    path(r'fmr/', views_fmr.famer_scan, name='famer_scan'),
    #path(r'fl/<int:d>/', views.famelist, name='famelist'),
    #url(r'^fl/.*$', views.famelist, name='famelist'),
    url(r'^hsd/(?P<ss>.*)/$', views.hindsight_daily, name='hindsight_daily'),
    url(r'^hsd/$', views.hindsight_daily, name='hindsight_daily'),
    url(r'^hsm/(?P<ss>.*)/$', views.hindsight_monthly, name='hindsight_monthly'),
    url(r'^hsm/$', views.hindsight_monthly, name='hindsight_monthly'),

    url(r'^about/$', views.about, name='about'),

    url(r'^re$', views.redirect_external, name='redirect_external'),


    path(r'fb/vol/<ss>/', views_fb.fb_vol, name='fb_vol'),
    path(r'fb/pfl/<ss>/', views_fb.fb_pfl, name='fb_pfl'),
    path(r'fb/cfp/<ss>/', views_fb.fb_cfp, name='fb_cfp'),
    path(r'fb/dme/<ss>/<scope>/<int:ns>/', views_fb.fb_dme, name='fb_dme'),
    path(r'fb/dme/<ss>/<scope>/', views_fb.fb_dme, name='fb_dme'),
    path(r'fb/dme/<ss>/', views_fb.fb_dme, name='fb_dme'),
    path(r'fb/chg/<ss>/', views_fb.fb_chg, name='fb_chg'),
    path(r'fb/f6s/<ss>/', views_fb.fb_f6s, name='fb_f6s'),
    path(r'fb/f66/<ss>/', views_fb.fb_f66, name='fb_f66'),
    path(r'fb/bes/<ss>/', views_fb.fb_bes, name='fb_bes'),
    path(r'fb/bel/<ss>/', views_fb.fb_bel, name='fb_bel'),
    path(r'fb/ahd/<ss>/', views_fb.fb_ahd, name='fb_ahd'),
    path(r'fb/sen/<ss>/<int:iex_id>/', views_fb.fb_sendoc, name='fb_sendoc'),
    path(r'fb/sec/<sec>/', views_fb.fb_sec, name='fb_sec'),
    path(r'fb/secsense/<sec>/', views_fb.fb_secsense, name='fb_secsense'),

    url(r'^my/recent/quotes/$', views_my.my_recent_quotes, name='my_recent_quotes'),
    url(r'^my/recent/', views_my.my_recent_quotes, name='my_recent_quotes'),
    url(r'^my/watch/quotes/$', views_my.my_watch_quotes, name='my_watch_quotes'),
    url(r'^my/watch/', views_my.my_watch_quotes, name='my_watch_quotes'),

    url(r'^watch/(?P<action>.*)/(?P<s>.*)/$', views_my.watchlist_entry, name='watchlist_entry'),
    url(r'^pref/(?P<item>.*)/(?P<choice>.*)/$', views_my.user_pref_update, name='user_pref_update'),

    url(r'^api/v1/fame66/w52/(?P<ss>.*)/$', apis.fame66_w52_support, name='fame66_w52_support'),
    url(r'^api/v1/fame66/(?P<ss>.*)/$', apis.fame66_support, name='fame66_support'),
    path(r'api/v1/famebits/vol/<ss>/<int:ns>/', apis.famebits_volume, name='famebits_volume'),
    path(r'api/v1/famebits/vol/<ss>/', apis.famebits_volume, name='famebits_volume'),
    path(r'api/v1/famebits/pfl/<ss>/<int:ns>/', apis.famebits_pricefluc, name='famebits_pricefluc'),
    path(r'api/v1/famebits/pfl/<ss>/', apis.famebits_pricefluc, name='famebits_pricefluc'),
    path(r'api/v1/famebits/f6s/<ss>/<int:ns>/', apis.famebits_fame66sent, name='famebits_fame66sent'),
    path(r'api/v1/famebits/f6s/<ss>/', apis.famebits_fame66sent, name='famebits_fame66sent'),
    path(r'api/v1/famebits/f66/<ss>/', apis.famebits_fame66, name='famebits_fame66'),
    path(r'api/v1/famebits/bes/<ss>/<int:ns>/', apis.famebits_bestsent, name='famebits_bestsent'),
    path(r'api/v1/famebits/bes/<ss>/', apis.famebits_bestsent, name='famebits_bestsent'),
    path(r'api/v1/famebits/bel/<ss>/', apis.famebits_bestlist, name='famebits_bestlist'),
    path(r'api/v1/famebits/chg/<ss>/<int:ns>/', apis.famebits_changerate, name='famebits_changerate'),
    path(r'api/v1/famebits/chg/<ss>/', apis.famebits_changerate, name='famebits_changerate'),
    path(r'api/v1/famebits/cfp/<ss>/<int:ns>/', apis.famebits_ceilfloor, name='famebits_ceilfloor'),
    path(r'api/v1/famebits/cfp/<ss>/', apis.famebits_ceilfloor, name='famebits_ceilfloor'),
    path(r'api/v1/famebits/dme/<ss>/<int:ns>/<target>/<int:mat>/', apis.famebits_dailymoveevents, name='famebits_dailymoveevents'),
    path(r'api/v1/famebits/dme/<ss>/<int:ns>/<target>/', apis.famebits_dailymoveevents, name='famebits_dailymoveevents'),
    path(r'api/v1/famebits/dme/<ss>/<int:ns>/', apis.famebits_dailymoveevents, name='famebits_dailymoveevents'),
    path(r'api/v1/famebits/dme/<ss>/', apis.famebits_dailymoveevents, name='famebits_dailymoveevents'),
    path(r'api/v1/famebits/ahd/<ss>/<int:ns>/', apis.famebits_ahead, name='famebits_ahead'),
    path(r'api/v1/famebits/ahd/<ss>/', apis.famebits_ahead, name='famebits_ahead'),
    path(r'api/v1/famebits/mkt/<int:ns>/rich/', apis.famebits_marketbits_rich, name='famebits_marketbits_rich'),
    path(r'api/v1/famebits/mkt/<int:ns>/', apis.famebits_marketbits, name='famebits_marketbits'),
    path(r'api/v1/famebits/mkt/', apis.famebits_marketbits, name='famebits_marketbits'),
    path(r'api/v1/famebits/sec/<sec>/rich/<int:ns>/', apis.famebits_sectorbits_rich, name='famebits_sectorbits_rich'),
    path(r'api/v1/famebits/sec/<sec>/rich/', apis.famebits_sectorbits_rich, name='famebits_sectorbits_rich'),
    path(r'api/v1/famebits/sec/<sec>/<int:ns>/', apis.famebits_sectorbits, name='famebits_sectorbits'),
    path(r'api/v1/famebits/sec/<sec>/', apis.famebits_sectorbits, name='famebits_sectorbits'),
    #path(r'api/v1/famebits/secs/<sec>/', apis.famebits_sectorbits, name='famebits_sectorbits'),
    path(r'api/v1/famebits/sens/<ss>/0/', apis.famebits_sense_symbol_0, name='famebits_sense_symbol_0'),
    path(r'api/v1/famebits/sens/<ss>/more/', apis.famebits_sense_symbol_more, name='famebits_sense_symbol_more'),
    path(r'api/v1/famebits/sens/<ss>/', apis.famebits_sense_symbol, name='famebits_sense_symbol'),
    path(r'api/v1/famebits/sensd/<ss>/<int:iex_id>/', apis.famebits_sense_symboldoc, name='famebits_sense_symboldoc'),
    path(r'api/v1/famebits/sensdt/<ss>/<int:iex_id>/', apis.famebits_sense_symboldoc_track, name='famebits_sense_symboldoc_track'),
    path(r'api/v1/famebits/send/<int:iex_id>/<int:n_sentences>/', apis.famebits_sense_doc, name='famebits_sense_doc'),
    path(r'api/v1/famebits/send/<int:iex_id>/<additional>/', apis.famebits_sense_doc, name='famebits_sense_doc'),
    path(r'api/v1/famebits/send/<int:iex_id>/', apis.famebits_sense_doc, name='famebits_sense_doc'),
    path(r'api/v1/famebits/date/', apis.famebits_date, name='famebits_date'),

    path(r'api/v1/famelists/all/<int:n>/', apis.famelist_overall, name='famelist_overall'),
    path(r'api/v1/famelists/all/', apis.famelist_overall, name='famelist_overall'),
    path(r'api/v1/famelists/alldetail/<int:n>/<int:start>/', apis.famelist_overalldetail, name='famelist_overalldetail'),
    path(r'api/v1/famelists/alldetail/<int:n>/', apis.famelist_overalldetail, name='famelist_overalldetail'),
    path(r'api/v1/famelists/alldetail/', apis.famelist_overalldetail, name='famelist_overalldetail'),

    path(r'api/v1/famelists/fmr/sense/<int:n>', apis.famelist_famersense, name='famelist_famersense'),
    path(r'api/v1/famelists/fmr/sense/', apis.famelist_famersense, name='famelist_famersense'),
    path(r'api/v1/famelists/fmr/f66/<int:d>/', apis.famelist_famerf66, name='famelist_famerf66'),
    path(r'api/v1/famelists/fmr/f66/', apis.famelist_famerf66, name='famelist_famerf66'),
    path(r'api/v1/famelists/fmr/<ftype>/', apis.famelist_famerscan, name='famelist_famerscan'),
    path(r'api/v1/famelists/sec/fh/', views_fh.fh_sector_json, name='fh_sector_json'),
    path(r'api/v1/famelists/sec/<sec>/', views_fb.fb_sec_json, name='fb_sec_json'),
    path(r'api/v1/famelists/secsense/<sec>/', views_fb.fb_secsense_json, name='fb_secsense_json'),

    path(r'api/v1/onebig/<ss>/', apis.cache_onebig_symbol, name='cache_onebig_symbol'),

    path(r'api/v1/my/watchlist/', apis.my_watchlist, name='my_watchlist'),
    path(r'api/v1/my/recentlist/<int:n_max>/', apis.my_recentlist, name='my_recentlist'),
    path(r'api/v1/my/recentlist/', apis.my_recentlist, name='my_recentlist'),
    
    path(r'api/v1/misc/sp500/', apis.misc_SP500, name='misc_SP500'),
    path(r'api/v1/misc/nonsp/', apis.misc_nonSP, name='misc_nonSP'),

    path(r'api/v1/stock/tohistory/<ss>/', apis.add_stock_to_history, name='add_stock_to_history'),

    # bad api call, all 404 out
    url(r'^api/.*$', views.error_404, name='404'),

    # sitemaps
    path('sitemap.xml', sitemap, {'sitemaps': {'static':StaticViewSitemap, 'URL': URLSitemap}}, name="django.contrib.sitemaps.views.sitemap"),
    #url('^$', views.index, name='index')
    url(r'^$', views.index, name='index'),
    url(r'^.*/$', views.error_404, name='404')
]
