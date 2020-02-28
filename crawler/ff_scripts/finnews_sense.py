# -*- coding: utf-8 -*-
"""
Created on Wed Apr 24 22:01:55 2019

@author: jsu
"""

import re
import time
import datetime, pytz
import numpy as np
import os
import errno

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.externals import joblib

from util_mysql import runsql, fetch_rawsql, runsqlmany
from finnews_settings import *






utc = pytz.timezone('UTC')
eastern = pytz.timezone('US/Eastern')
enow = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)

FILE_GLOBAL_TV = 'model/global_tv_$YEARWEEK.sav'.replace("$YEARWEEK", enow.strftime("%Y%U"))
FILE_GLOBAL_TV_LST = 'model/global_tv_latest.sav'
FILE_GLOBAL_GB = 'model/global_gb_$YEARWEEK.sav'.replace("$YEARWEEK", enow.strftime("%Y%U"))
FILE_LOCAL_TMP = 'model/local_gb_$YEARWEEK_$TERM_$SYMBOL.sav'.replace("$YEARWEEK", enow.strftime("%Y%U"))
FILE_OVERALL   = 'model/local_gb_$YEARWEEK_$TERM.sav'
FILE_LOCAL_LST = 'model/local_gb_latest_$TERM_$SYMBOL.sav'
FILE_OVERALL_LST = 'model/local_gb_latest_$TERM.sav'.replace("$YEARWEEK", enow.strftime("%Y%U"))

if os.path.isfile(FILE_GLOBAL_TV) and not FORCE_RETRAIN:
    RETRAIN_GLOBAL_TV = False
else:
    RETRAIN_GLOBAL_TV = True




def assure_folder(filename):
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise


def doc_to_vec(A):
    documents = []
    IEX_ids   = []

    for a in A:
        document = str(a['article'])
    
        # Remove all the special characters
        #document = re.sub(r'\W', ' ', str(document))

        # remove all single characters
        document = re.sub(r'\s+[a-zA-Z]\s+', ' ', document)

        # Remove single characters from the start
        document = re.sub(r'\^[a-zA-Z]\s+', ' ', document) 

        # Substituting multiple spaces with single space
        document = re.sub(r'\s+', ' ', document, flags=re.I)

        # Removing prefixed 'b' (bytes format only)
        #document = re.sub(r'^b\s+', '', document)

        # Converting to Lowercase
        document = document.lower()

        # Lemmatization
        # Option #1 use accurate positioned lemmatizer (tree leaves vs. departing leaves)
        #document = ' '.join(lemmatize_sent(document))
        # Option #2 general ignoring position, basically stemmer
        document = document.split()
        document = [wnl.lemmatize(word) for word in document]
    
        #document = [t for t in document if not t.isdigit() and t.isalnum()]
        #document = [t for t in document if not t.isdigit() and t.isalnum() and t[-2:]!='ly']
        document = [t for t in document if not t.isdigit() and t.isalnum() and t[-2:]!='ly' and len(t)>3]
        document = ' '.join(document)

        documents.append(document)
        IEX_ids.append(a['iex_id'])
    
    return documents, IEX_ids



