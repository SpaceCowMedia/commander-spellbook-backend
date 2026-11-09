'use strict';
{
    // Mirrors DictionaryValidator: the server has the last word, this only spares a round trip
    const RESERVED_CHARACTERS = ['!', '#', '$', '@', '|', '[', ']'];
    const CARD_STATE_KEYS = ['battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state'];
    const SUGGESTED_KEYS = ['name', 'mana_needed', 'easy_prerequisites', 'notable_prerequisites', 'description', 'notes', 'comment'];
    const TABS = ['keys', 'yaml', 'json'];

    let dialog = null;
    let editing = null;

    function element(tag, properties = {}, children = []) {
        const node = Object.assign(document.createElement(tag), properties);
        node.append(...children);
        return node;
    }

    function problemOf(dictionary) {
        if (dictionary === null || typeof dictionary !== 'object' || Array.isArray(dictionary)) {
            return 'A dictionary maps keys to values.';
        }
        for (const [key, value] of Object.entries(dictionary)) {
            if (!key || key !== key.trim() || key.includes('\n') || RESERVED_CHARACTERS.some(character => key.includes(character))) {
                return `"${key}" is not a valid key: a key is not blank, has no surrounding spaces and holds none of ${RESERVED_CHARACTERS.join(' ')}.`;
            }
            if (CARD_STATE_KEYS.includes(key)) {
                return `"${key}" cannot be overridden: a starting state is written in its own field.`;
            }
            if (typeof value !== 'string' && !(Array.isArray(value) && value.every(text => typeof text === 'string'))) {
                return `The value of "${key}" must be a text or a list of texts. In YAML, quote a text starting with { or [, as in "{2}{U}".`;
            }
        }
        return null;
    }

    function toYaml(dictionary) {
        return Object.keys(dictionary).length ? jsyaml.dump(dictionary, { lineWidth: -1, noRefs: true, quotingType: '"' }) : '';
    }

    function fromYaml(text) {
        if (!text.trim()) {
            return {};
        }
        try {
            // every scalar is a text, so that 2 or yes never turn into something a dictionary cannot hold
            return jsyaml.load(text, { schema: jsyaml.FAILSAFE_SCHEMA }) ?? {};
        } catch (error) {
            const line = error.mark ? ` on line ${error.mark.line + 1}` : '';
            throw new Error(`This is no valid YAML${line}: ${error.reason ?? error.message}. Quote a text starting with { or [, as in "{2}{U}".`);
        }
    }

    function fromJson(text) {
        if (!text.trim()) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            throw new Error(`This is no valid JSON: ${error.message}.`);
        }
    }

    function toRows(dictionary) {
        return Object.entries(dictionary).map(([key, value]) => ({ key, listed: Array.isArray(value), texts: Array.isArray(value) ? [...value] : [value] }));
    }

    function fromRows(rows) {
        const dictionary = {};
        for (const row of rows) {
            if (!row.key && row.texts.every(text => !text)) {
                continue;
            }
            if (Object.hasOwn(dictionary, row.key)) {
                throw new Error(`"${row.key}" is written more than once.`);
            }
            dictionary[row.key] = row.listed ? row.texts.filter(text => text) : row.texts.join('\n');
        }
        return dictionary;
    }

    // mirrors the widget's template, which writes the summary before this script runs
    function summarize(field, dictionary) {
        const summary = field.querySelector('.dictionary-summary');
        const keys = Object.keys(dictionary);
        const names = keys.flatMap((key, index) => [...(index ? [', '] : []), dictionary[key] === '' ? element('s', { textContent: key }) : key]);
        summary.classList.remove('dictionary-invalid');
        summary.classList.toggle('dictionary-empty', !keys.length);
        summary.replaceChildren(
            element('span', { className: 'dictionary-keys' }, keys.length ? names : ['Add keys']),
            ...(keys.length ? [element('span', { className: 'dictionary-count', textContent: keys.length, title: `${keys.length} key${keys.length === 1 ? '' : 's'}` })] : []),
        );
        summary.title = keys.length ? toYaml(dictionary) : 'Edit the dictionary';
    }

    // an action inside the dialog, drawn the way the admin draws the ones of its inlines
    function link(className, text, onClick) {
        const action = element('a', { href: '#', className, textContent: text, title: text });
        action.setAttribute('role', 'button');
        action.addEventListener('click', event => { event.preventDefault(); onClick(); });
        return action;
    }

    function textarea(value, onInput) {
        const input = element('textarea', { value, rows: Math.min(Math.max(value.split('\n').length, 1), 8), className: 'dictionary-text' });
        input.addEventListener('input', () => onInput(input.value));
        return input;
    }

    function renderRows() {
        const container = dialog.querySelector('.dictionary-rows');
        container.replaceChildren(...editing.rows.map((row, index) => {
            const texts = element('div', { className: 'dictionary-texts' }, row.texts.map((text, position) => {
                const item = element('div', { className: 'dictionary-item' }, [textarea(text, value => { row.texts[position] = value; })]);
                if (row.listed) {
                    item.append(link('inline-deletelink dictionary-remove-item', 'Remove this text', () => { row.texts.splice(position, 1); renderRows(); }));
                }
                return item;
            }));
            if (row.listed) {
                texts.append(link('addlink dictionary-add-item', 'Add another text', () => { row.texts.push(''); renderRows(); }));
            }
            const key = element('input', { type: 'text', value: row.key, placeholder: 'key', className: 'dictionary-key' });
            key.setAttribute('list', 'dictionary-suggested-keys');
            key.addEventListener('input', () => { row.key = key.value; });
            const listed = element('input', { type: 'checkbox', checked: row.listed });
            listed.addEventListener('change', () => {
                row.listed = listed.checked;
                row.texts = row.listed ? row.texts.filter(text => text) : [row.texts.join('\n')];
                if (!row.texts.length) {
                    row.texts = [''];
                }
                renderRows();
            });
            return element('div', { className: 'dictionary-row' }, [
                key,
                texts,
                element('label', { className: 'dictionary-listed', title: 'A list adds to the list it overrides, a text replaces it' }, [listed, ' list']),
                link('inline-deletelink dictionary-remove', 'Remove this key', () => { editing.rows.splice(index, 1); renderRows(); }),
            ]);
        }));
    }

    function currentDictionary() {
        switch (editing.tab) {
            case 'keys':
                return fromRows(editing.rows);
            case 'yaml':
                return fromYaml(dialog.querySelector('.dictionary-yaml').value);
            default:
                return fromJson(dialog.querySelector('.dictionary-json').value);
        }
    }

    function showProblem(problem) {
        const message = dialog.querySelector('.dictionary-problem');
        message.textContent = problem ?? '';
        message.hidden = !problem;
    }

    function read() {
        let dictionary;
        try {
            dictionary = currentDictionary();
        } catch (error) {
            showProblem(error.message);
            return null;
        }
        const problem = problemOf(dictionary);
        showProblem(problem);
        return problem ? null : dictionary;
    }

    function show(tab, dictionary) {
        editing.tab = tab;
        for (const name of TABS) {
            const button = dialog.querySelector(`.dictionary-tab-${name}`);
            button.classList.toggle('default', name === tab);
            button.setAttribute('aria-pressed', String(name === tab));
            dialog.querySelector(`.dictionary-panel-${name}`).hidden = name !== tab;
        }
        if (tab === 'keys') {
            editing.rows = toRows(dictionary);
            renderRows();
        } else if (tab === 'yaml') {
            dialog.querySelector('.dictionary-yaml').value = toYaml(dictionary);
        } else {
            dialog.querySelector('.dictionary-json').value = Object.keys(dictionary).length ? JSON.stringify(dictionary, null, 2) : '';
        }
    }

    function switchTo(tab) {
        if (tab === editing.tab) {
            return;
        }
        const dictionary = read();
        if (dictionary !== null) {
            show(tab, dictionary);
        }
    }

    function apply() {
        const dictionary = read();
        if (dictionary === null) {
            return;
        }
        const stored = editing.field.querySelector('textarea');
        stored.value = JSON.stringify(dictionary);
        stored.dispatchEvent(new Event('input', { bubbles: true }));
        stored.dispatchEvent(new Event('change', { bubbles: true }));
        summarize(editing.field, dictionary);
        dialog.close();
    }

    function build() {
        // the buttons of the admin, the one doing the job being its default one
        const tabs = TABS.map(name => {
            const tab = element('button', { type: 'button', className: `button dictionary-tab dictionary-tab-${name}`, textContent: name === 'keys' ? 'Keys' : name.toUpperCase() });
            tab.addEventListener('click', () => switchTo(name));
            return tab;
        });
        const add = link('addlink dictionary-add', 'Add another key', () => { editing.rows.push({ key: '', listed: false, texts: [''] }); renderRows(); });
        const save = element('button', { type: 'button', className: 'button default dictionary-apply', textContent: 'Apply' });
        save.addEventListener('click', apply);
        const cancel = element('button', { type: 'button', className: 'button dictionary-cancel', textContent: 'Cancel' });
        cancel.addEventListener('click', () => dialog.close());
        dialog = element('dialog', { className: 'dictionary-dialog' }, [
            element('h2', { textContent: 'Dictionary' }),
            element('p', { className: 'dictionary-help', textContent: 'Each key holds a text or a list of texts, which a combo writes with [[feature@key]]. Overriding what an ingredient brings, a text replaces, a list adds to a list, and a blank text leaves it out.' }),
            element('div', { className: 'dictionary-tabs' }, tabs),
            element('div', { className: 'dictionary-panel-keys' }, [element('div', { className: 'dictionary-rows' }), add]),
            element('div', { className: 'dictionary-panel-yaml' }, [element('textarea', { className: 'dictionary-yaml', rows: 14, spellcheck: false })]),
            element('div', { className: 'dictionary-panel-json' }, [element('textarea', { className: 'dictionary-json', rows: 14, spellcheck: false })]),
            element('p', { className: 'dictionary-problem errornote', hidden: true }),
            element('datalist', { id: 'dictionary-suggested-keys' }, SUGGESTED_KEYS.map(key => element('option', { value: key }))),
            element('div', { className: 'dictionary-buttons' }, [save, cancel]),
        ]);
        document.body.append(dialog);
    }

    function open(field) {
        if (!dialog) {
            build();
        }
        const stored = field.querySelector('textarea').value;
        editing = { field, tab: null, rows: [] };
        showProblem(null);
        try {
            const dictionary = fromJson(stored);
            const problem = problemOf(dictionary);
            if (problem) {
                throw new Error(problem);
            }
            show('keys', dictionary);
        } catch (error) {
            show('json', {});
            dialog.querySelector('.dictionary-json').value = stored;
            showProblem(error.message);
        }
        dialog.showModal();
    }

    document.addEventListener('click', event => {
        const summary = event.target.closest('.dictionary-summary');
        if (summary) {
            event.preventDefault();
            open(summary.closest('.dictionary-field'));
        }
    });

    document.addEventListener('DOMContentLoaded', () => {
        for (const field of document.querySelectorAll('.dictionary-field')) {
            try {
                const dictionary = fromJson(field.querySelector('textarea').value);
                if (!problemOf(dictionary)) {
                    summarize(field, dictionary);
                }
            } catch {
                field.querySelector('.dictionary-summary').classList.add('dictionary-invalid');
            }
        }
    });

    window.dictionaryEditor = { problemOf, toYaml, fromYaml, toRows, fromRows };
}
