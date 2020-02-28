function getF66ColorCode(d){
    var dt = 250/(1+Math.pow(Math.E,-0.08*d)) - 125;
    var r = (dt<0)? ("0"+((180-dt/2)|0).toString(16)).slice(-2).toUpperCase() : "00";
    var g = (dt<0)? "00" : ("0"+((128+dt)|0).toString(16)).slice(-2).toUpperCase();
    return "#"+r+g+"00"
};
function getF66Blocks(symbol){
    $.getJSON('/api/v1/famebits/f66/'+symbol+'/', function(d) {
        d = d.bits;
        var p = "";
        if (d.length != 6) {return}
        for (i in d) {
            p = p + '<pre class="btn btn-sm py-0 mx-0 my-1 px-1 text-light" style="background-color:' + getF66ColorCode(d[i].c_diff) + '" data-toggle="tooltip" data-placement="top" title="'+((d[i].c_diff<0)?"":"+") + d[i].c_diff + '% in the past ' + d[i].range+'">' + d[i].pr.substring(0,1) + '</pre>';
        }
        $("#maintext-"+symbol.replace(".","-")+"-f66").html('<span class="nw"><a href="/fb/f66/'+symbol+'/" target="_blank">' + p +'</a></span>');
        $('[data-toggle="tooltip"]').tooltip(); 
    });
};
