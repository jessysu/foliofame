function getFFText(stype, symbol, n=2) {
	$.getJSON('/api/v1/famebits/'+stype+'/'+symbol+'/'+n+'/', function(dd) {
        var t = "";
        for (i in dd.bits) {
            t = t + dd.bits[i] + '. ';
            }
        $("#maintext-txt").append('<p>' + t + '</p>');
    });
}

function getFFScanned(symbol, I_th=90) {
	$.getJSON('/api/v1/famebits/chg/'+symbol+'/', function(d) {
        if (d.chg >= 0) {
            var t = '<span class="scg">' +d.move+' '+Math.round(Math.abs(d.chg)*1000)/10+'%</span>';
        } else {
            var t = '<span class="scr">' +d.move+' '+Math.round(Math.abs(d.chg)*1000)/10+'%</span>';
        }
        $("#maintext-symbol-chg").html('Change: '+t+' <i class="fa fa-angle-double-right"></i>');
        if (d.I > I_th) {
            $("#maintext-symbol-chg").addClass("active");
            getFFText("chg", symbol, 3);
        }
        $.getJSON('/api/v1/famebits/vol/'+symbol+'/', function(d) {
        	if (d.z >= 0) {
                var t = '<span>+' +Math.round(d.z*10)/10+'&sigma;</span>';
            } else {
                var t = '<span>' +Math.round(d.z*10)/10+'&sigma;</span>';
            }
            $("#maintext-symbol-vol").html('Volume: '+d.volume_human+' ('+t+' '+ d.rarity +' volume) <i class="fa fa-angle-double-right"></i>');
            if (d.I > I_th) {
                $("#maintext-symbol-vol").addClass("active");
                getFFText("vol", symbol, 2);
            }
            $.getJSON('/api/v1/famebits/pfl/'+symbol+'/', function(d) {
                var t = 'Flux: ';
                t = t + '<span class="' + (d.low<d.previousClose ? "scr":"scg") + '">$' + d.low + '</span>~<span class="' + (d.high<d.previousClose ? "scr":"scg") + '">$' + d.high + '</span>';
                t = t + ' (' + d.rarity + ' ' + d.hl_ratio + '% flux)';
                t = t + ' <i class="fa fa-angle-double-right"></i>';
                $("#maintext-symbol-pfl").html(t);
                if (d.I > I_th) {
                    $("#maintext-symbol-pfl").addClass("active");
                    getFFText("pfl", symbol, 2);
                }
                $.getJSON('/api/v1/famebits/cfp/'+symbol+'/', function(d) {
                    $("#maintext-symbol-cfp").html('Breaking: ' + d.target + " " + d.move + ' <i class="fa fa-angle-double-right"></i>');
                    if (d.I > I_th) {
                        $("#maintext-symbol-cfp").addClass("active");
                        getFFText("cfp", symbol, 1);
                    }
                });
            });
        });
    });
    $.getJSON('/api/v1/famebits/ahd/'+symbol+'/', function(d) {
    	if (d.I >= 0.5 && d.times > 1 && d.target == 'self') {
    		$.getJSON('/api/v1/famebits/ahd/'+symbol+'/10/', function(dd) {
                var t = "<p>";
                for (i in dd.bits) {
                    if (dd.bits[i].includes("the past 6 months")) {
                        t = t + "</p><p>";
                    }
                    t = t + dd.bits[i] + '. ';
                }
                t = t + "</p>";
                $("#maintext-alt").append('<p>' + t + '</p>');
                $("#maintext-txt").hide();
    		});
    		$("#btn-ahead").removeClass('d-none');
    		$("#btn-ahead").html(d.term_short + ' <span class="text-' + (d.chgSign=='-'?'danger':'success') + '">' + d.chgSign + d.chg + '%</span> (x' + d.times + ') <i class="fa fa-angle-double-right"></i>');
    	}
    });
    $.getJSON('/api/v1/famebits/f6s/'+symbol+'/', function(d) {
        if (d.dp[0] == '+') {
            var t = '<span class="scg"> ' + d.dp + '</span>';
        } else {
            var t = '<span class="scr"> ' + d.dp + '</span>';
        }
        $("#maintext-symbol-f66").html('Holding: '+ t +' past ' + d.term + ' <i class="fa fa-angle-double-right"></i>');
    });
}

function getBestEver(symbol) {
    //symbol = symbol.replace('.','-');
    $.getJSON('/api/v1/famebits/bes/'+symbol+'/', function(d) {
        if (d.gain[0] == '+') {
            var t = '<span class="scg"> ' + d.gain + '</span>';
        } else {
            var t = '<span class="scr"> ' + d.gain + '</span>';
        }
        $("#maintext-symbol-bes").html('Timing: once ' + t + ' in '+ d.duration +' <i class="fa fa-angle-double-right"></i>');
    });
}

