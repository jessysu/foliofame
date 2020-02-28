function getF66ColorCode(d){
    var dt = 250/(1+Math.pow(Math.E,-0.08*d)) - 125;
    var r = (dt<0)? ("0"+((180-dt/2)|0).toString(16)).slice(-2).toUpperCase() : "00";
    var g = (dt<0)? "00" : ("0"+((128+dt)|0).toString(16)).slice(-2).toUpperCase();
    return "#"+r+g+"00"
};
