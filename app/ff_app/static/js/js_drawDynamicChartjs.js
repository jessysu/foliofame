function drawDynamic(symbol){
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/chart/dynamic', function(d) {
        $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/quote', function(dp) {
            var previousClose = dp.previousClose;
            var r = d["range"];
            var dd = d["data"];
            var V = [];
            var U = [];
            var T = [];
            var minY, maxY, minX, maxX, d1;
            if (r == "1d" || r == "today") {
                d1 = moment.utc().format().split('T')[0] + " ";
                minX = (moment(d1+"09:30").unix() )*1000;
                maxX = (moment(d1+"15:59").unix() )*1000;
            }
            var minY = 0.99 * previousClose;
            var maxY = 1.01 * previousClose;
            for (i in dd) {
                var ds = (r == "1d" || r == "today" ? d1+dd[i]["minute"] : dd[i]["date"]);
                var t = (moment(ds).unix() )*1000;
                var v = (r == "1d" || r == "today" ? dd[i]["marketAverage"] : dd[i]["close"]);
                if ( v <= 0 ) {continue;}
                if (r == "1d" || r == "today") {
                	V.push({t:t, y:v});
                } else {
                    V.push({t:t, o:dd[i]["open"], h:dd[i]["high"], l:dd[i]["low"], c:dd[i]["close"]});
                }
                minY = (minY < 0.99*v ? minY : 0.99*v);
                maxY = (maxY > 1.01*v ? maxY : 1.01*v);
            }
            var ctx = document.getElementById("chart-dynamic-chartjs");
            if (r == "1d" || r == "today") {
                var line = new Chart(ctx, {
                    type: "line",
                    data: {
                        datasets: [{
                            data: V,
                            fill: false,
                            borderColor: 'rgb(22,222,22)',
                        }],
                    },
                    options: {
                        elements: { point: {radius: 0}}, //hide marker
                    	maintainAspectRatio: false,
                        legend: {display: false},
                        scales: {
                            yAxes: [{
                                ticks: {suggestedMin:minY, suggestedMax:maxY}, 
                                gridLines: {}
                            }],
                            xAxes: [{
                                type: 'time',
                                time: {
                                    unit: 'hour',
                                    min: minX, 
                                    max: maxX
                                },
                            }]
                        },
                        tooltips: {
                            mode: 'index',
                        },
                        bands: {
                            yValue: previousClose,
                            bandLine: {
                                stroke: 1,
                                colour: 'rgb(22,22,22)',
                                type: "dashed",
                                label: "Previous Close"
                            },
                            belowThresholdColour: [
                                'rgb(222,22,22)'
                            ]
                        }
                    }
                });
            } else {
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
            }
        });
	});
};
