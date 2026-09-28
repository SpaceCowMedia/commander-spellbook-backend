import os
import re
import discord
import logging
from typing import Any, Awaitable, Callable
from discord.ext import commands
from discord import app_commands, ui, utils
from spellbook_client import ApiException, Variant, VariantsApi, CardsApi, InvalidUrlResponse, VariantsQueryValidationError, DeckRequest, CardInDeckRequest, FindMyCombosApi, CardListFromUrlApi
from spellbook_client.extensions import find_my_combos_create_plain
from text_utils import discord_chunk
from constants import WEBSITE_URL
from bot_utils import parse_queries, SpellbookQuery, url_from_variant, compute_variant_name, compute_variant_results, API, compute_variant_recipe, uri_validator


intents = discord.Intents(messages=True, guilds=True)
intents.message_content = True
bot = commands.Bot(
    command_prefix='?',
    intents=intents,
    description='Powered by Commander Spellbook (https://commanderspellbook.com/),\nUse the `{{query}}` syntax to search for combos, or launch one of the slash (/) commands.',
    activity=discord.Game(
        name='a combo on turn 3',
        platform='https://commanderspellbook.com/',
    ),
    allowed_mentions=discord.AllowedMentions.none(),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
)
permissions = discord.Permissions(
    view_channel=True,
    send_messages=True,
    send_messages_in_threads=True,
    manage_messages=True,
    embed_links=True,
    attach_files=True,
    read_message_history=True,
    add_reactions=True,
    use_external_emojis=True,
)
administration_guilds = [int(guild) for guild in (os.getenv(f'ADMIN_GUILD__{i}') for i in range(10)) if guild is not None]
administration_users = [int(user) for user in (os.getenv(f'ADMIN_USER__{i}') for i in range(10)) if user is not None]

MAX_SEARCH_RESULTS = 7
MAX_QUERY_LENGTH = 300
MAX_DECKLIST_FILE_SIZE = 100_000
MAX_FOLLOWUPS = 5
MAX_TRACKED_MESSAGES = 1000
ORDERING = '-popularity,identity_count,card_count,-created'

mana_emojis: dict[str, str] = {}
answers: dict[int, tuple[list[int], str | None]] = {}


@bot.event
async def setup_hook():
    bot.add_dynamic_items(VariantDetailsSelect)
    mana_emojis.update((emoji.name, str(emoji)) for emoji in await bot.fetch_application_emojis())


@bot.command(hidden=True)
async def sync(ctx: commands.Context):
    if ctx.guild is not None and ctx.guild.id in administration_guilds or ctx.author.id in administration_users:
        await ctx.message.add_reaction('👍')
        await bot.tree.sync(guild=ctx.guild)
        await ctx.message.remove_reaction('👍', bot.user)  # type: ignore
        await ctx.message.add_reaction('✅')


@bot.tree.command()
async def invite(interaction: discord.Interaction):
    invite_link = utils.oauth_url(bot.user.id, permissions=permissions)  # type: ignore
    button = ui.Button(label='Invite', url=invite_link, style=discord.ButtonStyle.link)
    view = ui.View()
    view.add_item(button)
    await interaction.response.send_message('Invite me to your server!', view=view)


@bot.event
async def on_guild_join(guild: discord.Guild):
    logging.info(f'Joined guild: {guild.name}')
    await bot.tree.sync(guild=guild)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logging.error(f'Error in command {interaction.command.qualified_name if interaction.command else None}', exc_info=error)
    message = 'Something went wrong, please try again later.'
    if interaction.response.is_done():
        await interaction.followup.send(content=message, ephemeral=True)
    else:
        await interaction.response.send_message(content=message, ephemeral=True)


def convert_mana_identity_to_emoji(identity: str):
    return ''.join(mana_emojis.get(f'mana{symbol.lower()}', symbol) for symbol in identity)


def identity_colour(identity: str) -> discord.Colour:
    match identity[:1]:
        case 'C':
            return discord.Colour.light_grey()
        case 'R':
            return discord.Colour.red()
        case 'U':
            return discord.Colour.blue()
        case 'G':
            return discord.Colour.green()
        case 'W':
            return discord.Colour.from_str('#f0e68c')
        case 'B':
            return discord.Colour.from_str('#500B90')
        case _:
            return discord.Colour.gold()


def compute_variants_results(variants: list[Variant]) -> str:
    result = ''
    for variant in variants:
        variant_url = url_from_variant(variant)
        variant_recipe = compute_variant_recipe(variant)
        variant_identity: str = variant.identity  # type: ignore
        result += f'* {convert_mana_identity_to_emoji(variant_identity)} [{variant_recipe}]({variant_url}) (in {variant.popularity} decks)\n'
    return result


