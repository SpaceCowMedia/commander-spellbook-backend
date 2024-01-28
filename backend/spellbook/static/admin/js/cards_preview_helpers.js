django.jQuery.fn.select2CardsPreview = function() {
    django.jQuery.each(this, function(i, element) {
        if (element.id.includes('__prefix__')) {
            return;
        }
        const s = django.jQuery(element).select2({
            ajax: {
                data: (params) => {
                    return {
                        term: params.term,
                        page: params.page,
                        app_label: element.dataset.appLabel,
                        model_name: element.dataset.modelName,
                        field_name: element.dataset.fieldName
                    };
                }
            },
            templateResult: (data) => {
                const elem = django.jQuery(document.createElement('span'));
                elem.addClass('tooltip-in-dropdown');
                elem.text(data.text);
                card_info.setup_tooltip(data.text, elem);
                return elem;
            },
            templateSelection: (data) => {
                const elem = django.jQuery(document.createElement('span'));
                elem.text(data.text);
                card_info.setup_tooltip(data.text, elem);
                return elem;
            },
        }).on('select2:closing', function(e) {
            django.jQuery('.tooltip-in-dropdown').tooltip('close');                        
        });
    });
    return this;
};

django.jQuery.fn.autocompleteCardsPreview = function() {
    django.jQuery.each(this, function(i, element) {
        if (element.id.includes('__prefix__')) {
            return;
        }
        const autocomplete = django.jQuery(element).autocomplete({
            source: function(request, response) {
                django.jQuery.ajax({
                    url: 'https://api.scryfall.com/cards/autocomplete',
                    dataType: 'json',
                    data: {
                        q: request.term,
                        format: 'json'
                    },
                    success: function(data) {
                        response(data.data);
                    }
                });
            },
            minLength: 3,
            open: function() {},
            close: function() {},
        })
        .autocomplete('instance');
        if (autocomplete) {
            autocomplete._renderItem = function(ul, item) {
                const newItem = django.jQuery('<li>')
                    .attr('data-value', item.value)
                    .append(item.label)
                    .appendTo(ul);
                card_info.setup_tooltip(item.value, newItem);
                return newItem;
            };
        }
    });
    return this;
};