def final_sense(is_incremental = False):
    if is_incremental:
        runsql("drop table if exists ff_finnews_f2")
        runsql("create table ff_finnews_f2 as select a.*, b.iex_source, b.iex_title, b.iex_related, b.article_url from (select * from ff_finnews_b12 union select * from ff_finnews_d8) a, (select iex_id, any_value(iex_source) iex_source, any_value(iex_title) iex_title, any_value(iex_related) iex_related, any_value(article_url) article_url from ff_finnews_iex where published>=date_sub(now() , interval 6 month) and greatest(length(article),length(iex_summary))>500 group by iex_id) b where a.iex_id=b.iex_id")
        runsql("create index ff_finnews_f2_i1 on ff_finnews_f2 (symbol, dest_date)")
        runsql("create index ff_finnews_f2_i2 on ff_finnews_f2 (symbol, published)")
        runsql("create index ff_finnews_f2_i3 on ff_finnews_f2 (symbol, iex_id)")
        runsql("drop table if exists ff_finnews_f3")
        runsql("create table ff_finnews_f3 as select * from ff_finnews_c1 union select * from ff_finnews_c11")
        runsql("create index ff_finnews_f3_i1 on ff_finnews_f3 (iex_id)")
        runsql("drop table if exists ff_finnews_f4")
        runsql("create table ff_finnews_f4 as select * from ff_finnews_c0 union select * from ff_finnews_c00")
        runsql("create index ff_finnews_f4_i1 on ff_finnews_f4 (iex_id)")
        print("Finalized Fame Sense incremental run ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        runsql("drop table if exists ff_finnews_f0")
        runsql("create table ff_finnews_f0 as select * from ff_finnews_b19")
        runsql("create index ff_finnews_f0_i1 on ff_finnews_f0 (symbol, dest_date)")
        runsql("create index ff_finnews_f0_i2 on ff_finnews_f0 (dest_date)")
        runsql("drop table if exists ff_finnews_f1")
        runsql("create table ff_finnews_f1 as select a.sector, ifnull(marketcap,if(@s=symbol,@m,null)) marketcap, @s:=symbol symbol, dest_date, dense_sense, condense_sense, dense_diff, condense_diff, dcon_bin, dense_diff*ifnull(marketcap,if(@s=symbol,@m,null)) denseeff, abs(dense_diff*ifnull(marketcap,if(@s=symbol,@m,null))) denseabs, @m:=ifnull(marketcap,@m) dummy_mc from (select c.sector, round(c.marketcap*cr) marketcap, d.* from ff_finnews_f0 d inner join ff_status_scan_w3 c on d.symbol=c.symbol left join (select a.symbol, a.close_date, a.close/b.close cr from ff_stock a, (select symbol, close from ff_stock where close_date=(select max(close_date) from ff_stock)) b where a.close_date>=date_sub(curdate(), interval 6 month) and a.symbol=b.symbol) a on d.symbol=a.symbol and d.dest_date=a.close_date order by symbol, dest_date ) a, (select @s:='',@m:=null) b")
        runsql("create index ff_finnews_f1_i1 on ff_finnews_f1 (sector, dest_date, dense_diff)")
        runsql("create index ff_finnews_f1_i2 on ff_finnews_f1 (dest_date)")
        runsql("create index ff_finnews_f1_i3 on ff_finnews_f1 (symbol, dest_date)")
        runsql("drop table if exists ff_finnews_f2")
        runsql("create table ff_finnews_f2 as select a.*, b.iex_source, b.iex_title, b.iex_related, b.article_url from ff_finnews_b12 a, (select iex_id, any_value(iex_source) iex_source, any_value(iex_title) iex_title, any_value(iex_related) iex_related, any_value(article_url) article_url from ff_finnews_iex where published>=date_sub(now() , interval 6 month) and greatest(length(article),length(iex_summary))>500 group by iex_id) b where a.iex_id=b.iex_id")
        runsql("create index ff_finnews_f2_i1 on ff_finnews_f2 (symbol, dest_date)")
        runsql("create index ff_finnews_f2_i2 on ff_finnews_f2 (symbol, published)")
        runsql("create index ff_finnews_f2_i3 on ff_finnews_f2 (symbol, iex_id)")
        runsql("drop table if exists ff_finnews_f3")
        runsql("create table ff_finnews_f3 as select * from ff_finnews_c1")
        runsql("create index ff_finnews_f3_i1 on ff_finnews_f3 (iex_id)")
        runsql("drop table if exists ff_finnews_f4")
        runsql("create table ff_finnews_f4 as select * from ff_finnews_c0")
        runsql("create index ff_finnews_f4_i1 on ff_finnews_f4 (iex_id)")
        runsql("drop table if exists ff_finnews_f5")
        runsql("create table ff_finnews_f5 as select * from ff_finnews_w7")
        runsql("create index ff_finnews_f5_i1 on ff_finnews_f5 (symbol, iex_id)")
        print("Finalized Fame Sense training run ... "+time.strftime('%Y-%m-%d %H:%M:%S'))




def gather_sense():
    A = fetch_rawsql("select iex_id, any_value(iex_title) title, any_value(if(length(article)>length(iex_summary),article,iex_summary)) article from ff_finnews_iex where published>=date_sub(now() , interval 6 month) and greatest(length(article),length(iex_summary))>500 group by iex_id")
    print("Done fetching finnews articles ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    documents, IEX_ids = doc_to_vec(A)
    print("Done cleaning finnews articles ... "+time.strftime('%Y-%m-%d %H:%M:%S'))

    if RETRAIN_GLOBAL_TV:
        TV = TfidfVectorizer(tokenizer=LemmaTokenizer(), max_df=0.3, min_df=2, max_features=1000, stop_words='english')
        tv = TV.fit_transform(documents)
        assure_folder(FILE_GLOBAL_TV)
        joblib.dump(TV, FILE_GLOBAL_TV)
        joblib.dump(TV, FILE_GLOBAL_TV_LST)
    else:
        #TV = joblib.load(FILE_GLOBAL_TV)
        TV = joblib.load(FILE_GLOBAL_TV_LST)
        tv = TV.transform(documents)
    print("Done corpus vectorizing ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    return A, IEX_ids, TV, tv



def dig_docs(A, IEX_ids, TV, tv, is_incremental=False):
    if is_incremental:
        keyword_table = 'ff_finnews_c00'
        keysent_table = 'ff_finnews_c11'
    else:
        keyword_table = 'ff_finnews_c0'
        keysent_table = 'ff_finnews_c1'
    runsql("drop table if exists " + keyword_table)
    runsql("create table "+keyword_table+" (iex_id varchar(30), key_id int, key_weight float, word varchar(100))")
    runsql("drop table if exists " + keysent_table)
    runsql("create table "+keysent_table+" (iex_id varchar(30), key_id int, key_weight float, sentence varchar(1000))")

    T = TV.get_feature_names()
    WORD_BUFFER = []
    SENT_BUFFER = []
    for i, d in enumerate([a['article'] for a in A]):
        dense_vector = tv[i].toarray()[0]
        keywords = [{'word':T[j],'tfidf':dense_vector[j]} for j in np.argsort(dense_vector)[::-1][:N_KEYWORDS]]
        WORD_BUFFER += [(IEX_ids[i], k, w['tfidf'], w['word']) for k,w in enumerate(keywords)]
        sentences = d.replace(';','.').split('. ')
        sentence_importance = []
        for idx, s in enumerate(sentences):
            s_weight = sum([k['tfidf'] for k in keywords if k['word'] in s.lower()])
            s_weight /= np.log2(max(8,len(s.split())))
            if len(s) < 1000:
                sentence_importance.append({'sentence':s, 'weight':s_weight, 'idx':idx})
        important_sentences = sorted(sentence_importance, key=lambda k: k['weight'])
        important_sentences = important_sentences[::-1][:N_SENTENCES]
        ordered_sentences  = sorted(important_sentences, key=lambda k: k['idx'])
        SENT_BUFFER += [(IEX_ids[i], k, s['weight'], s['sentence'][:1000]) for k,s in enumerate(ordered_sentences)]
        if len(WORD_BUFFER) >= 10000:
            runsqlmany("insert into "+keyword_table+" (iex_id, key_id, key_weight, word) values (%s,%s,%s,%s)", WORD_BUFFER)
            WORD_BUFFER = []
        if len(SENT_BUFFER) >= 10000:
            runsqlmany("insert into "+keysent_table+" (iex_id, key_id, key_weight, sentence) values (%s,%s,%s,%s)", SENT_BUFFER)
            SENT_BUFFER = []
    if WORD_BUFFER:
        runsqlmany("insert into "+keyword_table+" (iex_id, key_id, key_weight, word) values (%s,%s,%s,%s)", WORD_BUFFER)
    if SENT_BUFFER:
        runsqlmany("insert into "+keysent_table+" (iex_id, key_id, key_weight, sentence) values (%s,%s,%s,%s)", SENT_BUFFER)
    print("Done sentence weighing ... "+time.strftime('%Y-%m-%d %H:%M:%S'))



def profile_training():
    runsql("drop table if exists ff_stock_1y")
    runsql("create table ff_stock_1y as select * from ff_stock where close_date>=date_sub(now(), interval 1 year)")
    runsql("create index ff_stock_1y_i1 on ff_stock_1y (symbol, close_date)")
    runsql("drop table if exists ff_finnews_w1")
    runsql("create table ff_finnews_w1 as select symbol, published pt, date(published) published, iex_id, iex_source from ff_finnews_iex where greatest(length(article),length(iex_summary))>500")
    runsql("drop table if exists ff_finnews_w2")
    runsql("create table ff_finnews_w2 as select a.*, (select min(rn) from ff_stock_w40 where close_date<published) rn from ff_finnews_w1 a")
    runsql("create index ff_finnews_w2_i1 on ff_finnews_w2 (symbol, rn)")
    runsql("drop table if exists ff_finnews_w3")
    runsql("create table ff_finnews_w3 as select a.*, bp.close_date date_previous, bs.close_date date_same, b1.close_date date_1d, b2.close_date date_2d from ff_finnews_w2 a left join ff_stock_w40 bp on a.rn=bp.rn left join ff_stock_w40 bs on a.rn=bs.rn+1 left join ff_stock_w40 b1 on a.rn=b1.rn+2 left join ff_stock_w40 b2 on a.rn=b2.rn+3")
    runsql("create index ff_finnews_w3_i1 on ff_finnews_w3 (published)")
    runsql("drop table if exists ff_finnews_w4")
    runsql("create table ff_finnews_w4 as select a.* \
       ,(select min(close_date) from ff_stock_w40 where close_date>=date_add(published , interval 1 week)) date_1w \
       ,(select min(close_date) from ff_stock_w40 where close_date>=date_add(published , interval 2 week)) date_2w \
       ,(select min(close_date) from ff_stock_w40 where close_date>=date_add(published , interval 1 month)) date_1m \
       ,(select min(close_date) from ff_stock_w40 where close_date>=date_add(published , interval 2 month)) date_2m \
       from ff_finnews_w3 a")
    runsql("create index ff_finnews_w4_i1 on ff_finnews_w4 (symbol, date_previous)")
    runsql("create index ff_finnews_w4_i2 on ff_finnews_w4 (symbol, date_same)")
    runsql("create index ff_finnews_w4_i3 on ff_finnews_w4 (symbol, date_1d)")
    runsql("create index ff_finnews_w4_i4 on ff_finnews_w4 (symbol, date_2d)")
    runsql("drop table if exists ff_finnews_w5")
    runsql("create table ff_finnews_w5 as select a.*, bp.close close_p, bs.close close_s, b1d.close close_1d, b2d.close close_2d from ff_finnews_w4 a \
       left join ff_stock_1y bp on a.symbol=bp.symbol and a.date_previous=bp.close_date \
       left join ff_stock_1y bs on a.symbol=bs.symbol and a.date_same=bs.close_date \
       left join ff_stock_1y b1d on a.symbol=b1d.symbol and a.date_1d=b1d.close_date \
       left join ff_stock_1y b2d on a.symbol=b2d.symbol and a.date_2d=b2d.close_date")
    runsql("create index ff_finnews_w5_i1 on ff_finnews_w5 (symbol, date_1w)")
    runsql("create index ff_finnews_w5_i2 on ff_finnews_w5 (symbol, date_2w)")
    runsql("create index ff_finnews_w5_i3 on ff_finnews_w5 (symbol, date_1m)")
    runsql("create index ff_finnews_w5_i4 on ff_finnews_w5 (symbol, date_2m)")
    runsql("drop table if exists ff_finnews_w6")
    runsql("create table ff_finnews_w6 as select a.*, b1w.close close_1w, b2w.close close_2w, b1m.close close_1m, b2m.close close_2m from ff_finnews_w5 a \
       left join ff_stock_1y b1w on a.symbol=b1w.symbol and a.date_1w=b1w.close_date \
       left join ff_stock_1y b2w on a.symbol=b2w.symbol and a.date_2w=b2w.close_date \
       left join ff_stock_1y b1m on a.symbol=b1m.symbol and a.date_1m=b1m.close_date \
       left join ff_stock_1y b2m on a.symbol=b2m.symbol and a.date_2m=b2m.close_date")
    runsql("drop table if exists ff_finnews_w7")
    runsql("create table ff_finnews_w7 as select a.*, (close_s-close_p)/close_p chg_sameday, (close_1d-close_s)/close_s chg_1d, (close_2d-close_s)/close_s chg_2d , (close_1w-close_s)/close_s chg_1w, (close_2w-close_s)/close_s chg_2w, (close_1m-close_s)/close_s chg_1m, (close_2m-close_s)/close_s chg_2m from ff_finnews_w6 a")
    runsql("create index ff_finnews_w7_i1 on ff_finnews_w7 (published)")
    print("Done profiling ... "+time.strftime('%Y-%m-%d %H:%M:%S'))



def focus_prep(IEX_SYMBOL, IEX_ids, tv, is_train=True):
    ALL_LOCAL = {}
    OVERALL_X = []
    OVERALL_y = []
    for iexsym in IEX_SYMBOL:
        if not iexsym['iex_id'] in IEX_ids:
            print(iexsym['iex_id']+"("+iexsym['symbol']+") is not vectorized")
            continue
        i = IEX_ids.index(iexsym['iex_id'])
        dense_vector = tv[i].toarray()[0]
        if iexsym['symbol'] not in ALL_LOCAL:
            if is_train:
                ALL_LOCAL[iexsym['symbol']] = {'X_train':[], 'y_train':[], 'X_score':[], 'y_score':[], 'ID_score':[], 'chg_score':[]}
            else:
                ALL_LOCAL[iexsym['symbol']] = {'X_score':[], 'ID_score':[]}
        if is_train and iexsym['chg'] is not None:
            ALL_LOCAL[iexsym['symbol']]['X_train'].append(dense_vector)
            ALL_LOCAL[iexsym['symbol']]['y_train'].append(np.sign(iexsym['chg']) * (np.log10(abs(iexsym['chg'])+10**(-6))+6))
            OVERALL_X.append(dense_vector)
            OVERALL_y.append(np.sign(iexsym['chg']) * (np.log10(abs(iexsym['chg'])+10**(-6))+6))
        ALL_LOCAL[iexsym['symbol']]['X_score'].append(dense_vector)
        ALL_LOCAL[iexsym['symbol']]['ID_score'].append(iexsym['iex_id'])
        if is_train:
            ALL_LOCAL[iexsym['symbol']]['y_score'].append(np.sign(iexsym['chg']) * (np.log10(abs(iexsym['chg'])+10**(-6))+6) if iexsym['chg'] is not None else None)
            ALL_LOCAL[iexsym['symbol']]['chg_score'].append(iexsym['chg'])
    return ALL_LOCAL, OVERALL_X, OVERALL_y



def focus_models(term, ALL_LOCAL, OVERALL_X, OVERALL_y, is_train=True):
    local_model_file = FILE_OVERALL.replace('$TERM',term) if is_train else FILE_OVERALL_LST.replace('$TERM',term)
    if not is_train and not os.path.isfile(local_model_file):
        print("Missing required model file. Run training first.")
        sys.exit()
    elif not is_train:
        OGB = joblib.load(local_model_file)
        print("Loaded " + term + " overall model for incremental focus articles "+time.strftime('%Y-%m-%d %H:%M:%S'))
    elif os.path.isfile(local_model_file) and not RETRAIN_GLOBAL_TV:
        OGB = joblib.load(local_model_file)
        print("Loaded " + term + " overall model for focus articles "+time.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        OGB = GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=.1, min_samples_leaf=9, min_samples_split=9)
        OGB.fit(OVERALL_X, OVERALL_y)
        joblib.dump(OGB, local_model_file)
        with open(FILE_OVERALL_LST.replace('$TERM',term), 'wb') as fid:
            joblib.dump(OGB, fid)
        print("Done " + term + " training overall model for focus articles "+time.strftime('%Y-%m-%d %H:%M:%S'))

    for symbol, data in ALL_LOCAL.items():
        if is_train:
            SQL_insert = "insert into ff_finnews_b0 (symbol, iex_id, term, model_type, y, chg_term, raw_sense) values (%s,%s,%s,%s,%s,%s,%s)"
            local_model_file = FILE_LOCAL_TMP.replace('$TERM',term).replace('$SYMBOL',symbol)
            X = data['X_train']
            y = data['y_train']
            is_focus = True
            if os.path.isfile(local_model_file) and not RETRAIN_GLOBAL_TV:
                GB = joblib.load(local_model_file)
            elif len(X)>=3:
                GB = GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=.1, min_samples_leaf=9, min_samples_split=9)
                GB.fit(X, y)
                joblib.dump(GB, local_model_file)
                with open(FILE_LOCAL_LST.replace('$TERM',term).replace('$SYMBOL',symbol), 'wb') as fid:
                    joblib.dump(GB, fid)
            else:
                print("Using only global sense for " + symbol + " : " + term + " due to weak training data (n=" + str(len(X)) + ")")
                is_focus = False
            y = data['y_score']
            chg = data['chg_score']
        else:
            SQL_insert = "insert into ff_finnews_d2 (symbol, iex_id, term, model_type, raw_sense) values (%s,%s,%s,%s,%s)"
            local_model_file = FILE_LOCAL_LST.replace('$TERM',term).replace('$SYMBOL',symbol)
            if os.path.isfile(local_model_file):
                GB = joblib.load(local_model_file)
                is_focus = True
            else:
                is_focus = False
        X = data['X_score']
        ID = data['ID_score']
        SQL_Buffer = []
        counter = 0
        for i in range(len(X)):
            if is_focus:
                raw_sense = GB.predict(X[i].reshape(1,-1))
                SQL_Buffer.append((symbol, ID[i], term, 'L', y[i], chg[i], raw_sense[0]) if is_train else (symbol, ID[i], term, 'L', raw_sense[0]))
                counter += 1
            raw_sense = OGB.predict(X[i].reshape(1,-1))
            SQL_Buffer.append((symbol, ID[i], term, 'G', y[i], chg[i], raw_sense[0]) if is_train else (symbol, ID[i], term, 'G', raw_sense[0]))
            counter += 1
            if counter > 10000:
                if SQL_Buffer:
                    runsqlmany(SQL_insert, SQL_Buffer)
                    SQL_Buffer = []
                    counter = 0
        if SQL_Buffer:
            runsqlmany(SQL_insert, SQL_Buffer)




def build_sense():
    print("Started Fame Sense building ... "+time.strftime('%Y-%m-%d %H:%M:%S'))
    A, IEX_ids, TV, tv = gather_sense()
    dig_docs(A, IEX_ids, TV, tv)
    profile_training()

    print("Started focus models "+time.strftime('%Y-%m-%d %H:%M:%S'))
    A = fetch_rawsql("select iex_id, any_value(iex_title) title, any_value(if(length(article)>length(iex_summary),article,iex_summary)) article from ff_finnews_iex where published>=date_sub(now() , interval 1 year) and greatest(length(article),length(iex_summary))>500 group by iex_id")
    print("Done fetching focus articles "+time.strftime('%Y-%m-%d %H:%M:%S'))
    documents, IEX_ids = doc_to_vec(A)
    print("Done cleaning focus articles "+time.strftime('%Y-%m-%d %H:%M:%S'))
    tv = TV.transform(documents)
    print("Done vectorizing focus articles "+time.strftime('%Y-%m-%d %H:%M:%S'))

    runsql("drop table if exists ff_finnews_b0")
    runsql("create table ff_finnews_b0 (symbol varchar(10), iex_id varchar(30), term varchar(10), model_type varchar(4), y float, chg_term float, raw_sense float)")
    for term in TERMS:
        IEX_SYMBOL = fetch_rawsql("select iex_id, symbol, published, date_same, chg_"+term+" chg from ff_finnews_w7")
        ALL_LOCAL, OVERALL_X, OVERALL_y = focus_prep(IEX_SYMBOL, IEX_ids, tv)
        print("Done preparing focus articles for " + term + " training "+time.strftime('%Y-%m-%d %H:%M:%S'))
        
        focus_models(term, ALL_LOCAL, OVERALL_X, OVERALL_y, is_train=True)
        print("Finished local sense on term " + term + " ... " + time.strftime('%Y-%m-%d %H:%M:%S'))

    runsql("create index ff_finnews_b0_i1 on ff_finnews_b0 (iex_id)")
    runsql("drop table if exists ff_finnews_b1")
    runsql("create table ff_finnews_b1 as select iex_id, any_value(published) published, any_value(date(published)) published_date, any_value(iex_source) iex_source, any_value(iex_title) iex_title from ff_finnews_iex where published>=date_sub(now() , interval 6 month) and greatest(length(article),length(iex_summary))>500 group by iex_id")
    runsql("create index ff_finnews_b1_i1 on ff_finnews_b1 (iex_id)")
    runsql("drop table if exists ff_finnews_b2")
    runsql("create table ff_finnews_b2 as select a.*, b.published, b.published_date, b.iex_source, b.iex_title from ff_finnews_b0 a, ff_finnews_b1 b where a.iex_id=b.iex_id")
    runsql("create index ff_finnews_b2_i1 on ff_finnews_b2 (symbol, iex_id, model_type, term)")
    runsql("drop table if exists ff_finnews_b3")
    runsql("create table ff_finnews_b3 as select symbol, iex_id, model_type, any_value(published) published, sum(if(raw_sense>=0,1,0)) n_up, sum(if(raw_sense<0,1,0)) n_down \
           , max(raw_sense) max_sense, min(raw_sense) min_sense, sum(raw_sense)/(max(raw_sense)-min(raw_sense)) con_sense \
           , avg(if(raw_sense>=0,raw_sense,null)) pos_sense, avg(if(raw_sense<0,raw_sense,null)) neg_sense \
           from ff_finnews_b2 group by symbol, iex_id, model_type")
    runsql("create index ff_finnews_b3_i1 on ff_finnews_b3 (symbol, iex_id, model_type)")
    runsql("drop table if exists ff_finnews_b4")
    runsql("create table ff_finnews_b4 as select symbol, count(distinct iex_id) n_doc from ff_finnews_b3 group by symbol")
    runsql("create index ff_finnews_b4_i1 on ff_finnews_b4 (symbol)")
    runsql("drop table if exists ff_finnews_b5")
    runsql("create table ff_finnews_b5 as select a.symbol, a.iex_id, any_value(published) published, any_value(b.n_doc) n_doc, sum(n_up) n_up, sum(n_down) n_down \
           , sum( if(model_type='L', 1/(1/log10(b.n_doc+2)+1) * con_sense, 1/log10(b.n_doc+2)/(1/log10(b.n_doc+2)+1) * con_sense) ) con_sense \
           , if(sum(n_up)>0,sum(n_up*pos_sense)/sum(n_up),null) pos_sense, if(sum(n_down)>0,sum(n_down*neg_sense)/sum(n_down),null) neg_sense \
           , sum(if(model_type='G',n_up,0)) n_g_up, sum(if(model_type='G',n_down,0)) n_g_down, sum(if(model_type='L',n_up,0)) n_l_up, sum(if(model_type='L',n_down,0)) n_l_down \
           from ff_finnews_b3 a, ff_finnews_b4 b where a.symbol = b.symbol group by symbol, iex_id")
    runsql("drop table if exists ff_finnews_b6")
    runsql("create table ff_finnews_b6 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) bin, a.* from (select a.*, cnt from (select * from ff_finnews_b5) a, (select count(1) cnt from ff_finnews_b5) b order by con_sense) a, (select @rn:=0) b")
    runsql("create index ff_finnews_b6_i1 on ff_finnews_b6 (bin)")
    runsql("drop table if exists ff_finnews_b7")
    runsql("create table ff_finnews_b7 select a.bin, a.min_con, ifnull(b.min_con,(select max(con_sense) from ff_finnews_b6)) max_con from (select bin bin, min(con_sense) min_con from ff_finnews_b6 group by bin) a left join (select bin-1 bin, min(con_sense) min_con from ff_finnews_b6 group by bin-1) b on a.bin=b.bin")
    runsql("drop table if exists ff_finnews_b8")
    runsql("create table ff_finnews_b8 as select a.*, date(published) published_date, (con_sense-b.min_con)/(b.max_con-b.min_con) bin_float from ff_finnews_b6 a, ff_finnews_b7 b where a.bin=b.bin")
    runsql("create index ff_finnews_b8_i1 on ff_finnews_b8 (symbol, published)")
    runsql("create index ff_finnews_b8_i2 on ff_finnews_b8 (symbol, published_date)")
    runsql("drop table if exists ff_stock_date6m")
    runsql("create table ff_stock_date6m as select * from \
           (select adddate('1970-01-01',t4.i*10000 + t3.i*1000 + t2.i*100 + t1.i*10 + t0.i) dest_date from \
           (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t0, \
           (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t1, \
           (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t2, \
           (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t3, \
           (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t4) v \
           where dest_date between date_sub(curdate(), interval 6 month) and curdate()")
    runsql("drop table if exists ff_finnews_b9")
    runsql("create table ff_finnews_b9 as select distinct(symbol) symbol, dest_date from ff_finnews_b6, ff_stock_date6m")
    runsql("create index ff_finnews_b9_i1 on ff_finnews_b9 (symbol, dest_date)")
    runsql("drop table if exists ff_finnews_b10")
    runsql("create table ff_finnews_b10 as select symbol, dest_date, sum(power(0.8,greatest(dlag,0.01))*(bin+bin_float))+0.26*50 dense_sum, sum(power(0.8,greatest(dlag,0.01)))+0.26 dense_base \
           , ifnull((sum(power(0.8,greatest(dlag,0.01))*(bin+bin_float))+0.26*50)/(sum(power(0.8,greatest(dlag,0.01)))+0.26),50) dense_sense \
           , sum(power(0.8,greatest(dlag,0.01))*con_sense) condense_sum, sum(power(0.8,greatest(dlag,0.01)))+0.26 condense_base \
           , ifnull((sum(power(0.8,greatest(dlag,0.01))*con_sense))/(sum(power(0.8,greatest(dlag,0.01)))+0.26),0) condense_sense \
           from (select a.symbol, a.dest_date, b.bin, b.bin_float, round(TIMESTAMPDIFF(HOUR,published,dest_date)/24,2) dlag, con_sense from ff_finnews_b9 a left join ff_finnews_b8 b on a.symbol=b.symbol and DATEDIFF(dest_date, b.published) between 0 and 13) a group by symbol, dest_date")
    runsql("create index ff_finnews_b10_i1 on ff_finnews_b10 (symbol, dest_date)")
    runsql("drop table if exists ff_finnews_b11")
    runsql("create table ff_finnews_b11 as select a.*, a.dense_sense-b.dense_sense dense_diff, a.condense_sense-b.condense_sense condense_diff from \
           (select * from ff_finnews_b10 where dest_date = (select max(dest_date) from ff_finnews_b10) ) a, \
           (select * from ff_finnews_b10 where dest_date = (select max(dest_date) from ff_finnews_b10 where dest_date<(select max(dest_date) from ff_finnews_b10))) b \
           where a.symbol=b.symbol order by abs(dense_diff) desc")
    runsql("create index ff_finnews_b11_i1 on ff_finnews_b11 (symbol)")
    runsql("drop table if exists ff_finnews_b12")
    runsql("create table ff_finnews_b12 as select a.symbol, iex_id, published, dest_date, n_doc, n_up, n_down, con_sense, pos_sense, neg_sense, n_g_up, n_g_down, n_l_up, n_l_down, bin+bin_float bin, dense_sense, bin+bin_float-dense_sense bin_diff, con_sense-condense_sense con_sense_diff from ff_finnews_b8 a, ff_finnews_b10 b where a.symbol=b.symbol and date_add(dest_date,interval 1 day)=published_date")
    runsql("create index ff_finnews_b12_i1 on ff_finnews_b12 (symbol, dest_date)")
    runsql("create index ff_finnews_b12_i2 on ff_finnews_b12 (symbol, published)")
    runsql("create index ff_finnews_b12_i3 on ff_finnews_b12 (symbol, iex_id)")
    runsql("drop table if exists ff_finnews_b13")
    runsql("create table ff_finnews_b13 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) dbin, a.* from (select a.*, cnt from (select * from ff_finnews_b12) a, (select count(1) cnt from ff_finnews_b12) b order by bin_diff) a, (select @rn:=0) b")
    runsql("create index ff_finnews_b13_i1 on ff_finnews_b13 (dbin)")
    runsql("drop table if exists ff_finnews_b14")
    runsql("create table ff_finnews_b14 select a.dbin, a.min_con, ifnull(b.min_con,(select max(bin_diff) from ff_finnews_b13)) max_con from (select dbin dbin, min(bin_diff) min_con from ff_finnews_b13 group by dbin) a left join (select dbin-1 dbin, min(bin_diff) min_con from ff_finnews_b13 group by dbin-1) b on a.dbin=b.dbin")
    runsql("drop table if exists ff_finnews_b15")
    runsql("create table ff_finnews_b15 as select @rn:=@rn+1 rn, dest_date from (select * from ff_stock_date6m order by dest_date desc) a, (select @rn:=0) b")
    runsql("create index ff_finnews_b15_i1 on ff_finnews_b15 (dest_date)")
    runsql("drop table if exists ff_finnews_b16")
    runsql("create table ff_finnews_b16 as select a.*, c.dest_date dest_ref, a.dense_sense-c.dense_sense dense_diff, a.condense_sense-c.condense_sense condense_diff from ff_finnews_b10 a, ff_finnews_b15 b, ff_finnews_b10 c, ff_finnews_b15 d where a.symbol=c.symbol and a.dest_date=b.dest_date and c.dest_date=d.dest_date and b.rn+1=d.rn")
    runsql("create index ff_finnews_b16_i1 on ff_finnews_b16 (symbol, dest_date)")
    runsql("drop table if exists ff_finnews_b17")
    runsql("create table ff_finnews_b17 as select @rn:=@rn+1 rn, floor(@rn/(cnt+1)*100) dcon_bin, a.* from (select a.*, cnt from (select * from ff_finnews_b16) a, (select count(1) cnt from ff_finnews_b16) b order by condense_diff) a, (select @rn:=0) b")
    runsql("drop table if exists ff_finnews_b18")
    runsql("create table ff_finnews_b18 select a.dcon_bin, a.min_con, ifnull(b.min_con,(select max(condense_diff) from ff_finnews_b17)) max_con from (select dcon_bin dcon_bin, min(condense_diff) min_con from ff_finnews_b17 group by dcon_bin) a left join (select dcon_bin-1 dcon_bin, min(condense_diff) min_con from ff_finnews_b17 group by dcon_bin-1) b on a.dcon_bin=b.dcon_bin")
    runsql("drop table if exists ff_finnews_b19")
    runsql("create table ff_finnews_b19 as select rn, symbol, dest_date, dense_sense, condense_sense, dest_ref, dense_diff, condense_diff, a.dcon_bin+(condense_diff-b.min_con)/(b.max_con-b.min_con) dcon_bin from ff_finnews_b17 a, ff_finnews_b18 b where a.dcon_bin=b.dcon_bin")
    print("Done focus sensing "+time.strftime('%Y-%m-%d %H:%M:%S'))
    final_sense(is_incremental = False)
    file_cleanup()








# Incremental
def incremental_sense():
    print("Started incrementals "+time.strftime('%Y-%m-%d %H:%M:%S'))
    runsql("drop table if exists ff_finnews_d0")
    runsql("create table ff_finnews_d0 as select iex_id, any_value(published) published, any_value(iex_title) title, any_value(if(length(article)>length(iex_summary),article,iex_summary)) article from ff_finnews_iex where published>=date_sub(now() , interval 1 week) and greatest(length(article),length(iex_summary))>500 group by iex_id")
    runsql("create index ff_finnews_d0_i1 on ff_finnews_d0 (iex_id)")
    runsql("drop table if exists ff_finnews_d1")
    runsql("create table ff_finnews_d1 as select a.iex_id, a.title, a.article, b.iex_id dummy from ff_finnews_d0 a left join ff_finnews_b1 b on a.iex_id=b.iex_id having dummy is null")
    runsql("create index ff_finnews_d1_i1 on ff_finnews_d1 (iex_id)")
    A = fetch_rawsql("select iex_id, title, article from ff_finnews_d1")
    print("Done fetching incremental articles "+time.strftime('%Y-%m-%d %H:%M:%S'))
    documents, IEX_ids = doc_to_vec(A)
    print("Done cleaning incremental articles "+time.strftime('%Y-%m-%d %H:%M:%S'))
    TV = joblib.load(FILE_GLOBAL_TV_LST)
    tv = TV.transform(documents)
    T  = TV.get_feature_names()
    print("Done vectorizing incremental articles "+time.strftime('%Y-%m-%d %H:%M:%S'))

    dig_docs(A, IEX_ids, TV, tv, is_incremental=True)
    
    runsql("drop table if exists ff_finnews_d2")
    runsql("create table ff_finnews_d2 (symbol varchar(10), iex_id varchar(30), term varchar(10), model_type varchar(4), raw_sense float)")
    IEX_SYMBOL = fetch_rawsql("select a.symbol, a.iex_id, a.published from ff_finnews_iex a, ff_finnews_d1 b where a.iex_id=b.iex_id")
    ALL_LOCAL, _X, _y = focus_prep(IEX_SYMBOL, IEX_ids, tv, is_train=False)
    print("Done preparing incremental articles for scoring "+time.strftime('%Y-%m-%d %H:%M:%S'))
    for term in TERMS:
        focus_models(term, ALL_LOCAL, [], [], is_train=False)
        print("Done scoring incremental articles for " + term + " : "+time.strftime('%Y-%m-%d %H:%M:%S'))

    runsql("create index ff_finnews_d2_i1 on ff_finnews_d2 (iex_id)")
    runsql("drop table if exists ff_finnews_d3")
    runsql("create table ff_finnews_d3 as select a.*, published, title from ff_finnews_d2 a, ff_finnews_d0 b where a.iex_id=b.iex_id")
    runsql("create index ff_finnews_d3_i1 on ff_finnews_d3 (symbol, iex_id, model_type, term)")
    runsql("drop table if exists ff_finnews_d4")
    runsql("create table ff_finnews_d4 as select symbol, iex_id, model_type, any_value(published) published, sum(if(raw_sense>=0,1,0)) n_up, sum(if(raw_sense<0,1,0)) n_down \
           , max(raw_sense) max_sense, min(raw_sense) min_sense, sum(raw_sense)/(max(raw_sense)-min(raw_sense)) con_sense \
           , avg(if(raw_sense>=0,raw_sense,null)) pos_sense, avg(if(raw_sense<0,raw_sense,null)) neg_sense \
           from ff_finnews_d3 group by symbol, iex_id, model_type")
    runsql("create index ff_finnews_d4_i1 on ff_finnews_d4 (symbol, iex_id, model_type)")
    runsql("drop table if exists ff_finnews_d5")
    runsql("create table ff_finnews_d5 as select a.symbol, a.iex_id, any_value(published) published, any_value(b.n_doc) n_doc, sum(n_up) n_up, sum(n_down) n_down \
           , sum( if(model_type='L', 1/(1/log10(ifnull(b.n_doc,0)+2)+1) * con_sense, 1/log10(ifnull(b.n_doc,0)+2)/(1/log10(ifnull(b.n_doc,0)+2)+1) * con_sense) ) con_sense \
           , if(sum(n_up)>0,sum(n_up*pos_sense)/sum(n_up),null) pos_sense, if(sum(n_down)>0,sum(n_down*neg_sense)/sum(n_down),null) neg_sense \
           , sum(if(model_type='G',n_up,0)) n_g_up, sum(if(model_type='G',n_down,0)) n_g_down, sum(if(model_type='L',n_up,0)) n_l_up, sum(if(model_type='L',n_down,0)) n_l_down \
           from ff_finnews_d4 a left join ff_finnews_b4 b on a.symbol = b.symbol group by symbol, iex_id")
    runsql("drop table if exists ff_finnews_d6")
    runsql("create table ff_finnews_d6 as select ifnull(b.bin,if(con_sense>max_max,99,0)) bin , a.* from ff_finnews_d5 a inner join (select max(max_con) max_max, min(min_con) min_min from ff_finnews_b7) c left join ff_finnews_b7 b on a.con_sense>b.min_con and a.con_sense<=b.max_con")
    runsql("drop table if exists ff_finnews_d7")
    runsql("create table ff_finnews_d7 as select a.*, date(published) published_date, (con_sense-b.min_con)/(b.max_con-b.min_con) bin_float from ff_finnews_d6 a, ff_finnews_b7 b where a.bin=b.bin")
    runsql("drop table if exists ff_finnews_d8")
    runsql("create table ff_finnews_d8 as select a.symbol, iex_id, published, dest_date, n_doc, n_up, n_down, con_sense, pos_sense, neg_sense, n_g_up, n_g_down, n_l_up, n_l_down, bin+bin_float bin, dense_sense, bin+bin_float-dense_sense bin_diff, con_sense-condense_sense con_sense_diff from ff_finnews_d7 a, ff_finnews_b11 b where a.symbol=b.symbol")
    print("Done incremental sensing "+time.strftime('%Y-%m-%d %H:%M:%S'))
    final_sense(is_incremental = True)


def file_cleanup():
    files = os.listdir('model')
    count = 0
    for f in files:
        if 'global' not in f and 'latest' not in f and enow.strftime("%Y%U") not in f:
            os.remove(os.path.join('model', f))
            count += 1
    print("Cleaned up " + str(count) + " model files, keeping " + str(len(files)-count))
    print("Done model file clean up "+time.strftime('%Y-%m-%d %H:%M:%S'))



if __name__ == '__main__':
    # test any of the below locally
    #build_sense()
    incremental_sense()
    #file_cleanup()