def variant_view(variant: Variant) -> ui.LayoutView:
    variant_identity: str = variant.identity  # type: ignore
    container = ui.Container(
        ui.TextDisplay(f'## [{compute_variant_name(variant)}]({url_from_variant(variant)})\n### Identity: {convert_mana_identity_to_emoji(variant_identity)}\n### Results\n{compute_variant_results(variant)}'),
        accent_colour=identity_colour(variant_identity),
    )
    images = [discord.MediaGalleryItem(card.card.image_uri_front_normal) for card in variant.uses if card.card.image_uri_front_normal]
    if images:
        container.add_item(ui.MediaGallery(*images[:10]))
    view = ui.LayoutView()
    view.add_item(container)
    return view


class VariantDetailsSelect(ui.DynamicItem[ui.Select], template='variant-details'):
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Select, match: re.Match[str]):
        return cls(item)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            async with API() as api_client:
                variant = await VariantsApi(api_client).variants_retrieve(id=self.item.values[0])
        except ApiException:
            await interaction.followup.send(content='Failed to fetch the combo.', ephemeral=True)
            return
        await interaction.followup.send(view=variant_view(variant), ephemeral=True)


def variants_view(query_info: SpellbookQuery, variants: list[Variant], count: int) -> ui.LayoutView:
    container = ui.Container(
        ui.TextDisplay(f'### Showing {len(variants)} of {count} results for {query_info.summary}'),
        accent_colour=discord.Colour.from_str('#d68fc5'),
    )
    for variant in variants:
        variant_identity: str = variant.identity  # type: ignore
        container.add_item(ui.Section(
            f'{convert_mana_identity_to_emoji(variant_identity)} {compute_variant_recipe(variant)}\n-# in {variant.popularity} decks',
            accessory=ui.Button(label='View', url=url_from_variant(variant)),
        ))
    container.add_item(ui.ActionRow(VariantDetailsSelect(ui.Select(
        custom_id='variant-details',
        placeholder='Show combo details',
        options=[
            discord.SelectOption(
                label=compute_variant_name(variant)[:100],
                value=variant.id,
                description=compute_variant_results(variant, separator=', ')[:100],
            )
            for variant in variants
        ],
    ))))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


async def handle_queries(queries: list[str], send: Callable[..., Awaitable[Any]]) -> str | None:
    reaction = None
    for query in queries:
        if len(query) > MAX_QUERY_LENGTH:
            await send(content=f'Queries can be at most {MAX_QUERY_LENGTH} characters long.')
            reaction = '⚠'
            continue
        query_info = SpellbookQuery(query)
        try:
            async with API() as api_client:
                api = VariantsApi(api_client)
                result = await api.variants_list(
                    q=query_info.patched_query,
                    limit=MAX_SEARCH_RESULTS,
                    ordering=ORDERING,
                    count=True,
                )
        except ApiException as e:
            data = e.data
            if not isinstance(data, VariantsQueryValidationError):
                await send(content=f'Failed to fetch results for {query_info.summary}', suppress_embeds=True)
                return '❌'
            error_messages = data.q or []
            reply = f'There {'is a problem' if len(error_messages) <= 1 else 'are problems'} with {query_info.summary}'
            if len(error_messages) > 1:
                reply += ':\n' + ''.join(f'\n* {error_message}' for error_message in error_messages)
            elif error_messages:
                reply += f'. {error_messages[0]}'
            await send(content=reply, suppress_embeds=True)
            reaction = '⚠'
            continue
        result_count: int = result.count  # type: ignore
        results: list[Variant] = result.results
        if result_count == 1:
            await send(view=variant_view(results[0]))
        elif result_count > 0:
            await send(view=variants_view(query_info, results, result_count))
        else:
            await send(content=f'No results found for {query_info.summary}', suppress_embeds=True)
    return reaction


@bot.tree.command()
async def search(interaction: discord.Interaction, query: app_commands.Range[str, 1, MAX_QUERY_LENGTH]):
    '''This command returns some results for a Commander Spellbook query.
    Same as {{query}}.

    Parameters
    -----------
    query: str
        The Commander Spellbook query, such as "id=WUB cards=2"
    '''
    await interaction.response.defer(thinking=True)
    await handle_queries([query], interaction.followup.send)


