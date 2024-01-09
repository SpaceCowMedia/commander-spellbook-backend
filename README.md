# [Commander Spellbook](https://commanderspellbook.com/)

Commander Spellbook is a combo database, wiki and engine for [Magic: The Gathering](https://magic.wizards.com/en).
It's designed to be a one-stop shop for all the information you might want about a combo, whether it's a deck you're
building or one you're playing against.

This is an Open Source project, and we welcome contributions from the community. If you'd like to contribute, please
read the [Contributing](#contributing) section below.

## Architecture

Commander Spellbook consists of three main components:

- A [PostgreSQL](https://www.postgresql.org/) database containing all the combo data
- A [Django](https://www.djangoproject.com/) [backend](/backend/) that exposes the data via a REST API
- A [React](https://reactjs.org/) [frontend](https://github.com/SpaceCowMedia/commander-spellbook-site) that consumes the API and displays the content in a user-friendly way

## Contributing

Anyone is welcome to contribute to Commander Spellbook. You can contribute in a number of ways:

* On the [backend](/backend/), by opening a pull request with your changes
* On the [frontend](https://github.com/SpaceCowMedia/commander-spellbook-site), by opening a pull request with your changes
* By [submitting new combos](https://commanderspellbook.com/submit-a-combo/)

### Contribution Guidelines

You can find the contribution guidelines for the backend [here](CONTRIBUTING.md).

### Documentation

You can read some Markdown documentation [here](https://spacecowmedia.github.io/commander-spellbook-backend/).
