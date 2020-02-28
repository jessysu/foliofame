function getFame66_w52(symbol){
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/quote', function(d) {
        var cp = d.latestPrice;
        var mn = d.week52Low;
        var mx = d.week52High;
        $.getJSON('/api/v1/fame66/w52/'+symbol+'/', function(data) {
            var ctx = document.getElementById("chart-w52-"+symbol.replace('.','-'));
            var color = Chart.helpers.color;
            data['backgroundColor'] = color('rgb(54,162,235)').alpha(0.5).rgbString();
            data['datasets'][0]['data'].push(cp);
            data['labels'].push('now');
            var line = new Chart(ctx, {
                type: "line",
                data: data,
                options: {
                    legend: {display:false},
                    maintainAspectRatio: false,
                    fullWidth: true,
                    scales: {
                        yAxes: [{ticks:{display:false, min:mn, max:mx, stepSize:(mx-mn)/4}, gridLines:{drawBorder:false,drawTicks:false}}],
                        xAxes: [{ticks:{display:false}, gridLines:{display:false}}]
                    },
                    tooltips: {
                        displayColors: false,
                        callbacks: {
                            label: function(tooltipItem, data) {
                                return data['labels'][tooltipItem['index']] + ": " + (data['datasets'][0]['data'][tooltipItem['index']]).toFixed(2);
                            },
                            title: function(tooltipItem, data) {return;}
                        }
                    }
                }
            });
        });
    });
};
