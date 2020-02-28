

STYPE_LIST = [{'ftype':'ahd', 'name':'Informers', 'short':'<i class="fas fa-lightbulb fa-fw"></i>', 'desc':"Stocks with recurring patterns", 'stype': 'ahd', 'sclause':"", 'sch': 'b'},
              {'ftype':'cfp', 'name':'Breakers', 'short':'<i class="far fa-calendar fa-fw"></i>', 'desc':"Stocks above 90-day high or below 90-day low", 'stype':'cfp', 'sclause':"", 'sch': 'b'},
              {'ftype':'cbk', 'name':'Toppers', 'short':'<i class="far fa-calendar-plus fa-fw"></i>', 'desc':"Stocks above 90-day high", 'stype': 'cfp', 'sclause':"and context like '%high%'", 'sch': 'u'},
              {'ftype':'fbk', 'name':'Divers', 'short':'<i class="far fa-calendar-minus fa-fw"></i>', 'desc':"Stocks below 90-day low", 'stype':'cfp', 'sclause':"and context like '%low%'", 'sch': 'd'},
              {'ftype':'chg', 'name':'Changers', 'short':'<i class="fas fa-sort fa-fw"></i>', 'desc':"Stocks with huge price change", 'stype': 'chg', 'sclause':"", 'sch': 'b'},
              {'ftype':'gnr', 'name':'Gainers', 'short':'<i class="fas fa-plus fa-fw"></i>', 'desc':"Stocks with big gain", 'stype':'chg', 'sclause':"and changePct>0", 'sch': 'u'},
              {'ftype':'lsr', 'name':'Losers', 'short':'<i class="fas fa-minus fa-fw"></i>', 'desc':"Stocks with big loss", 'stype':'chg', 'sclause':"and changePct<0", 'sch': 'd'},
              {'ftype':'vol', 'name':'Volumers', 'short':'<i class="fas fa-database fa-fw"></i>', 'desc':"Stocks with large volume", 'stype':'vol', 'sclause':"", 'sch': 'b'},
              {'ftype':'pfl', 'name':'Sweepers', 'short':'<i class="fas fa-icicles fa-fw"></i>', 'desc':"Stocks fluctuate", 'stype':'pfl', 'sclause':"", 'sch': 'b'},
              {'ftype':'f66', 'name':'Performers', 'short':'<i class="fas fa-thumbs-up fa-fw"></i>', 'desc':"Stocks performed well", 'stype':'f66', 'sclause':"", 'sch': ''},
              ]

STYPE_LIST_MAX_ROWS = 100

DME_SCOPES = [
              {'scope':'mua', 'name':'>MA+', 'desc':'closed above moving averages of the watched windows', 'api_url':'/api/v1/famebits/dme/$SS/6/mua/'},
              {'scope':'extrema', 'name':'Extrema', 'desc':'daily high above ceilings or daily low below floors', 'api_url':'/api/v1/famebits/dme/$SS/3/b/'},
              {'scope':'close', 'name':'Breaking', 'desc':'closed above ceilings or below floors', 'api_url':'/api/v1/famebits/dme/$SS/$NS/bc/'},
              {'scope':'mda', 'name':'<MA+', 'desc':'closed below moving averages of the watched windows', 'api_url':'/api/v1/famebits/dme/$SS/6/mda/'},
              {'scope':'mu90', 'name':'>MA90', 'desc':'closed above 90-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/mu/90/'},
              {'scope':'md90', 'name':'<MA90', 'desc':'closed below 90-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/md/90/'},
              {'scope':'mu7', 'name':'>MA7', 'desc':'closed above 7-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/mu/7/'},
              {'scope':'md7', 'name':'<MA7', 'desc':'closed below 7-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/md/7/'},
              {'scope':'mu30', 'name':'>MA30', 'desc':'closed above 30-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/mu/30/'},
              {'scope':'md30', 'name':'<MA30', 'desc':'closed below 30-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/md/30/'},
              {'scope':'mu180', 'name':'>MA180', 'desc':'closed above 180-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/mu/180/'},
              {'scope':'md180', 'name':'<MA180', 'desc':'closed below 180-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/md/180/'},
              #{'scope':'mu14', 'name':'>MA14', 'desc':'closed above 14-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/mu/14/'},
              #{'scope':'mu60', 'name':'>MA60', 'desc':'closed above 60-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/mu/60/'},
              #{'scope':'md14', 'name':'<MA14', 'desc':'closed below 14-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/md/14/'},
              #{'scope':'md60', 'name':'<MA60', 'desc':'closed below 60-day moving average', 'api_url':'/api/v1/famebits/dme/$SS/$NS/md/60/'},
              ]


USER_PREFS = [
              {'item':'home_block', 'url':'hblk', 'choices':['txt','btn'], 'type':'switch', 'purpose':'homepage view', 'category':'UI rendering'}
            ]

BLOCKED_STOCKS = ['GOOGL','DISCA']
