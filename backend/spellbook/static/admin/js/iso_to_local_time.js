django.jQuery(function() {
    django.jQuery('.local-datetime').each(function() {
        var $this = django.jQuery(this);
        var iso_date = $this.attr('title');
        if (iso_date) {
            var local_date = new Date(iso_date);
            $this.text(local_date.toLocaleString());
        }
    });
});
