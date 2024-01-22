'use strict';
{
    const SelectBox = {
        cache: {},
        init: function(id) {
            const box = document.getElementById(id);
            SelectBox.cache[id] = [];
            const cache = SelectBox.cache[id];
            for (const node of box.options) {
                cache.push({value: node.value, text: node.text, displayed: 1});
            }
            const searchInput = document.getElementById(id.replace(/_[^_]+$/, '_input'));
            if (searchInput) {
                searchInput.onpaste = event => {
                    event.stopPropagation();
                    event.preventDefault();
                    let paste = (event.clipboardData || window.clipboardData).getData('text');
                    paste = paste.split(/[\r\n/]+/)
                        .map(item => item.trim())
                        .filter(item => item.length > 0)
                        .join('; ');
                    event.target.value = paste;
                };
            }
        },
        redisplay: function(id) {
            // Repopulate HTML select box from cache
            const box = document.getElementById(id);
            const scroll_value_from_top = box.scrollTop;
            box.innerHTML = '';
            for (const node of SelectBox.cache[id]) {
                if (node.displayed) {
                    const new_option = new Option(node.text, node.value, false, false);
                    // Shows a tooltip when hovering over the option
                    new_option.title = node.text;
                    box.appendChild(new_option);
                }
            }
            box.scrollTop = scroll_value_from_top;
        },
        filter: function(id, text) {
            // For each query token:
            const queries = text.toLowerCase().split(/\s*;\s*/);
            // Redisplay the HTML select box, displaying only the choices containing ALL
            // the words in text. (It's an AND search.)
            for (const node of SelectBox.cache[id]) {
                const node_text = node.text.toLowerCase();
                const lower_node_text = node_text.toLowerCase();
                node.displayed = 0;
                for (const query of queries) {
                    const lower_query = query.toLowerCase();
                    const tokens = lower_query.split(/\s+/).filter(t => t.length > 0);
                    const currentScore = node.displayed;
                    for (const token of tokens) {
                        if (!lower_node_text.includes(token)) {
                            node.displayed = currentScore;
                            break; // Once the first token isn't found we're done
                        } else {
                            node.displayed += 1;
                        }
                    }
                    if (lower_node_text.includes(lower_query)) {
                        node.displayed += 100;
                    }
                    if (lower_node_text.endsWith(lower_query)) {
                        node.displayed += 500;
                    }
                    if (lower_node_text.startsWith(lower_query)) {
                        node.displayed += 1000;
                    }
                    if (lower_node_text === lower_query) {
                        node.displayed += 10000;
                    }
                }
            }
            SelectBox.sort(id);
            SelectBox.redisplay(id);
        },
        get_hidden_node_count(id) {
            const cache = SelectBox.cache[id] || [];
            return cache.filter(node => node.displayed === 0).length;
        },
        delete_from_cache: function(id, value) {
            let delete_index = null;
            const cache = SelectBox.cache[id];
            for (const [i, node] of cache.entries()) {
                if (node.value === value) {
                    delete_index = i;
                    break;
                }
            }
            cache.splice(delete_index, 1);
        },
        add_to_cache: function(id, option) {
            SelectBox.cache[id].push({value: option.value, text: option.text, displayed: 1});
        },
        cache_contains: function(id, value) {
            // Check if an item is contained in the cache
            for (const node of SelectBox.cache[id]) {
                if (node.value === value) {
                    return true;
                }
            }
            return false;
        },
        move: function(from, to) {
            const from_box = document.getElementById(from);
            for (const option of from_box.options) {
                const option_value = option.value;
                if (option.selected && SelectBox.cache_contains(from, option_value)) {
                    SelectBox.add_to_cache(to, {value: option_value, text: option.text, displayed: 1});
                    SelectBox.delete_from_cache(from, option_value);
                }
            }
            SelectBox.redisplay(from);
            SelectBox.redisplay(to);
        },
        move_all: function(from, to) {
            const from_box = document.getElementById(from);
            for (const option of from_box.options) {
                const option_value = option.value;
                if (SelectBox.cache_contains(from, option_value)) {
                    SelectBox.add_to_cache(to, {value: option_value, text: option.text, displayed: 1});
                    SelectBox.delete_from_cache(from, option_value);
                }
            }
            SelectBox.redisplay(from);
            SelectBox.redisplay(to);
        },
        sort: function(id) {
            SelectBox.cache[id].sort(function(a, b) {
                if (a.displayed != b.displayed) {
                    return a.displayed < b.displayed ? 1 : -1;
                }
                a = a.text.toLowerCase();
                b = b.text.toLowerCase();
                if (a > b) {
                    return 1;
                }
                if (a < b) {
                    return -1;
                }
                return 0;
            } );
        },
        select_all: function(id) {
            const box = document.getElementById(id);
            for (const option of box.options) {
                option.selected = true;
            }
        }
    };
    window.SelectBox = SelectBox;
}
