'use strict';
const card_info = {
    cache: {},
    get_cardface_text: function (card) {
        return `${card.name}  ${card.mana_cost} - ${card.type_line}\n\n${card.oracle_text}`.replace('"', '\'');
    },
    get_card_text: function (card) {
        if (card.card_faces && card.card_faces.length > 0) {
            return card
                .card_faces
                .map(this.get_cardface_text)
                .join('\n🔄\n');
        }
        return this.get_cardface_text(card);
    },
    get_cardface_image_html: function (card) {
        const alt = this.get_cardface_text(card);
        const html = `<img class="card-image" src="${card.image_uris.normal}" alt="${alt}"/>`;
        return html;
    },
    get_card_image_html: function (card) {
        if (card.image_uris) {
            return this.get_cardface_image_html(card);
        }
        if (card.card_faces && card.card_faces.length > 0) {
            return card
                .card_faces
                .filter(face => face.image_uris)
                .map(this.get_cardface_image_html.bind(this))
                .join('');
        }
        return '';
    },
    fetch_card_info: async function (name) {
        return await django.jQuery.ajax({
            url: 'https://api.scryfall.com/cards/named',
            dataType: 'json',
            data: {
                exact: name,
                format: 'json'
            },
        });
    },
    fetch_card_oracle_info: async function (oracle_id) {
        return await django.jQuery.ajax({
            type: 'POST',
            url: 'https://api.scryfall.com/cards/collection',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                identifiers: [{
                    oracle_id: oracle_id
                }]
            }),
        });
    },
    fetch_card_html: async function (name) {
        const data = await this.fetch_card_info(name);
        return this.get_card_image_html(data);
    },
    fetch_card_oracle_html: async function (oracle_id) {
        const data = await this.fetch_card_oracle_info(oracle_id);
        if (data.data && data.data.length > 0) {
            return this.get_card_image_html(data.data[0]);
        }
        throw new Error('No card found');
    },
    update_card_image: function (card_name, element) {
        this.fetch_card_html(card_name).then(function (html) {
            element.innerHTML = html;
        });
    },
    update_card_oracle_image: function (oracle_id, element) {
        this.fetch_card_oracle_html(oracle_id).then(function (html) {
            element.innerHTML = html;
        });
    },
    setup_tooltip: function (card_name, element, image=true) {
        if (image) {
            django.jQuery(element).tooltip({
                items: element,
                classes: {
                    "ui-tooltip": "ui-corner-all ui-widget-shadow card-info-tooltip"
                },
                content: next => {
                    if (this.cache[card_name]) {
                        next(this.cache[card_name]);
                        return;
                    }
                    this.fetch_card_html(card_name).then(html => {
                        this.cache[card_name] = html;
                        next(html);
                    });
                },
                show: "fade",
                hide: "fade",
                position: { my: "left+20 center", at: "right center", collision: "flipfit" },
                track: true,
                create: function(ev, ui) {
                    django.jQuery(this).data("ui-tooltip").liveRegion.remove();
                }
            }).dblclick(function() {
                django.jQuery(this).tooltip('close');
            });
        } else {
            element.title = 'Loading..';
            element.onmouseover = () => {
                if (element.title === 'Loading..') {
                    element.title = 'Loading...';
                    this.fetch_card_info(card_name)
                        .then(this.get_card_text.bind(this))
                        .then(text => {
                            element.title = text;
                        });
                }
            };
        }
    }
}
