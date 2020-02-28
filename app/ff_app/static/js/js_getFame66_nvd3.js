function draw66(data, symbol, call66=true){
    nv.addGraph(function() {
        var chart = nv.models.discreteBarChart()
            .x(function(d) { return d.label })
            .y(function(d) { return d.value/100 })
            .margin({"left":2,"right":2,"top":2,"bottom":2})
            .valueFormat(d3.format('+,.2%'))
            .showYAxis(false).showXAxis(false)
            ;
        chart.color(function(d){
            var dt = 250/(1+Math.pow(Math.E,-0.08*d.value)) - 125;
            var r = (dt<0)? ("0"+((180-dt/2)|0).toString(16)).slice(-2).toUpperCase() : "00";
            var g = (dt<0)? "00" : ("0"+((128+dt)|0).toString(16)).slice(-2).toUpperCase();
            return "#"+r+g+"00"
        });
        chart.tooltip.contentGenerator(function(d){
            return '<p><b>' + ((d.data.value<0)?"":"+") + d.data.value + '%</b> in the past <b>' + d.data.label +'</b></p>';
        });
        if (call66) {
            chart.discretebar.dispatch.on("elementClick", function(e) {
                window.open('/fb/f66/'+symbol+'/', '_blank');
            })
        }
        d3.select('#chart-' + symbol.replace('.','-') + ' svg')
            .datum([data])
            .transition().duration(500)
            .call(chart);
        nv.utils.windowResize(chart.update);
        return chart;
    });
}

function getFame66(symbol, data=0, call66=true){
    if (!data) {
        $.getJSON('/api/v1/fame66/'+symbol+'/', function(data) {
            draw66(data, symbol, call66);
        });
    } else {
        draw66(data, symbol, call66);
    }
};
