/**
 * 
 * @param {string} name 
 * @param {HTMLElement} element 
 */
function fetch_card_info(name, element) {
    let attributeName = 'title';
    if (typeof $ !== 'undefined' && $ !== null) {
        attributeName = 'data-card-info';
    }
    if (element.getAttribute(attributeName) === null) {
        django.jQuery.ajax({
            url: 'https://api.scryfall.com/cards/named',
            dataType: 'json',
            data: {
                exact: name,
                format: 'json'
            },
            success: function(data) {
                if (data.card_faces && data.card_faces.length > 0) {
                    element.setAttribute(attributeName,
                        data.card_faces.map(e => 
                            e.name + '  ' + e.mana_cost + ' - ' + e.type_line + '\n\n' + 
                            e.oracle_text)
                        .join('\n🔄\n'));
                } else {
                    element.setAttribute(attributeName,
                        data.name + '  ' + data.mana_cost + ' - ' + data.type_line + '\n\n' +
                        data.oracle_text);
                }
                if (typeof $ !== 'undefined' && $ !== null) {
                    $(".ui-tooltip-content").parents('div').remove();
                    $(element).tooltip({
                        items: `[${attributeName}]`,
                        content: function() {
                            return this.getAttribute(attributeName);
                        }
                    }).mouseover();
                }
            }
        });
    }
}
