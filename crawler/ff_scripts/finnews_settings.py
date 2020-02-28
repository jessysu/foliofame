# -*- coding: utf-8 -*-
"""
Created on Wed Apr 24 21:58:54 2019

@author: jsu
"""


import datetime, pytz
import sys
from util_mysql import table_exist



FORCE_RETRAIN = False

utc = pytz.timezone('UTC')
eastern = pytz.timezone('US/Eastern')
enow = utc.localize(datetime.datetime.utcnow()).astimezone(eastern)



N_KEYWORDS = 20
N_SENTENCES = 5

TERMS = ['1d','2d','1w','2w','1m','2m']



# run nltk.download in docker build
from nltk import pos_tag, word_tokenize
#nltk.download('punkt')
#nltk.download('averaged_perceptron_tagger')
from nltk.stem import WordNetLemmatizer
#nltk.download('wordnet')
wnl = WordNetLemmatizer()


def penn2morphy(penntag):
    """ Converts Penn Treebank tags to WordNet. """
    morphy_tag = {'NN':'n', 'JJ':'a', 'VB':'v', 'RB':'r'}
    try:
        return morphy_tag[penntag[:2]]
    except:
        return 'n' 
def lemmatize_sent(text): 
    # Text input is string, returns lowercased strings.
    return [wnl.lemmatize(word.lower(), pos=penn2morphy(tag)) 
            #for word, tag in pos_tag(text.split())]
            for word, tag in pos_tag(word_tokenize(text))]



class LemmaTokenizer(object):
    def penn2morphy(penntag):
        """ Converts Penn Treebank tags to WordNet. """
        morphy_tag = {'NN':'n', 'JJ':'a', 'VB':'v', 'RB':'r'}
        try:
            return morphy_tag[penntag[:2]]
        except:
            return 'n' 
    def __init__(self):
        self.wnl = WordNetLemmatizer()
    def __call__(self, doc):
        #return [self.wnl.lemmatize(t) for t in word_tokenize(doc)]
        return [self.wnl.lemmatize(word.lower(), pos=penn2morphy(tag)) for word, tag in pos_tag(word_tokenize(doc))]

def assure_folder(filename):
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise



if not table_exist("ff_finnews_iex"):
    print("Missing required table: ff_finnews_iex")
    sys.exit()