@bot.tree.command()
async def combos(interaction: discord.Interaction, card: str):
    '''This command returns the most popular combos that use a card.

    Parameters
    -----------
    card: str
        The name of the card, such as "Thassa's Oracle"
    '''
    await interaction.response.defer(thinking=True)
    escaped_card = card.replace('"', '\\"')
    await handle_queries([f'card="{escaped_card}"'], interaction.followup.send)


@combos.autocomplete('card')
async def card_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    if not current:
        return []
    async with API() as api_client:
        # only names are needed, and the generated CardDetail model rejects a blank producedMana
        response = await CardsApi(api_client).cards_list_without_preload_content(q=current, limit=25)
        cards = (await response.json())['results']
    return [app_commands.Choice(name=card['name'], value=card['name']) for card in cards if len(card['name']) <= 100]


def can_reply(message: discord.Message) -> bool:
    if message.guild is None:
        return True
    permissions = message.channel.permissions_for(message.guild.me)  # type: ignore
    can_send = permissions.send_messages_in_threads if isinstance(message.channel, discord.Thread) else permissions.send_messages
    return can_send and permissions.read_message_history


async def answer_queries(message: discord.Message):
    queries = parse_queries(message.content)
    if not queries or not can_reply(message):
        return
    await message.add_reaction('🔍')
    reply_ids: list[int] = []

    async def reply(**kwargs):
        reply_ids.append((await message.reply(**kwargs)).id)
    reaction = await handle_queries(queries, reply)
    await message.remove_reaction('🔍', bot.user)  # type: ignore
    if reaction:
        await message.add_reaction(reaction)
    answers[message.id] = (reply_ids, reaction)
    if len(answers) > MAX_TRACKED_MESSAGES:
        del answers[next(iter(answers))]


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if not message.author.bot:
        await answer_queries(message)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.author.bot or parse_queries(before.content) == parse_queries(after.content):
        return
    reply_ids, reaction = answers.pop(after.id, ([], None))
    for reply_id in reply_ids:
        await after.channel.get_partial_message(reply_id).delete()  # type: ignore
    if reaction:
        await after.remove_reaction(reaction, bot.user)  # type: ignore
    await answer_queries(after)


async def handle_find_my_combos(interaction: discord.Interaction, deck: DeckRequest | str):
    try:
        async with API() as api_client:
            api = FindMyCombosApi(api_client)
            if isinstance(deck, str):
                result = await find_my_combos_create_plain(api, deck, ordering=ORDERING)
            else:
                result = await api.find_my_combos_create(deck_request=deck, ordering=ORDERING)
        results_identity: str = result.results.identity  # type: ignore
        reply = f'## Find My Combos results for your deck\n### Deck identity: {convert_mana_identity_to_emoji(results_identity)}\n'
        results_included: list[Variant] = result.results.included
        results_included_by_changing_commanders: list[Variant] = result.results.included_by_changing_commanders
        results_almost_included: list[Variant] = result.results.almost_included
        results_almost_included_by_changing_commanders: list[Variant] = result.results.almost_included_by_changing_commanders
        results_almost_included_by_adding_colors: list[Variant] = result.results.almost_included_by_adding_colors
        results_almost_included_by_adding_colors_and_changing_commanders: list[Variant] = result.results.almost_included_by_adding_colors_and_changing_commanders
        if len(results_included) > 0:
            reply += f'### {len(results_included)} combos found\n'
            reply += compute_variants_results(results_included)
        if len(results_included_by_changing_commanders) > 0:
            reply += f'### {len(results_included_by_changing_commanders)} combos found by changing commanders\n'
            reply += compute_variants_results(results_included_by_changing_commanders)
        if len(results_almost_included) > 0:
            reply += f'### {len(results_almost_included)} potential combos found\n'
            reply += compute_variants_results(results_almost_included)
        if len(results_almost_included_by_changing_commanders) > 0:
            reply += f'### {len(results_almost_included_by_changing_commanders)} potential combos found by changing commanders with the same color identity\n'
            reply += compute_variants_results(results_almost_included_by_changing_commanders)
        if len(results_almost_included_by_adding_colors) > 0:
            reply += f'### {len(results_almost_included_by_adding_colors)} potential combos found by adding colors to the identity\n'
            reply += compute_variants_results(results_almost_included_by_adding_colors)
        if len(results_almost_included_by_adding_colors_and_changing_commanders) > 0:
            reply += f'### {len(results_almost_included_by_adding_colors_and_changing_commanders)} potential combos found by changing commanders and their color identities\n'
            reply += compute_variants_results(results_almost_included_by_adding_colors_and_changing_commanders)
        if len(results_included) == 0 \
            and len(results_included_by_changing_commanders) == 0 \
                and len(results_almost_included) == 0 \
                and len(results_almost_included_by_changing_commanders) == 0 \
                and len(results_almost_included_by_adding_colors) == 0 \
                and len(results_almost_included_by_adding_colors_and_changing_commanders) == 0:
            reply += 'No combos found.'
        chunks = discord_chunk(reply)
        if len(chunks) > MAX_FOLLOWUPS and not interaction.is_guild_integration() and not interaction.context.dm_channel:
            chunks = chunks[:MAX_FOLLOWUPS - 1] + [f'Too many results to list here: add me to this server or use {WEBSITE_URL}/find-my-combos to see them all.']
        for chunk in chunks:
            await interaction.followup.send(content=chunk, suppress_embeds=True, ephemeral=not interaction.context.dm_channel)
        if interaction.message:
            await interaction.message.remove_reaction('🔍', bot.user)  # type: ignore
            await interaction.message.add_reaction('✅')
    except ApiException:
        if interaction.message:
            await interaction.message.remove_reaction('🔍', bot.user)  # type: ignore
            await interaction.message.add_reaction('❌')
        await interaction.followup.send(content='Failed to fetch results.')


