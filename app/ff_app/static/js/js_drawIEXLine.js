
// highcharts version
function drawIEX(symbol, obj, range="5y", grouped=true){
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/chart/'+range, function(data) {
    	var ohlc = [],
            volume = [],
            c = []
            dataLength = data.length,
            groupingUnits = [['week', [1]],[
                              'month', [1, 2, 3, 4, 6]
                              ]],
            i = 0;

        for (i; i < dataLength; i += 1) {
            const diff = data[i].close - data[i].open;
            const color = diff > 0 ? 'green' : (diff === 0 ? 'black' : 'red');
            const ts = new Date(data[i].date).getTime();
            //ohlc.push([ts, data[i].open, data[i].high, data[i].low, data[i].close]);
            c.push([ts, data[i].close]);
            volume.push([ts, data[i].volume]);
        }
        

        Highcharts.stockChart(obj, {
            yAxis: [{
                labels: {
                    align: 'left'
                },
                height: '80%',
                resize: {
                    enabled: true
                }
            }, {
                labels: {
                    align: 'left'
                },
                top: '80%',
                height: '20%',
                offset: 0
            }],
            rangeSelector: {
                selected: 1,
                inputEnabled: false,
                buttonTheme:{display: 'none'},
                labelStyle:{display: 'none'}
            },
            series: [{
                name: symbol,
                data: c
            }, {
                type: 'column',
                name: 'Volume',
                data: volume,
                yAxis: 1
            }],
            responsive: {
                rules: [{
                    condition: {
                        maxWidth: 800
                    },
                    chartOptions: {
                        rangeSelector: {
                            inputEnabled: false
                        }
                    }
                }]
            }
        });
    });
};

// chart.js version
/*
function drawIEXCandle(symbol, id, range="6m"){
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/chart/'+range, function(dd) {
        var V = [];
        var U = [];
        var T = [];
        for (i in dd) {
            var ds = dd[i]["date"];
            var t = (moment(ds).unix() )*1000;
            var v = dd[i]["close"];
            if ( v <= 0 ) {continue;}
            V.push({t:t, o:dd[i]["open"], h:dd[i]["high"], l:dd[i]["low"], c:dd[i]["close"]});
        }
        var ctx = document.getElementById(id);
        var candelstick = new Chart(ctx, {
            type: "candlestick",
            data: {
                datasets: [{
                    data: V,
                    fractionDigitsCount: 2,
                }],
            },
            options: {
                maintainAspectRatio: false,
                legend: {display: false},
                tooltips: {
                    position: 'nearest',
                    mode: 'index',
                }
            }
        });
    });
};
*/