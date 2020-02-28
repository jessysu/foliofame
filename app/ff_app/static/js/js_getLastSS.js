function getLastSS(symbol) {
	var sym_id = symbol.replace(".","-");
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/quote', function(data) {
        $("#recent-"+sym_id+"-color").attr("class", ((data.changePercent<0) ? "btn btn-sm btn-danger":"btn btn-sm btn-success"));
        $("#recent-"+sym_id+"-chp").text(((data.changePercent<0) ? " ":" +") + Math.round(data.changePercent*10000)/100+'%');
    });
}