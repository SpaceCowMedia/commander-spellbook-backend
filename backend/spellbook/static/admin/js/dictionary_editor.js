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

    // the fields of the explanation, which the widget renders with their own widgets, inside the form
    // but while the editor shows them
    function explanationOf(field) {
        return [...field.querySelector('.dictionary-explanation-fields').children];
    }

    function controlsOf(fields) {
        return fields.flatMap(row => [...row.querySelectorAll('input, select, textarea')]);
    }

    function stateOf(control) {
        if (control.type === 'checkbox' || control.type === 'radio') {
            return control.checked;
        }
        return control.type === 'select-multiple' ? [...control.options].map(option => option.selected) : control.value;
    }

    function restore(control, state) {
        if (typeof state === 'boolean') {
            control.checked = state;
        } else if (Array.isArray(state)) {
            [...control.options].forEach((option, index) => { option.selected = state[index]; });
        } else {
            control.value = state;
        }
    }

    // the labels of the fields holding a text, which a box to tick is not
    function writtenTexts(field) {
        return explanationOf(field)
            .filter(row => [...row.querySelectorAll('input, select, textarea')].some(control => !['checkbox', 'radio', 'hidden'].includes(control.type) && control.value))
            .map(row => row.querySelector('label').textContent);
    }

    // mirrors the widget's template, which writes the summary before this script runs
    function summarize(field, attributes) {
        const summary = field.querySelector('.dictionary-summary');
        const keys = Object.keys(attributes);
        const written = writtenTexts(field);
        const names = [
            ...written.map(label => element('em', { className: 'dictionary-written-text', textContent: label })),
            ...keys,
        ].flatMap((name, index) => index ? [', ', name] : [name]);
        summary.classList.toggle('dictionary-invalid', Boolean(field.querySelector(':scope > .errorlist')));
        summary.classList.toggle('dictionary-empty', !keys.length && !written.length);
        summary.replaceChildren(
            element('span', { className: 'dictionary-keys' }, names.length ? names : ['Add explanation or attributes']),
            ...(keys.length ? [element('span', { className: 'dictionary-count', textContent: keys.length, title: `${keys.length} attribute${keys.length === 1 ? '' : 's'}` })] : []),
        );
        summary.title = keys.length ? toYaml(attributes) : 'Edit the explanation and attributes';
    }

    // the fields of the explanation go back into the form, holding what they held unless the editor
    // applies, and then telling the form what changed, which they could not while out of it
    function putBack(applied) {
        if (!editing || editing.done) {
            return;
        }
        editing.done = true;
        editing.field.querySelector('.dictionary-explanation-fields').append(...editing.explanation);
        for (const [control, state] of editing.saved) {
            if (!applied) {
                restore(control, state);
            } else if (JSON.stringify(stateOf(control)) !== JSON.stringify(state)) {
                control.dispatchEvent(new Event('input', { bubbles: true }));
                control.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    // an action inside the dialog, drawn the way the admin draws the ones of its inlines
    function link(className, text, onClick) {
        const action = element('a', { href: '#', className, textContent: text, title: text });
        action.setAttribute('role', 'button');
        action.addEventListener('click', event => { event.preventDefault(); onClick(); });
        return action;
    }

    // django.contrib.admin.utils.quote, which the views of the admin undo on the ids of their urls
    function quote(name) {
        return name.replace(/[":/_#?;@&=+$,[\]<>%\n\\]/g, character => `_${character.charCodeAt(0).toString(16).toUpperCase().padStart(2, '0')}`);
    }

    // the select of the admin with its links, its ids named after the row for its popups to find it
    function keyPicker(index) {
        const template = editing.field.querySelector('.dictionary-key-template');
        const picker = template.content.firstElementChild.cloneNode(true);
        for (const node of picker.querySelectorAll('[id]')) {
            node.id = node.id.replace(template.dataset.placeholder, `dictionary_key_${index}`);
        }
        return picker;
    }

    // an attribute is written by its name, which its option holds as its text: the admin puts the value
    // of the option in the urls of its links, so the value is the name quoted, even after a popup of the
    // admin left the name itself there
    function pickAttribute(key, row) {
        const source = editing.field.dataset;
        django.jQuery(key).select2({
            theme: 'admin-autocomplete',
            dropdownParent: django.jQuery(dialog),
            ajax: {
                url: source.autocompleteUrl,
                delay: 250,
                cache: true,
                data: params => ({ term: params.term, page: params.page, app_label: source.appLabel, model_name: source.modelName, field_name: source.fieldName }),
                processResults: ({ results, pagination }) => ({ results: results.map(({ text }) => ({ id: quote(text), text })), pagination }),
            },
        }).on('change', () => {
            const option = key.selectedOptions[0];
            option.value = quote(option.textContent);
            row.key = option.textContent;
        });
        updateRelatedObjectLinks(key);
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
            const picker = keyPicker(index);
            const key = picker.querySelector('select');
            key.append(element('option', { value: quote(row.key), textContent: row.key }));
            const kind = element('select', { className: 'dictionary-kind', title: 'An attribute can hold a text, which a combo writes, or nothing' },
                Object.entries(KINDS).map(([value, label]) => element('option', { value, textContent: label, selected: row.kind === value })));
            kind.addEventListener('change', () => { row.kind = kind.value; renderRows(); });
            const item = element('div', { className: 'dictionary-row' }, [
                picker,
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
        putBack(true);
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
            element('h2', { textContent: 'Explanation and attributes' }),
            element('div', { className: 'dictionary-body' }, [
                element('section', { className: 'dictionary-explanation' }, [
                    element('h3', { textContent: 'Explanation' }),
                    element('p', { className: 'dictionary-help dictionary-explanation-help' }),
                    element('div', { className: 'dictionary-explanation-rows' }),
                ]),
                element('section', { className: 'dictionary-attributes' }, [
                    element('h3', { textContent: 'Attributes' }),
                    element('p', { className: 'dictionary-help dictionary-attributes-help' }),
                    element('div', { className: 'dictionary-tabs' }, tabs),
                    element('div', { className: 'dictionary-panel-keys' }, [element('div', { className: 'dictionary-rows' }), add]),
                    element('div', { className: 'dictionary-panel-yaml' }, [element('textarea', { className: 'dictionary-yaml', rows: 14, spellcheck: false })]),
                    element('div', { className: 'dictionary-panel-json' }, [element('textarea', { className: 'dictionary-json', rows: 14, spellcheck: false })]),
                ]),
            ]),
            element('p', { className: 'dictionary-problem errornote', hidden: true }),
            element('div', { className: 'dictionary-buttons' }, [save, cancel]),
        ]);
        dialog.addEventListener('close', () => putBack(false));
        document.body.append(dialog);
    }

    function open(field) {
        if (!dialog) {
            build();
        }
        const stored = field.querySelector('textarea').value;
        const explanation = explanationOf(field);
        editing = { field, tab: null, rows: [], explanation, saved: controlsOf(explanation).map(control => [control, stateOf(control)]), done: false };
        dialog.querySelector('.dictionary-explanation-rows').replaceChildren(...explanation);
        dialog.querySelector('.dictionary-explanation').hidden = !explanation.length;
        // what the explanation and the attributes do depends on the producer, which its form tells
        for (const [selector, text] of [['.dictionary-explanation-help', field.dataset.explanationHelp], ['.dictionary-attributes-help', field.dataset.attributesHelp]]) {
            const help = dialog.querySelector(selector);
            help.textContent = text ?? '';
            help.hidden = !help.textContent;
        }
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
