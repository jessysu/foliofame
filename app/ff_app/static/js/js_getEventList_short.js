function getEventList(symbol, I_threshold=90, head="chg", color="secondary") {
	$.getJSON('/api/v1/famebits/chg/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            var tt = d.move + ' ' + Math.round(Math.abs(d.chg)*10000)/100 + '% in share price';
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/chg/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-'+color+' py-0 mr-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '"><span class="text-' + (d.chg<0?'danger">':'success">+') + Math.round(d.chg*10000)/100+'%</span></a>');
            $('[data-toggle="tooltip"]').tooltip();
            if (head=="chg") {
                $("#maintext-"+symbol.replace(".","-")+"-head").append((Math.abs(d.chg*100)).toPrecision(2)+'% '+(d.chg<0 ? "loss":"gain"));
            }
        }
    });
    $.getJSON('/api/v1/famebits/cfp/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            var tt = d.target + " " + d.move;
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/cfp/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-'+color+' py-0 mr-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+d.qmove+'</a>');
            $('[data-toggle="tooltip"]').tooltip();
            if (head=="cfp") {
                $("#maintext-"+symbol.replace(".","-")+"-head").append(d.qmove);
            }
        }
    });
    $.getJSON('/api/v1/famebits/vol/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            var tt = Math.round(Math.abs(d.z)*10)/10 + ' standard deviations ' + (d.z<0?"below":"above") + " average trading volume";
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/vol/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-'+color+' py-0 mr-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+Math.round(d.z*10)/10+'&sigma; vol</a>');
            $('[data-toggle="tooltip"]').tooltip();
            if (head=="vol") {
                $("#maintext-"+symbol.replace(".","-")+"-head").append((d.z).toPrecision(2)+'&sigma; vol');
            }
        }
    });
    $.getJSON('/api/v1/famebits/pfl/'+symbol+'/', function(d) {
        if (d.I >= I_threshold) {
            var tt = d.hl_ratio+'% '+d.rarity+' flux over previos closing price';
            $("#maintext-"+symbol.replace(".","-")+"-event").append('<a href="/fb/pfl/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-'+color+' py-0 mr-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+d.hl_ratio+'% flux</a>');
            $('[data-toggle="tooltip"]').tooltip();
            if (head=="pfl") {
                $("#maintext-"+symbol.replace(".","-")+"-head").append((d.hl_ratio).toPrecision(2)+'% flux');
            }
        }
    });
    $.getJSON('/api/v1/famebits/ahd/'+symbol+'/', function(d) {
        if (d.I >= 0.5 && d.times > 1 && d.target == 'self') {
            var tt = "After the day " + d.td + ", " + d.times + " out of " + d.outof + " times " + symbol +" went " + (d.chgSign=='-'?'down':'up') + " in " + d.term + ", for an average of " + d.chg + "%";
            $("#maintext-"+symbol.replace(".","-")+"-ahead").append('<a href="/fb/ahd/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-'+color+' py-0 mr-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">' + d.term_short + ' <span class="text-' + (d.chgSign=='-'?'danger':'success') + '">' + d.chgSign + d.chg + '%</span> (x' + d.times + ')</a>');
            $('[data-toggle="tooltip"]').tooltip();
            if (head=="ahd") {
                $("#maintext-"+symbol.replace(".","-")+"-head").append(d.times+' / '+d.outof);
            }
        }
    });
};
