function toggleWatch(ss, action, objadd, objdrop, csrf_token, uio=false, reqpath='/') {
	if (uio) {
        if (action != 'add' && action != 'drop') {
            return
        }
        $.ajax({
            url: "/watch/"+action+"/"+ss+"/",
            type: "POST",
            data: {"csrfmiddlewaretoken": csrf_token, "view": "my_quotes"},
            success: function(data) {
                if (data.message == "Succeeded") {
                    if ($.isArray(objadd)) {
                        for (o in objadd) {
                            $('#'+objadd[o]).toggleClass('d-none')
                        }
                    } else {
                        $('#'+objadd).toggleClass('d-none');
                    }
                    if ($.isArray(objdrop)) {
                        for (o in objdrop) {
                            $('#'+objdrop[o]).toggleClass('d-none')
                        }
                    } else {
                        $('#'+objdrop).toggleClass('d-none');
                    }
                } else {
                    alert(data.message);
                }
            }
        });
    } else {
        window.open("/accounts/login/?next="+reqpath,"_self");
    }
}
