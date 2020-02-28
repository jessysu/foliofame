function procNews(symbol, data, n=10) {
    $("#badge-news-"+symbol.replace(".","-")).text(data.length);
    var da = moment();
    var db = moment(data[0].datetime).format("YYYY-MM-DD HH:mm");
    if (da.diff(db,'days',true) < 1.0){
        $('#badge-news-'+symbol.replace(".","-")).removeClass("badge-secondary");
        $('#badge-news-'+symbol.replace(".","-")).addClass("badge-danger");
    }
    for (d in data) {
        var dd = moment(data[d].datetime).format("M/D ha z");
        var dt = data[d].headline;
        var str = '<span class="badge badge-secondary mb-1 d-none d-md-inline-block">'+data[d].source+'</span> ';
        str = str + '<a class="text-secondary" href="/re?s='+symbol+'&v=home&t=iexnews&u=' + data[d].url + '" target="_blank">' + data[d].headline + '</a>';
        //str = '<span class="list-group-item list-group-item-action flex-column clearfix"><small class="p-1">' + dd + str + '</small></span>';
        str = '<div class="hvr3 mt-2"><small class="p-1"><b>' + dd + '</b>' + str + '</small></div>';
        $("#news-"+symbol.replace(".","-")).append(str);
        if (d>=n) {break;}
    }
}

function getNews(symbol, n=5) {
    if (n>0) {
	$.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/news/last/'+n, function(data) {
	    procNews(symbol, data);
    });
    };
};
