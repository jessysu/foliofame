function getBakingItems(obj, symbol, D, I_th=90) {
    var t = '';
    var tt;
    var d;
    var o = '<a class="btn btn-sm btn-block btn-outline-light p-0 my-1" href="/fh/' + symbol + '/" target="_blank">' + symbol + '</a>';
    t = t + '<div class="col-3 col-sm-2 col-md-3 col-xl-2">' + o + '</div>';
    o = '';
    if ("chginfo" in D) {
        d = D.chginfo;
        tt = d.move + ' ' + Math.round(Math.abs(d.chg)*10000)/100 + '% in share price';
        o = o + '<span id="' + obj + '-chg"><a href="/fb/chg/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-secondary py-0 ml-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '"><span class="text-' + (d.chg<0 ? 'danger">':'success">+') + Math.round(d.chg*10000)/100+'%</span></a></span>';
    }
    if ("volinfo" in D) {
        d = D.volinfo;
        tt = Math.round(Math.abs(d.z)*10)/10 + ' standard deviations ' + (d.z<0?"below":"above") + " average trading volume";
        o = o + '<span id="' + obj + '-vol"><a href="/fb/vol/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-secondary py-0 ml-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+Math.round(d.z*10)/10+'&sigma; vol</a></span>';
    }
    if ("pflinfo" in D) {
        d = D.pflinfo;
        tt = d.hl_ratio+'% '+d.rarity+' flux over previos closing price';
        o = o + '<span id="' + obj + '-pfl"><a href="/fb/pfl/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-secondary py-0 ml-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+Math.round(d.hl_ratio*10)/10+'% flx</a></span>';
    }
    if ("cfpinfo" in D) {
        d = D.cfpinfo;
        tt = d.target + " " + d.move;
        o = o + '<span id="' + obj + '-cfp"><a href="/fb/dme/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-secondary py-0 ml-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+d.qmove+'</a></span>';
    }
    if ("ahdinfo" in D) {
        d = D.ahdinfo;
        tt = d.times + " out of " + d.outof + " times " + symbol +" went " + (d.chgSign=='-'?'down':'up') + " an average of " + d.chg + "% in " + d.term + ", after the day " + d.td;
        o = o + '<span id="' + obj + '-ahd"><a href="/fb/ahd/'+symbol+'/" target="_blank" class="btn btn-sm btn-outline-secondary py-0 ml-1 my-1" data-toggle="tooltip" data-placement="top" title="' + tt + '">'+d.term_short + ' <span class="text-' + (d.chgSign=='-'?'danger':'success') + '">' + d.chgSign + d.chg + '%</span> (x' + d.times + ')</a></span>';
    }
    if ("f66info" in D) {
        d = D.f66info.bits;
        var p = "";
        if (d.length == 6) {
            for (i in d) {
                p = p + '<pre class="btn btn-sm py-0 mx-0 my-1 px-1 text-light" style="background-color:' + getF66ColorCode(d[i].c_diff) + '" data-toggle="tooltip" data-placement="top" title="'+((d[i].c_diff<0)?"":"+") + d[i].c_diff + '% in the past ' + d[i].range+'">' + d[i].pr.substring(0,1) + '</pre>';
            }
            o = '<span id="' + obj + '-f66" class="nw"><a href="/fb/f66/'+symbol+'/" target="_blank">' + p +'</a></span>' + o;
        }
    }
    t = t + '<div id="' + obj + '-events" class="col-9 col-sm-10 col-md-9 col-lg-9">' + o + '</div>';
    t = '<div class="row my-1 align-items-center hvr2" id="' + obj + '-row">' + t + '</div>';
    $("#baking-list").append(t);
    $('[data-toggle="tooltip"]').tooltip();
};
