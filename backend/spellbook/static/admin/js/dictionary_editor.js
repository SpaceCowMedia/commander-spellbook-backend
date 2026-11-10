'use strict';
{
    // Mirrors validate_attributes: the server has the last word, this only spares a round trip
    const RESERVED_CHARACTERS = ['$', '@', '|', '[', ']'];
    const BUILT_IN_KEYS = ['name', 'mana_needed', 'easy_prerequisites', 'notable_prerequisites', 'description', 'notes', 'comment', 'battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state'];
    const TABS = ['keys', 'yaml', 'json'];
    const KINDS = { text: 'text', none: 'no text' };

    let dialog = null;
    let editing = null;

    function element(tag, properties = {}, children = []) {
        const node = Object.assign(document.createElement(tag), properties);
        node.append(...children);
        return node;
    }

    function problemOf(attributes) {
        if (attributes === null || typeof attributes !== 'object' || Array.isArray(attributes)) {
            return 'The attributes must map their names to a text, or to nothing.';
        }
        for (const [name, text] of Object.entries(attributes)) {
            if (!name || name !== name.trim() || name.includes('\n') || RESERVED_CHARACTERS.some(character => name.includes(character))) {
                return `"${name}" is not a valid attribute: a name is not blank, has no surrounding spaces and holds none of ${RESERVED_CHARACTERS.join(' ')}.`;
            }
            if (BUILT_IN_KEYS.includes(name)) {
                return `"${name}" is no attribute: write it in its own field.`;
            }
            if (text !== null && typeof text !== 'string') {
                return `The text of "${name}" must be a single text, or nothing. In YAML, quote a text starting with { or [, as in "{2}{U}".`;
            }
        }
        return null;
    }

    // an attribute holding nothing is written bare, which reads back as nothing, while every other scalar is a text
    function toYaml(attributes) {
        return Object.keys(attributes).length ? jsyaml.dump(attributes, { lineWidth: -1, noRefs: true, quotingType: '"', styles: { '!!null': 'empty' } }).replace(/: $/gm, ':') : '';
    }

    function fromYaml(text) {
        if (!text.trim()) {
            return {};
        }
        try {
            // every scalar is a text, so that 2 or yes never turn into something an attribute cannot hold
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

    function toRows(attributes) {
        return Object.entries(attributes).map(([key, text]) => ({ key, kind: text ? 'text' : 'none', text: text ?? '' }));
    }

    function fromRows(rows) {
        const attributes = {};
        for (const row of rows) {
            if (!row.key && (row.kind === 'none' || !row.text)) {
                continue;
            }
            if (Object.hasOwn(attributes, row.key)) {
                throw new Error(`"${row.key}" is written more than once.`);
            }
            attributes[row.key] = row.kind === 'none' || !row.text ? null : row.text;
        }
        return attributes;
    }

    // mirrors the widget's template, which writes the summary before this script runs
    function summarize(field, attributes) {
        const summary = field.querySelector('.dictionary-summary');
        const keys = Object.keys(attributes);
        summary.classList.remove('dictionary-invalid');
        summary.classList.toggle('dictionary-empty', !keys.length);
        summary.replaceChildren(
            element('span', { className: 'dictionary-keys', textContent: keys.length ? keys.join(', ') : 'Add attributes' }),
            ...(keys.length ? [element('span', { className: 'dictionary-count', textContent: keys.length, title: `${keys.length} attribute${keys.length === 1 ? '' : 's'}` })] : []),
        );
        summary.title = keys.length ? toYaml(attributes) : 'Edit the attributes';
    }

    // an action inside the dialog, drawn the way the admin draws the ones of its inlines
    function link(className, text, onClick) {
        const action = element('a', { href: '#', className, textContent: text, title: text });
        action.setAttribute('role', 'button');
        action.addEventListener('click', event => { event.preventDefault(); onClick(); });
        return action;
    }

    // the names are the ids, being what the attributes are written with
    function pickAttribute(key, row) {
        const source = editing.field.dataset;
        django.jQuery(key).select2({
            theme: 'admin-autocomplete',
            dropdownParent: django.jQuery(dialog),
            placeholder: 'attribute',
            ajax: {
                url: source.autocompleteUrl,
                delay: 250,
                cache: true,
                data: params => ({ term: params.term, page: params.page, app_label: source.appLabel, model_name: source.modelName, field_name: source.fieldName }),
                processResults: ({ results, pagination }) => ({ results: results.map(({ text }) => ({ id: text, text })), pagination }),
            },
        }).on('change', () => { row.key = key.value; });
    }

    function renderRows() {
        const container = dialog.querySelector('.dictionary-rows');
        container.replaceChildren(...editing.rows.map((row, index) => {
            // the text of an attribute holding nothing is kept, for a change of mind to bring it back
            let texts;
            if (row.kind === 'none') {
                texts = element('div', { className: 'dictionary-texts dictionary-no-value', textContent: 'The attribute alone, with nothing to write.' });
            } else {
                const input = element('textarea', { value: row.text, rows: Math.min(Math.max(row.text.split('\n').length, 1), 8), className: 'dictionary-text' });
                input.addEventListener('input', () => { row.text = input.value; });
                texts = element('div', { className: 'dictionary-texts' }, [input]);
            }
            const key = element('select', { className: 'dictionary-key' }, [element('option', { value: row.key, textContent: row.key })]);
            const kind = element('select', { className: 'dictionary-kind', title: 'An attribute can hold a text, which a combo writes, or nothing' },
                Object.entries(KINDS).map(([value, label]) => element('option', { value, textContent: label, selected: row.kind === value })));
            kind.addEventListener('change', () => { row.kind = kind.value; renderRows(); });
            const item = element('div', { className: 'dictionary-row' }, [
                key,
                texts,
                kind,
                link('inline-deletelink dictionary-remove', 'Remove this attribute', () => { editing.rows.splice(index, 1); renderRows(); }),
            ]);
            pickAttribute(key, row);
            return item;
        }));
    }

    function currentAttributes() {
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
        let attributes;
        try {
            attributes = currentAttributes();
        } catch (error) {
            showProblem(error.message);
            return null;
        }
        const problem = problemOf(attributes);
        showProblem(problem);
        return problem ? null : attributes;
    }

    function show(tab, attributes) {
        editing.tab = tab;
        for (const name of TABS) {
            const button = dialog.querySelector(`.dictionary-tab-${name}`);
            button.classList.toggle('default', name === tab);
            button.setAttribute('aria-pressed', String(name === tab));
            dialog.querySelector(`.dictionary-panel-${name}`).hidden = name !== tab;
        }
        if (tab === 'keys') {
            editing.rows = toRows(attributes);
            renderRows();
        } else if (tab === 'yaml') {
            dialog.querySelector('.dictionary-yaml').value = toYaml(attributes);
        } else {
            dialog.querySelector('.dictionary-json').value = Object.keys(attributes).length ? JSON.stringify(attributes, null, 2) : '';
        }
    }

    function switchTo(tab) {
        if (tab === editing.tab) {
            return;
        }
        const attributes = read();
        if (attributes !== null) {
            show(tab, attributes);
        }
    }

    function apply() {
        const attributes = read();
        if (attributes === null) {
            return;
        }
        const stored = editing.field.querySelector('textarea');
        stored.value = JSON.stringify(attributes);
        stored.dispatchEvent(new Event('input', { bubbles: true }));
        stored.dispatchEvent(new Event('change', { bubbles: true }));
        summarize(editing.field, attributes);
        dialog.close();
    }

    function build() {
        // the buttons of the admin, the one doing the job being its default one
        const tabs = TABS.map(name => {
            const tab = element('button', { type: 'button', className: `button dictionary-tab dictionary-tab-${name}`, textContent: name === 'keys' ? 'Attributes' : name.toUpperCase() });
            tab.addEventListener('click', () => switchTo(name));
            return tab;
        });
        const add = link('addlink dictionary-add', 'Add another attribute', () => { editing.rows.push({ key: '', kind: 'none', text: '' }); renderRows(); });
        const save = element('button', { type: 'button', className: 'button default dictionary-apply', textContent: 'Apply' });
        save.addEventListener('click', apply);
        const cancel = element('button', { type: 'button', className: 'button dictionary-cancel', textContent: 'Cancel' });
        cancel.addEventListener('click', () => dialog.close());
        dialog = element('dialog', { className: 'dictionary-dialog' }, [
            element('h2', { textContent: 'Attributes' }),
            element('p', { className: 'dictionary-help', textContent: 'The attributes this produces the feature with. Each can hold a text, which a combo needing the feature writes with [[feature@attribute]], or nothing.' }),
            element('div', { className: 'dictionary-tabs' }, tabs),
            element('div', { className: 'dictionary-panel-keys' }, [element('div', { className: 'dictionary-rows' }), add]),
            element('div', { className: 'dictionary-panel-yaml' }, [element('textarea', { className: 'dictionary-yaml', rows: 14, spellcheck: false })]),
            element('div', { className: 'dictionary-panel-json' }, [element('textarea', { className: 'dictionary-json', rows: 14, spellcheck: false })]),
            element('p', { className: 'dictionary-problem errornote', hidden: true }),
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
            const attributes = fromJson(stored);
            const problem = problemOf(attributes);
            if (problem) {
                throw new Error(problem);
            }
            show('keys', attributes);
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
                const attributes = fromJson(field.querySelector('textarea').value);
                if (!problemOf(attributes)) {
                    summarize(field, attributes);
                }
            } catch {
                field.querySelector('.dictionary-summary').classList.add('dictionary-invalid');
            }
        }
    });

    window.dictionaryEditor = { problemOf, toYaml, fromYaml, toRows, fromRows };
}
