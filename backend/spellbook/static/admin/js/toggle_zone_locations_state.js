django.jQuery(function() {
    django.jQuery('fieldset.ingredient').each(function() {
        const checkboxEvent = 'change.update_zone_location';
        const parent = django.jQuery(this);
        function setupEventListeners() {
            const battlefieldState = parent.find('th.column-battlefield_card_state, td.field-battlefield_card_state');
            const exileState = parent.find('th.column-exile_card_state, td.field-exile_card_state');
            const libraryState = parent.find('th.column-library_card_state, td.field-library_card_state');
            const graveyardState = parent.find('th.column-graveyard_card_state, td.field-graveyard_card_state');
            function toggleZoneLocation(checkbox, state) {
                if (checkbox.is(':checked')) {
                    state.each(function(index) {
                        const element = django.jQuery(this);
                        element.show();
                        if (index > 0) {
                            // This should be done for td
                            const correspondingCheckbox = checkbox.eq(index - 1);
                            const innerInput = element.find('input');
                            if (correspondingCheckbox.is(':checked')) {
                                innerInput.css('visibility', 'visible');
                            } else {
                                innerInput.css('visibility', 'hidden');
                            }
                        }
                    });
                } else {
                    state.hide();
                }
            }
            let battlefield = parent.find('.field-zone_locations input[type="checkbox"][value="B"]');
            battlefield.off(checkboxEvent).on(checkboxEvent, function() {
                toggleZoneLocation(battlefield, battlefieldState);
            });
            toggleZoneLocation(battlefield, battlefieldState);
            let exile = parent.find('.field-zone_locations input[type="checkbox"][value="E"]');
            exile.off(checkboxEvent).on(checkboxEvent, function() {
                toggleZoneLocation(exile, exileState);
            });
            toggleZoneLocation(exile, exileState);
            let library = parent.find('.field-zone_locations input[type="checkbox"][value="L"]');
            library.off(checkboxEvent).on(checkboxEvent, function() {
                toggleZoneLocation(library, libraryState);
            });
            toggleZoneLocation(library, libraryState);
            let graveyard = parent.find('.field-zone_locations input[type="checkbox"][value="G"]');
            graveyard.off(checkboxEvent).on(checkboxEvent, function() {
                toggleZoneLocation(graveyard, graveyardState);
            });
            toggleZoneLocation(graveyard, graveyardState);
        }
        django.jQuery('.add-row a[href="#"]').on('click', setupEventListeners);
        setupEventListeners();
    });
});
