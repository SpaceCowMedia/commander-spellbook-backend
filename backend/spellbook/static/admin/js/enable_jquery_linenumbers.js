django.jQuery(function() {
    django.jQuery('textarea#id_description').each(function() {
        var $this = django.jQuery(this);
        $this.linenumbers();
    });
});