class FindMyCombosModal(ui.Modal, title='Find My Combos'):
    def __init__(self):
        super().__init__()
        self.commanders = ui.TextInput(
            placeholder='Codie, Vociferous Codex',
            style=discord.TextStyle.long,
            required=False,
            max_length=300,
        )
        self.main = ui.TextInput(
            placeholder='Brainstorm\nPonder\n...',
            style=discord.TextStyle.long,
            required=False,
        )
        self.decklist_file = ui.FileUpload(required=False)
        self.add_item(ui.Label(text='Commanders', component=self.commanders))
        self.add_item(ui.Label(text='Main', component=self.main))
        self.add_item(ui.Label(text='Decklist file', description='Or upload your deck as a .txt file', component=self.decklist_file))

    async def on_submit(self, interaction: discord.Interaction[commands.Bot]):
        ephemeral = not interaction.context.dm_channel
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)
        if interaction.message is not None:
            await interaction.message.add_reaction('🔍')
        if not self.main.value and not self.decklist_file.values:
            await interaction.followup.send(content='Paste your main deck or upload a decklist file.', ephemeral=ephemeral)
            return
        decklist = f'// Commanders\n{self.commanders.value}\n\n// Main\n{self.main.value}'
        for attachment in self.decklist_file.values:
            if not (attachment.content_type or '').startswith('text/') or attachment.size > MAX_DECKLIST_FILE_SIZE:
                await interaction.followup.send(content=f'The decklist file must be a text file of at most {MAX_DECKLIST_FILE_SIZE // 1000} KB.', ephemeral=ephemeral)
                return
            decklist += '\n' + (await attachment.read()).decode(errors='replace')
        await handle_find_my_combos(interaction=interaction, deck=decklist)


@bot.tree.command(name='find-my-combos')
async def find_my_combos(interaction: discord.Interaction, decklist: str | None = None):
    '''This command searches and suggests combos for your deck. You can either provide
    a decklist url or submit your deck with the modal form.

    Parameters
    -----------
    decklist: str
        The url of a decklist from one of our supported deckbuilding sites.
    '''
    if decklist:
        if uri_validator(decklist):
            await interaction.response.defer(ephemeral=not interaction.context.dm_channel, thinking=True)
            try:
                async with API() as api_client:
                    api = CardListFromUrlApi(api_client)
                    result = await api.card_list_from_url_retrieve(url=decklist)
                await handle_find_my_combos(
                    interaction=interaction,
                    deck=DeckRequest(
                        commanders=[CardInDeckRequest(card=c.card, quantity=c.quantity) for c in result.commanders] if result.commanders else None,
                        main=[CardInDeckRequest(card=c.card, quantity=c.quantity) for c in result.main] if result.main else None,
                    ),
                )
            except ApiException as e:
                data = e.data
                if interaction.message:
                    await interaction.message.add_reaction('❌')
                if isinstance(data, InvalidUrlResponse):
                    await interaction.followup.send(content=f'{data.detail.removesuffix('.')}.', ephemeral=True)
                else:
                    await interaction.followup.send(content='Failed to fetch decklist.', ephemeral=True)
        else:
            await interaction.response.send_message('Invalid url provided.', ephemeral=not interaction.context.dm_channel)
    else:
        await interaction.response.send_modal(FindMyCombosModal())


bot.run(os.getenv('DISCORD_TOKEN', ''), root_logger=True)
