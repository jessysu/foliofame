
// highcharts version
function drawIEX(symbol, obj, range="5y", grouped=true){
    const redraw = (event) => {
        const chartTarget = event.target;
        const candlesticks = chartTarget.series[0].points;
        const volumeBars = chartTarget.series[1].points;
        for (let i = 0; i < candlesticks.length; i++) {
            const candle = candlesticks[i];
            const volumeBar = volumeBars[i];
            if (candle.close > candle.open) {
                const color = 'green';
                volumeBar.graphic.css({color: color});
                candle.graphic.css({color: color});
            } else if (candle.close < candle.open) {
                const color = 'red';
                volumeBar.graphic.css({color: color});
                candle.graphic.css({color: color});
            }
        }
    };

    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/chart/'+range, function(data) {
        var ohlc = [],
            volume = [],
            dataLength = data.length,
            groupingUnits = [['week', [1]],[
                              'month', [1, 2, 3, 4, 6]
                              ]],
            i = 0;

        for (i; i < dataLength; i += 1) {
            const diff = data[i].close - data[i].open;
            const color = diff > 0 ? 'green' : (diff === 0 ? 'black' : 'red');
            const ts = new Date(data[i].date).getTime();
            ohlc.push([ts, data[i].open, data[i].high, data[i].low, data[i].close]);
            volume.push([ts, data[i].volume]);
        }

        Highcharts.stockChart(obj, {
        	chart: {
                events: {render: redraw}
            },
            rangeSelector: {
                selected: 1,
                inputEnabled: false,
                buttonTheme:{display: 'none'},
                labelStyle:{display: 'none'}
            },
            plotOptions: {
                candlestick: {
                    lineColor: '#777'
                }
            },
            yAxis: [{
                labels: {
                    align: 'right',
                    x: -3
                },
                title: {text: 'OHLC'},
                height: '60%',
                lineWidth: 2,
                resize: {enabled: true}
            }, {
                labels: {
                    align: 'right',
                    x: -3
                },
                title: {text: 'Volume'},
                top: '65%',
                height: '35%',
                offset: 0,
                lineWidth: 2
            }],
            tooltip: {split: true},
            series: [{
                type: 'candlestick',
                turboThreshold: 0,
                name: symbol,
                data: ohlc,
                dataGrouping: {
                    units: grouped ? groupingUnits : {}
                }
            }, {
                type: 'column',
                turboThreshold: 0,
                name: 'Volume',
                data: volume,
                yAxis: 1,
                dataGrouping: {
                    units: grouped ? groupingUnits : {}
                }
            }]
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