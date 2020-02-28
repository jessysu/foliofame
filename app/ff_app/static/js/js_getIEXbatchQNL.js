var etnow = moment(new Date()).tz("America/Toronto");
var ethm = etnow.format("HHmm");
var Sclose = {};
var SCP = {};
function getLogo(symbol) {
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/logo', function(data) {
        $("#maintext-"+symbol.replace('.','-')+"-logo").html('<img class="img-fluid img-thumbnail mx-auto d-block gs" style="max-height:10vh;" src="'+data.url+'" onerror="if (this.src!=\'/static/img/err.png\') this.src=\'/static/img/err.png\'"/>');
    });
};
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
        str = '<div class="hvrb mt-2"><small class="p-1"><b>' + dd + '</b>' + str + '</small></div>';
        $("#news-"+symbol.replace(".","-")).append(str);
        if (d>=n-1) {break;}
    }
}
function getQN(sstr, n_news=2) {
    $.getJSON('https://api.iextrading.com/1.0/stock/market/batch?symbols='+sstr+'&types=quote,news', function(bdata) {
    	for (d in bdata) {
            var data = bdata[d].quote;
    		var symbol = data.symbol;
            var t = "";
            if (data.changePercent>=0) {t="+"};
            $("#maintext-"+symbol.replace('.','-')+"-close").text("$"+(data.close).toFixed(2));
            $("#maintext-"+symbol.replace('.','-')+"-name").text(data.companyName);
            $("#maintext-"+symbol.replace('.','-')+"-chp").addClass(((data.changePercent<0) ? "scr":"scg"));
            $("#maintext-"+symbol.replace('.','-')+"-chp").text(t+Math.round(data.changePercent*10000)/100+'%');
            $("#maintext-"+symbol.replace('.','-')+"-ytd").addClass(((data.ytdChange<0) ? "scr":"scg"));
            $("#maintext-"+symbol.replace('.','-')+"-ytd").text(((data.ytdChange<0) ? "":"+") + Math.round(data.ytdChange*10000)/100+'%');
            $("#maintext-"+symbol.replace('.','-')+"-cap").html('$'+intToString(data.marketCap));
            $("#maintext-"+symbol.replace('.','-')+"-capchp").attr("class", ((data.changePercent<0) ? "scr":"scg"));
            $("#maintext-"+symbol.replace('.','-')+"-capchp").text(t+"$"+ intToString(Math.round(data.marketCap*( 1 - 1/(1+data.changePercent)))) );
            if (data.week52Low && data.week52High) {$("#maintext-"+symbol.replace('.','-')+"-w52").text('$'+(data.week52Low).toFixed(2)+'~$'+(data.week52High).toFixed(2));}
            if (data.peRatio) {$("#maintext-"+symbol.replace('.','-')+"-pe").text(data.peRatio);}
            Sclose[symbol] = data.previousClose;
            SCP[symbol] = data.calculationPrice;
            procNews(symbol, bdata[d].news, n_news);
        }
    });
};
function getSocket(sstr) {
	if ( etnow.isoWeekday() < 6 && ethm < "2030" && ethm > "0830") {
	    //console.log("Start socket");
	    var socket = io.connect('https://ws-api.iextrading.com/1.0/tops');
	    socket.on('connect', function () {
	        socket.emit('subscribe', sstr);
	        //console.log('Connection! in socket on');
	    });
	    function logScreen(jn) {
	        var j = JSON.parse(jn);
	        var d = moment(new Date(j.lastUpdated)).tz("America/Toronto");
	        var dd = d.format("YYYY-MM-DD");
	        var hm = d.format("HHmm");
	        if (hm < "2030" && SCP[j.symbol] != "close" && j.lastSalePrice > 0) {
	            var c = j.lastSalePrice;
	            var b = Sclose[j.symbol];
	            $("#maintext-"+j.symbol.replace('.','-')+"-chp").addClass(c<b ? "scr":"scg");
	            $("#maintext-"+j.symbol.replace('.','-')+"-chp").removeClass(c<b ? "scg":"scr");
	            $("#maintext-"+j.symbol.replace('.','-')+"-chp").text((c<b ? "":"+") + Math.round((c-b)/b*10000)/100 + "%");
	            $("#maintext-"+j.symbol.replace('.','-')+"-close").text("$"+c.toFixed(2));
	        }
	    }
	    socket.on('message', logScreen);
	}
}