function getFameSense0(symbol) {
    //symbol = symbol.replace('.','-');
    $.getJSON('/api/v1/famebits/sens/'+symbol+'/0/', function(d) {
    	if ($.isEmptyObject(d)) {return}
    	var c = d.sense_desc.toLowerCase().includes('neutral') ? "secondary" : (d.sense_desc.toLowerCase().includes('positive') ? 'success' : 'danger');
        var t = '<span class="text-' + c + '">' + d.sense_desc + '</span>';
        t = t + ' <i class="fas fa-heartbeat mx-2"></i> ';
        c = d.sense_drift.toLowerCase().includes('little') ? "secondary" : (d.sense_drift.toLowerCase().includes('gain') ? 'success' : 'danger');
        t = t + '<span class="text-' + c + '">' + d.sense_drift + '</span>';
        t = '<a class="btn btn-sm btn-outline-secondary" href="/fh/sense/'+symbol+'/">' + t + ' <i class="fa fa-angle-double-right"></i></a>'; 
        $("#maintext-symbol-sen0").html(t);
    });
}


function getIEXQuote(symbol) {
    //symbol = symbol.replace('.','-');
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/quote', function(d) {
        var data = d;
        var previousClose = d.previousClose;
        var s="";
        if (data.changePercent < 0) {
            $("#maintext-symbol-chp").attr("class", "scr");
            $("#navbar-symbol-chp").attr("class", "scr");
        } else {
            $("#maintext-symbol-chp").attr("class", "scg");
            $("#navbar-symbol-chp").attr("class", "scg");
            s = "+";
        }
        $("#maintext-symbol-title").html("<span class='text-truncate'>" + d.companyName + " <span class='d-none d-md-inline-block'> ("+d.sector+")</span></span>");
        $("#maintext-symbol-close").text('$'+d.latestPrice);
        $("#maintext-symbol-chp").attr("class", ((data.changePercent<0) ? "scr":"scg"));
        $("#maintext-symbol-chp").text(((data.changePercent<0) ? "":"+") + Math.round(data.changePercent*10000)/100+'%');
        $("#navbar-symbol-name").text(symbol);
        $("#navbar-symbol-chp").attr("class", ((data.changePercent<0) ? "scr":"scg"));
        $("#navbar-symbol-chp").text(((data.changePercent<0) ? "":"+") + Math.round(data.changePercent*10000)/100 + "%");
        $("#navbar-symbol-close").text('$'+d.latestPrice);
        $("#maintext-symbol-pe").text(data.peRatio);
        $("#maintext-symbol-ytd").addClass((data.ytdChange<0) ? "scr":"scg");
        $("#maintext-symbol-ytd").removeClass((data.ytdChange<0) ? "scg":"scr");
        $("#maintext-symbol-ytd").text(((data.ytdChange<0) ? "":"+") + Math.round(data.ytdChange*10000)/100+'%');
        $("#maintext-symbol-cap").html('$'+intToString(data.marketCap));
        $("#maintext-symbol-capchp").attr("class", ((data.changePercent<0) ? "scr":"scg"));
        $("#maintext-symbol-capchp").text(((data.changePercent<0) ? "-":"+") + "$"+ intToString(Math.abs(Math.round(data.marketCap*( 1 - 1/(1+data.changePercent))))) );
        $("#maintext-symbol-52w").text((data.week52Low).toFixed(2) + " - " + (data.week52High).toFixed(2));

        if ( data.calculationPrice == "tops") {
            var socket = io.connect('https://ws-api.iextrading.com/1.0/tops');
            socket.on('connect', function () {
                socket.emit('subscribe', symbol);
            });
            function logScreen(jn) {
                var j = JSON.parse(jn);
                var c = j.lastSalePrice;
                var b = data.previousClose;
                var s = "";
                if (j.lastSalePrice < data.previousClose) {
                    $("#maintext-symbol-chp").attr("class", "scr");
                    $("#navbar-symbol-chp").attr("class", "scr");
                } else {
                    $("#maintext-symbol-chp").attr("class", "scg");
                    $("#navbar-symbol-chp").attr("class", "scg");
                    s = "+";
                }
                $("#maintext-symbol-chp").text(s + Math.round((c-b)/b*10000)/100 + "%");
                $("#navbar-symbol-chp").text(s + Math.round((c-b)/b*10000)/100 + "%");
                $("#maintext-symbol-close").text('$'+c);
                $("#navbar-symbol-close").text('$'+c);
            }
            socket.on('message', logScreen);
        }
    });
}


