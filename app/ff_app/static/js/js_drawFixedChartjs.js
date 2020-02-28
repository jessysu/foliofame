function drawFixed(symbol){
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/chart/1d', function(dd) {
        $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/quote', function(dp) {
            var previousClose = dp.previousClose;
            var V = [];
            var U = [];
            var T = [];
            var d1 = moment.utc().format().split('T')[0] + " ";
            var minX = (moment(d1+"09:30").unix() )*1000;
            var maxX = (moment(d1+"15:59").unix() )*1000;
            var minY = 0.99 * previousClose;
            var maxY = 1.01 * previousClose;
            for (i in dd) {
                var ds = d1+dd[i]["minute"];
                var t = (moment(ds).unix() )*1000;
                var v = dd[i]["marketAverage"];
                if ( v <= 0 ) {continue;}
                V.push({t:t, y:v});
                minY = (minY < 0.99*v ? minY : 0.99*v);
                maxY = (maxY > 1.01*v ? maxY : 1.01*v);
            }
            var ctx = document.getElementById("chart-fix1d-chartjs");
            var line = new Chart(ctx, {
                type: "line",
                data: {
                    datasets: [{
                        data: V,
                        fill: false,
                        pointHitRadius: 5,
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
                            colour: '#bbb',
                            type: "dashed",
                            label: "Previous Close"
                        },
                        belowThresholdColour: [
                            'rgb(222,22,22)'
                        ]
                    }
                }
            });
            // chart.js candlesticks
            /*
            $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/chart/1m', function(dd) {
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
                var ctx = document.getElementById("chart-fix1m-chartjs");
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
            */
        });
    });
};

function drawSense(ctx, V, min=0, max=100, midpoint=50){
    var line = new Chart(ctx, {
        type: "line",
        data: {
            datasets: [{
                data: V,
                fill: false,
                pointHitRadius: 5,
                borderColor: 'rgb(22,222,22)',
            }],
        },
        options: {
            //elements: { point: {radius: 0}}, //hide marker
        	maintainAspectRatio: false,
            legend: {display: false},
            scales: {
                yAxes: [{
                    ticks: {suggestedMin:min, suggestedMax:max}, 
                    //gridLines: {}
                }],
                xAxes: [{
                    type: 'time',
                }]
            },
            tooltips: {
                mode: 'index',
            },
            bands: {
                yValue: midpoint,
                bandLine: {
                    stroke: 1,
                    colour: '#bbb',
                    type: "dashed",
                    label: "Neutral"
                },
                belowThresholdColour: [
                    'rgb(222,22,22)'
                ]
            }
        }
    });
}


function drawPlain(ctx, V, min=0){
    var line = new Chart(ctx, {
        type: "line",
        data: {
            datasets: [{
                data: V,
                fill: false,
                pointHitRadius: 5,
                borderColor: 'rgb(123,123,123)',
            }],
        },
        options: {
        	maintainAspectRatio: false,
            legend: {display: false},
            scales: {
                xAxes: [{
                    type: 'time',
                }]
            },
            tooltips: {
                mode: 'index',
            },
        }
    });
}