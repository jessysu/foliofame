function getFame66(symbol){
    $.getJSON('/api/v1/fame66/'+symbol+'/', function(data) {
        var ctx = document.getElementById("chart-"+symbol.replace('.','-'));
        var labels = [];
        var values = [];
        var colors = [];
        var mn = 0;
        var mx = 0;
        for (i in data.values) {
            labels.push(data.values[i].label);
            values.push(data.values[i].value);
            var dt = 250/(1+Math.pow(Math.E,-0.08*data.values[i].value)) - 125;
            var r = (dt<0)? ((180-dt/2)|0) : 0;
            var g = (dt<0)? 0 : ((128+dt)|0);
            colors.push("rgb("+r+","+g+",0)");
            if (data.values[i].value < mn) {mn = data.values[i].value;}
            if (data.values[i].value > mx) {mx = data.values[i].value;}
        }
        var all_data = {labels:labels, datasets:[{data:values, backgroundColor:colors}]};
        var bar = new Chart(ctx, {
            type: "bar",
            data: all_data,
            options: {
                legend: {display:false},
                maintainAspectRatio: false,
                fullWidth: true,
                scales: {
                    yAxes: [{ticks:{display:false, min:mn, max:mx}, gridLines:{drawBorder:false,drawTicks:false,display:false}}],
                    xAxes: [{ticks:{display:false}, gridLines:{drawBorder:false,drawTicks:false,display:false}}]
                },
                tooltips: {
                    displayColors: false,
                    callbacks: {
                        label: function(tooltipItem, data) {
                            return data['labels'][tooltipItem['index']] + ": " + (data['datasets'][0]['data'][tooltipItem['index']]).toFixed(2) + "%";
                        },
                        title: function(tooltipItem, data) {return;}
                    }
                }
            }
        });
	});
};
