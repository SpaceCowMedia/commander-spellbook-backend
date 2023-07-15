django.jQuery(function() {
    django.jQuery('fieldset.ingredient').each(function() {
        const parent = django.jQuery(this);
        const battlefieldState = parent.find('th.column-battlefield_card_state, td.field-battlefield_card_state');
        const exileState = parent.find('th.column-exile_card_state, td.field-exile_card_state');
        const libraryState = parent.find('th.column-library_card_state, td.field-library_card_state');
        const graveyardState = parent.find('th.column-graveyard_card_state, td.field-graveyard_card_state');
        function toggleZoneLocation(checkbox, state) {
            if (checkbox.is(':checked')) {
                state.show();
            } else {
                state.hide();
            }
        }
        let battlefield = parent.find('.field-zone_locations input[type="checkbox"][value="B"]').change(function() {
            toggleZoneLocation(django.jQuery(this), battlefieldState);
        });
        toggleZoneLocation(battlefield, battlefieldState);
        let exile = parent.find('.field-zone_locations input[type="checkbox"][value="E"]').change(function() {
            toggleZoneLocation(django.jQuery(this), exileState);
        });
        toggleZoneLocation(exile, exileState);
        let library = parent.find('.field-zone_locations input[type="checkbox"][value="L"]').change(function() {
            toggleZoneLocation(django.jQuery(this), libraryState);
        });
        toggleZoneLocation(library, libraryState);
        let graveyard = parent.find('.field-zone_locations input[type="checkbox"][value="G"]').change(function() {
            toggleZoneLocation(django.jQuery(this), graveyardState);
        });
        toggleZoneLocation(graveyard, graveyardState);
    });
});
