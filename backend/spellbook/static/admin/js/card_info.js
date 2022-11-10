function fetch_card_info(name, element) {
    if (element.title === '') {
        element.title = name;
        django.jQuery.ajax({
            url: 'https://api.scryfall.com/cards/named',
            dataType: 'json',
            data: {
                exact: name,
                format: 'json'
            },
            success: function(data) {
                element.removeAttribute('title');
                if (data.card_faces && data.card_faces.length > 0) {
                    element.title = data.card_faces
                        .map(e => 
                            e.name + '  ' + e.mana_cost + ' - ' + e.type_line + '\n\n' + 
                            e.oracle_text)
                        .join('\n🔄\n');
                } else {
                    element.title = 
                        data.name + '  ' + data.mana_cost + ' - ' + data.type_line + '\n\n' +
                        data.oracle_text;
                }
            }
        });
    }
}
