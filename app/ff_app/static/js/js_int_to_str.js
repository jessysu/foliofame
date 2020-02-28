    function intToString (value) {
        var suffixes = ["", "K", "M", "B","T"];
        var suffixNum = Math.floor(((""+value).length-1)/3);
        var shortValue = parseFloat((suffixNum != 0 ? (value / Math.pow(1000,suffixNum)) : value).toPrecision(2));
        if (shortValue % 1 != 0) {
            var shortNum = shortValue.toFixed(1);
            }
        return shortValue+suffixes[suffixNum];
    }
