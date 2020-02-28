# -*- coding: utf-8 -*-
"""
Created on Tue Oct  10 22:35:38 2017

@author: jsu
"""

#pip intsll twitter
import twitter
#pip install newspaper3k
from newspaper import Article

import re, sys, datetime, time

from dateutil import parser
from get_sp500 import refresh_sp500
from util_mysql import table_exist, runsql, fetch_rawsql, dbcommit, dbclose, getcur

from static import TApp
t = twitter.Twitter(
        auth=twitter.OAuth(
            TApp['token'], 
            TApp['token_secret'], 
            TApp['consumer_key'], 
            TApp['consumer_secret']))


re_pattern = re.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', re.UNICODE)
re_tag     = re.compile(r'<[^>]+>')




FF_TWEETS_DDL = """create table ff_tweets (
symbol varchar(10),
tid bigint, 
created_at datetime, 
last_updated datetime, 
favorites int, 
retweets int,
tweet_text varchar(255),
tweet_url varchar(255),
user_name varchar(255),
user_screen varchar(255),
user_followers int,
user_friends int,
user_statuses int,
article_title varchar(1000),
article_url varchar(1000),
article text
)
""".replace('\n', ' ').replace('\r', '')

def assure_required_tables():
    if not table_exist("ff_tweets"):
        runsql(FF_TWEETS_DDL)
    if not table_exist("ff_scan_symbols"):
        refresh_sp500()
    r = fetch_rawsql("select min(datediff(now(),last_updated)) d from ff_scan_symbols")[0]
    if r['d'] > 7:
        refresh_sp500()



# Start of task
assure_required_tables()

symbols = fetch_rawsql("select symbol from ff_scan_symbols where datediff(now(),last_updated) < 60 and ifnull(TIMESTAMPDIFF(minute, last_scanned, now()),9999) > 1440 order by last_scanned desc")
if len(symbols) == 0 :
    sys.exit()

symbol = symbols[0]['symbol']
print("Working on " + symbol + " : " + time.strftime('%Y-%m-%d %H:%M:%S'))
sid = 0
current_time = datetime.datetime.now(datetime.timezone.utc)
#current_time = datetime.datetime.now()


for d in range(6, 0, -1):
    dt = current_time - datetime.timedelta(days=d)
    print("  Fetching up to "+dt.strftime('%Y-%m-%d'))
    tq = t.search.tweets(q="$"+symbol, lang="en", result_type="popular", until=dt.date().isoformat(), since_id=sid, count="100")
    for tw in tq['statuses']:
        tid = tw['id']
        sid = max(sid, tid)
        print("    Checking tweet #" +str(tid) + ". "+ time.strftime('%Y-%m-%d %H:%M:%S'))
        url_list = [i['url'] for i in tw['entities']['urls']]
        # no article
        if len(url_list) == 0:
            print("      No article")
            continue
        chk = fetch_rawsql("select count(1) cnt from ff_tweets where tid = "+str(tid))[0]['cnt']
        # old tweet
        if chk:
            runsql("update ff_tweets set last_updated=now(), favorites="+str(tw['favorite_count'])+", retweets="+str(tw['retweet_count'])+" where tid="+str(tid))
            print("      Old tweet")
            continue
        tweet_text = re_pattern.sub(u'\uFFFD', tw['text'])
        #chk = fetch_rawsql("select count(1) cnt from ff_tweets where tweet_text='" + tweet_text + "'")[0]['cnt']
        # same tweet text
        #if chk:
        #    print("      Duplicate")
        #    continue
        for u in url_list:
            chk = fetch_rawsql("select count(1) cnt from ff_tweets where tweet_url = '"+u+"'")[0]['cnt']
            if chk:
                break
        # same article from tweet_url
        if chk:
            print("      Old URL")
            continue
        for u in url_list:
            article = Article(u)
            try:
                article.download()
                article.parse()
            except:
                print("download error for "+u)
                continue
            ax = re_pattern.sub(u'\uFFFD', article.text.replace('\n', ''))
            if len(ax) < 500:
                print("      Insufficient content")
                continue
            au = article.canonical_link
            at = re_pattern.sub(u'\uFFFD', article.title)
            td = parser.parse(tw['created_at'])
            rawsql = "insert into ff_tweets (symbol, tid, created_at, last_updated, favorites, retweets, tweet_text, tweet_url, user_name, user_screen, user_followers, user_friends, user_statuses, article_title, article_url, article)"
            rawsql += "values (%s, %s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            val = (symbol, tid, td, tw['favorite_count'], tw['retweet_count'], tweet_text, u, tw['user']['name'], tw['user']['screen_name'], tw['user']['followers_count'], tw['user']['friends_count'], tw['user']['statuses_count'], at, au, ax)
            runsql(rawsql, val)
            dbcommit
            break

runsql("update ff_scan_symbols set last_scanned=now() where symbol = '"+symbol+"'")
print("  Updated scanning list. " + time.strftime('%Y-%m-%d %H:%M:%S'))
