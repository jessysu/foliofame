function getEventList(symbol, I_threshold=90, head="chg") {
    $.getJSON('/api/v1/famebits/chg/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/chg/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-warning py-0 ml-1 my-1">'+d.move+' <span class="text-' + (d.chg<0?'danger':'success') + '">' + Math.round(Math.abs(d.chg)*10000)/100+'%</span> <i class="fa fa-angle-double-right"></i></a>');
            if (head=="chg") {
                $("#maintext-"+symbol.replace(".","-")+"-head").html(Math.round(Math.abs(d.chg)*10000)/100+'% '+(d.chg<0 ? "loss":"gain"));
            }
        }
    });
    $.getJSON('/api/v1/famebits/cfp/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/cfp/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-warning py-0 ml-1 my-1">'+d.target+" "+d.move+' <i class="fa fa-angle-double-right"></i></a>');
            if (head=="cfp") {
                $("#maintext-"+symbol.replace(".","-")+"-head").html(d.qmove);
            }
        }
    });
    $.getJSON('/api/v1/famebits/vol/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/vol/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-warning py-0 ml-1 my-1">'+Math.round(d.z*10)/10+'&sigma; '+d.rarity+' vol <i class="fa fa-angle-double-right"></i></a>');
            if (head=="vol") {
                $("#maintext-"+symbol.replace(".","-")+"-head").html(Math.round(d.z*10)/10+'&sigma; vol');
            }
        }
    });
    $.getJSON('/api/v1/famebits/pfl/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/pfl/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-warning py-0 ml-1 my-1">'+d.hl_ratio+'% '+d.rarity+' flux <i class="fa fa-angle-double-right"></i></a>');
            if (head=="pfl") {
                $("#maintext-"+symbol.replace(".","-")+"-head").html(d.hl_ratio+'% flux');
            }
        }
    });
};
