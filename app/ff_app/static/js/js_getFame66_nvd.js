function getFame66(symbol, txtcolor=""){
    $.getJSON('/api/v1/fame66/'+symbol+'/', function(data) {
        nv.addGraph(function() {
            var chart = nv.models.discreteBarChart()
                .x(function(d) { return d.label })
                .y(function(d) { return d.value/100 })
                .margin({"left":5,"right":5,"top":20,"bottom":60})
                .valueFormat(d3.format('+,.2%'))
                .staggerLabels(true).showYAxis(false)
                .showValues(true);
            chart.color(function(d){
                var dt = 250/(1+Math.pow(Math.E,-0.08*d.value)) - 125;
                var r = (dt<0)? ("0"+((180-dt/2)|0).toString(16)).slice(-2).toUpperCase() : "00";
                var g = (dt<0)? "00" : ("0"+((128+dt)|0).toString(16)).slice(-2).toUpperCase();
                return "#"+r+g+"00"
            });
            chart.tooltip.contentGenerator(function(d){
                return '<p><b>' + ((d.data.value<0)?"":"+") + d.data.value + '%</b> in the past <b>' + d.data.label +'</b></p>';
            });
            d3.select('#chart-fame66-exp svg')
                .datum([data])
                .transition().duration(500)
                .call(chart);
            if (txtcolor) {
                d3.selectAll('.nvd3 text').style('fill',txtcolor);
            }
            nv.utils.windowResize(chart.update);
            return chart;
        });
	});
};
