# -*- coding: utf-8 -*-
"""
Created on Thu Dec 1 22:35:41 2018

@author: jsu
"""

#pip install justext
import justext

#pip install newspaper3k
#from newspaper import Article

# https://github.com/kurtmckee/feedparser
#import feedparser

import requests
import random
import re
import datetime, time
from dateutil.parser import parse
import pytz
utc = pytz.timezone('UTC')

from util_mysql import table_exist, runsql, fetch_rawsql, dbcommit, dbclose

T_SOURCE_REQUEST_GAP_SEC = 30
T_SOURCE_REQUEST_RDM_SEC = 30
F_REFETCH_IN_SCAN        = False


FF_FINNEWS_IEX_DDL = """create table ff_finnews_iex (
symbol varchar(10),
published datetime, 
last_updated datetime, 
iex_id varchar(30),
iex_url varchar(100),
iex_source varchar(20),
iex_title varchar(255),
iex_image varchar(100),
iex_summary varchar(1000),
iex_related varchar(255),
article_title varchar(1000),
article_url varchar(1000),
article text
) character set utf8 collate utf8_unicode_ci
""".replace('\n', ' ').replace('\r', '')

re_pattern = re.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', re.UNICODE)


def assure_required_tables():
    if not table_exist("ff_finnews_iex"):
        runsql(FF_FINNEWS_IEX_DDL)
        runsql("create index ff_finnews_iex_i1 on ff_finnews_iex (symbol, iex_url)")
        runsql("create index ff_finnews_iex_i2 on ff_finnews_iex (iex_id)")
        runsql("create index ff_finnews_iex_i3 on ff_finnews_iex (last_updated)")
        runsql("create index ff_finnews_iex_i4 on ff_finnews_iex (published)")

# Start of task
assure_required_tables()

headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.90 Safari/537.36'}

C = {}

symbols = fetch_rawsql("select symbol from ff_scan_symbols")
symbols = [i['symbol'] for i in symbols]

#symbols = ['AAPL','AMD','GOOG','NVDA','QCOM']
#symbols = symbols[:5]

n_insert_attempt = 0
n_insert_success = 0
for s in symbols:
    s = s.replace("-",".")
    try:
        P = requests.get("https://api.iextrading.com/1.0/stock/"+s+"/news/last/100")
        P = P.json()
    except:
        print("[e] IEX error and skipped '"+s+"' ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
        time.sleep(5)
        continue
    for post in P:
        pi = post['url'].split('/')[-1]
        # pt = datetime.datetime.fromisoformat(post['datetime']).astimezone(utc)
        # data looks like 2019-02-26T17:00:00-05:00
        pt = parse(post['datetime']).astimezone(utc)
        # old news
        chk = fetch_rawsql("select count(1) cnt from ff_finnews_iex where symbol='"+s+"' and iex_url='"+post['url'][:100]+"' and article<>''")[0]['cnt']
        if chk:
            # overwrite last_updated as current time (NOT preferred)
            #runsql("update ff_finnews_iex set last_updated=now() where symbol='"+s+"' and iex_url='"+post['url'][:100]+"'")
            continue
        # news previously fetched
        if pi:
            A = fetch_rawsql("select article, article_url, article_title from ff_finnews_iex where iex_id='"+pi+"' and article<>''")
            if A:
                A = A[0]
                rawsql = "insert into ff_finnews_iex (symbol, published, last_updated, iex_id, iex_url, iex_source, iex_title, iex_image, iex_summary, iex_related, article_title, article_url, article)"
                rawsql += "values (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                val = (s, pt, pi, post['url'][:100], post['source'][:20], post['headline'][:255], post['image'][:100], post['summary'][:65000], post['related'][:255], A['article_title'], A['article_url'], A['article'])
                runsql(rawsql, val)
                print("  [i] Recycled entry ("+pi+"): "+post['headline'])
                continue
        # news previously failed retrieving from source
        f_refetch = False
        chk = fetch_rawsql("select count(1) cnt from ff_finnews_iex where symbol='"+s+"' and iex_url='"+post['url'][:100]+"' and ( article='' or length(article)<length(iex_summary) )")[0]['cnt']
        if chk:
            if F_REFETCH_IN_SCAN:
                f_refetch = True
                print("  [i] Refetching old entry", post['headline'])
            else:
                continue
        
        # sleep well to avoid rate limit of destination site
        if post['source'] in C:
            diff = datetime.datetime.now() - C[post['source']]
            dsec = (diff.days * 86400 + diff.seconds)
            if dsec < T_SOURCE_REQUEST_GAP_SEC:
                time.sleep(T_SOURCE_REQUEST_GAP_SEC + int(T_SOURCE_REQUEST_RDM_SEC*random.random()) - dsec)
        C[post['source']] = datetime.datetime.now()
        R = requests.get(post['url'], headers=headers)
        
        S = justext.justext(R.content, justext.get_stoplist("English"))
        p = [r.text for r in S if r.is_heading or not r.is_boilerplate]
        ax = ""
        au = ""
        at = ""
        if p:
            at = re_pattern.sub(u'\uFFFD', p[0])
            au = R.url
            ax = re_pattern.sub(u'\uFFFD', " ".join(p[1:]))
        #article = Article(post['url'])
        #try:
            #article.download()
            #article.parse()
            #au = article.canonical_link
            #at = re_pattern.sub(u'\uFFFD', article.title)
            #ax = re_pattern.sub(u'\uFFFD', article.text.replace('\n', ''))
            #print("  [i] New entry", post.headline)
        #except:
            #print("  [e] Download error for "+post.headline)
            #continue
        if f_refetch:
            rawsql = "update ff_finnews_iex set last_updated=now(), article_title = %s, article = %s where symbol= %s and iex_url= %s"
            val = (at, ax, s, post['url'][:100])
            print("  [i] Old entry updated: ", post['headline'])
        else:
            rawsql = "insert into ff_finnews_iex (symbol, published, last_updated, iex_id, iex_url, iex_source, iex_title, iex_image, iex_summary, iex_related, article_title, article_url, article)"
            rawsql += "values (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            val = (s, pt, pi, post['url'][:100], post['source'][:20], post['headline'][:255], post['image'][:100], post['summary'][:1000], post['related'][:255], at[:1000], au[:1000], ax[:64000])
            n_insert_attempt += 1
            runsql(rawsql, val)
            n_insert_success += 1
            print("  [i] New entry: ", post['headline'])
    print("Done ..."+s+" ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    dbcommit()
dbclose()

# please add this message in email
print("Inserted " + str(n_insert_success) + " news entries out of " + str(n_insert_attempt) + " attempts")


from finnews_sense import incremental_sense
incremental_sense()
