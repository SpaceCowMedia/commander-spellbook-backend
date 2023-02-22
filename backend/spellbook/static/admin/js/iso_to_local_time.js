django.jQuery(function() {
    django.jQuery('span.local-datetime').each(function() {
        var $this = django.jQuery(this);
        var iso_date = $this.attr('data-iso');
        if (iso_date) {
            var local_date = new Date(iso_date);
            if (local_date instanceof Date && !isNaN(local_date.valueOf())) {
                $this.text(local_date.toLocaleString());
            }
        }
    });
});
