
function format_card_summary(card) {
    const alt = `${card.name}  ${card.mana_cost} - ${card.type_line}\n\n${card.oracle_text}`.replace('"', '\'');
    return `<img class="card-image" src="${card.image_uris.normal}" alt="${alt}"/>`;
}

async function fetch_card_info(name) {
    const data = await django.jQuery.ajax({
        url: 'https://api.scryfall.com/cards/named',
        dataType: 'json',
        data: {
            exact: name,
            format: 'json'
        },
    });
    if (data.card_faces && data.card_faces.length > 0) {
        return data
            .card_faces
            .map(format_card_summary)
            .join('');
    }
    return format_card_summary(data);
}

function setup_tooltip(card_name, element) {
    if (typeof $ !== 'undefined' && $ !== null) {
        $(element).tooltip({
            items: element,
            classes: {
                "ui-tooltip": "ui-corner-all ui-widget-shadow card-info-tooltip"
              },
            content: function(next) {
                fetch_card_info(card_name).then(next);
            },
            // show: "fold",
            // hide: "fold",
            position: { my: "left+20 center", at: "right center", collision: "flipfit" },
            track: true,
        });
    } else {
        element.title = 'Loading..';
        element.onmouseover = function() {
            if (element.title === 'Loading..') {
                element.title = 'Loading...';
                fetch_card_info(card_name).then(function(text) {
                    element.title = text;
                });
            }
        };
    }
}