function getIEXnewsFH(symbol) {
    //symbol = symbol.replace('.','-');
    $.getJSON('https://api.iextrading.com/1.0/stock/'+symbol+'/news/last/5', function(data) {
    	for (d in data) {
            var dd = moment(data[d].datetime).format("YYYY-MM-DD hh:mm a z");
            var dt = data[d].headline;
            var str = '<span class="badge badge-secondary mb-1">'+data[d].source+'</span> ';
            str = str + '<a href="/re?s='+symbol+'&v=be&t=iexnews&u=' + data[d].url + '" class="list-group-item-heading text-light" target="_blank"><b>' + data[d].headline + '</b></a>';
            var ds = data[d].summary;
            if (ds.length > 50) {
                str = str + '<p class="list-group-item-text"><small>'+ds+'</small></p>';
            }
            str = '<span class="list-group-item list-group-item-action flex-column bg-dark text-light">' + str + '<div id="news'+d+'"></div> <small class="pull-right p-1">' + dd + '</small></span>';
            $("#maintext-news").append(str);
            var related = data[d].related.split(",");
            for (r in related) {
                if (related[r].length < 6 && r < 3 && related[r]!=symbol) {
                    $.getJSON('https://api.iextrading.com/1.0/stock/'+related[r]+'/quote', (function(d_) {
                        return function(rr) {
                            var ns='<a class="btn btn-sm ';
                            if (rr.change < 0) {
                                ns = ns + 'btn-danger';
                            } else {
                                ns = ns + 'btn-success';
                            }
                            ns = ns + ' mt2" href="/fh/'+rr.symbol+'/" target="_blank">'+rr.symbol+'</a> ';
                            $("#news"+d_).append(ns);
                        }
                    })(d));
                }
            }
        }
    });
}



function getFameSense(symbol, senseChartID, more=false) {
    
    $.getJSON('/api/v1/famebits/sens/'+symbol+'/' + (more?'more/':''), function(d) {
    	if ($.isEmptyObject(d)) {
    	    getIEXnewsFH(symbol);
    	    return
    	}
    	$("#sense-chart-container").removeClass('d-none');
    	$("#maintext-symbol-sense-wrap").removeClass('d-none');
    	$("#maintext-symbol-drift-wrap").addClass('d-lg-block');
    	$("#maintext-symbol-sense").append(d.sense_desc);
        if (!d.sense_desc.toLowerCase().includes('neutral')) {
        	$("#maintext-symbol-sense").addClass((d.sense_desc.toLowerCase().includes('positive')) ? "scg":"scr")
        }
        $("#maintext-symbol-drift").append(d.sense_drift);
        if (!d.sense_drift.toLowerCase().includes('little')) {
        	$("#maintext-symbol-drift").addClass((d.sense_drift.toLowerCase().includes('gain')) ? "scg":"scr")
        }
        for (i in d.sense_docs) {
        	var doc = d.sense_docs[i];
        	var dd = moment(doc.published).format("YYYY-MM-DD hh:mm a z");
        	var ab = '<p class="list-group-item-text"><small>' + doc.abstract + '</small></p>';
            var str = '';
            str = str + '<a class="badge mr-2 ' + (doc.contribution.toLowerCase().includes("neutral") ? "badge-secondary" : (doc.bin_diff<0 ? "badge-danger":"badge-success") ) + '" href="/fb/sen/'+symbol+'/' + doc.id + '/" target="_blank"><big><i class="fas fa-heartbeat mr-1"></i>' + doc.contribution + ' <i class="fa fa-angle-double-right"></i></big></a> ';
            str = str + '<a href="/fb/sen/'+symbol+'/' + doc.id + '/" class="list-group-item-heading text-light" target="_blank"><big>' + doc.title + '</big></a> ';
            str = str + ab;
            //str = '<span class="list-group-item list-group-item-action flex-column bg-dark text-light my-3">' + str + ' <div class="mb-3"><small>' + dd + '</small></div><div id="news'+i+'"></div></span>';
            str = '<span onclick="event.stopPropagation();event.preventDefault();window.open(\'/fb/sen/'+symbol+'/' + doc.id + '/\')" class="list-group-item list-group-item-action flex-column bg-dark text-light my-3 cp">' + str + ' <div class="mb-3"><small>' + dd + '</small></div><div id="news'+i+'"></div></span>';
            $("#maintext-news").append(str);
            var related = doc.related;
            if (!related.length) {continue}
            $.getJSON('https://api.iextrading.com/1.0/stock/market/batch?symbols='+related.join()+'&types=quote', (function(b_) {
            	return function(b) {
                    var str = "";
                    for (j in b) {
                       	var sym = b[j].quote.symbol;
                       	var chg = b[j].quote.changePercent;
                       	//str = str + '<a class="btn btn-sm ' + (chg<0 ? 'btn-outline-danger':'btn-outline-success') + ' m-1" href="/fh/'+sym+'/" target="_blank"> ' + sym + ' ' +(chg<0 ? '':'+') + Math.round(chg*10000)/100 + '%</a>';
                       	str = str + '<a class="btn btn-sm ' + (chg<0 ? 'btn-outline-danger':'btn-outline-success') + ' py-0 my-1 mr-1" onclick="event.stopPropagation();window.open(\'/fh/'+sym+'/\')"> ' + sym + ' ' +(chg<0 ? '':'+') + Math.round(chg*10000)/100 + '%</a>';
                    }
                    $("#news"+b_).append(str);
            	}
            })(i));
        }
    
        dd = d.dense_points;
        V = [];
        for (i in dd) {
            var t = (moment(dd[i]["dest_date"]).unix() )*1000;
            var v = dd[i]["dense_sense"];
            if ( v ) {
                V.push({t:t, y:Math.round(v*100)/100});
            }
        }
        var ctx = document.getElementById(senseChartID);
        drawSense(ctx, V);
    });
}