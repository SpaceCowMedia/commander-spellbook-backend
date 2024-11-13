import os
import discord
import logging
from discord.ext import commands
from discord import ui, utils
from spellbook_client import ApiException, Variant, VariantsApi, InvalidUrlResponse, VariantsQueryValidationError, DeckRequest, CardInDeckRequest, FindMyCombosApi, CardListFromUrlApi
from spellbook_client.extensions import find_my_combos_create_plain
from text_utils import discord_chunk, chunk_diff_async
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
administration_guilds = [int(guild) for guild in (os.getenv(f'KUBE_ADMIN_GUILD__{i}', os.getenv(f'ADMIN_GUILD__{i}')) for i in range(10)) if guild is not None]
administration_users = [int(user) for user in (os.getenv(f'KUBE_ADMIN_USER__{i}', os.getenv(f'ADMIN_USER__{i}')) for i in range(10)) if user is not None]

MAX_SEARCH_RESULTS = 7
ORDERING = '-popularity,identity_count,card_count,-created'


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


def convert_mana_identity_to_emoji(identity: str):
    return identity \
        .replace('C', '<:manac:673716795667906570>') \
        .replace('W', '<:manaw:673716795991130151>') \
        .replace('U', '<:manau:673716795890335747>') \
        .replace('B', '<:manab:673716795651391519>') \
        .replace('R', '<:manar:673716795978285097>') \
        .replace('G', '<:manag:673716795491876895>')


def compute_variants_results(variants: list[Variant]) -> str:
    result = ''
    for variant in variants:
        variant_url = url_from_variant(variant)
        variant_recipe = compute_variant_recipe(variant)
        variant_identity: str = variant.identity  # type: ignore
        result += f'* {convert_mana_identity_to_emoji(variant_identity)} [{variant_recipe}]({variant_url}) (in {variant.popularity} decks)\n'
    return result


async def handle_queries(
    queries: list[str],
    interaction: discord.Interaction | None = None,
    message: discord.Message | None = None,
):
    if interaction is not None and message is not None:
        raise ValueError('Either interaction or message must be provided')
    if interaction is None and message is None:
        raise ValueError('Either interaction or message must be provided, not both')
    if message:
        await message.add_reaction('🔍')
    reply = ''
    embed: discord.Embed | None = None
    chunks: list[str] = []

    def add_kwargs(i: int, c: str):
        return {
            'content': c,
            'suppress_embeds': embed is None or i != len(chunks) - 1,
            'embed': embed if i == len(chunks) - 1 else None,
        }
    messages: list[discord.Message] = []
    for query in queries:
        query_info = SpellbookQuery(query)
        try:
            async with API() as api_client:
                api = VariantsApi(api_client)
                result = await api.variants_list(
                    q=query_info.patched_query,
                    limit=MAX_SEARCH_RESULTS,
                    ordering=ORDERING,
                )
            result_count: int = result.count
            results: list[Variant] = result.results
            if len(queries) == 1 and result_count == 1:
                variant = results[0]
                variant_url = url_from_variant(variant)
                variant_identity: str = variant.identity  # type: ignore
                match variant_identity[:1]:
                    case 'C':
                        variant_color = discord.Colour.light_grey()
                    case 'R':
                        variant_color = discord.Colour.red()
                    case 'U':
                        variant_color = discord.Colour.blue()
                    case 'G':
                        variant_color = discord.Colour.green()
                    case 'W':
                        variant_color = discord.Colour.from_str('#f0e68c')
                    case 'B':
                        variant_color = discord.Colour.from_str('#500B90')
                    case _:
                        variant_color = discord.Colour.gold()
                embed = discord.Embed(
                    colour=variant_color,
                    title=compute_variant_name(variant),
                    url=variant_url,
                    description=f'### Identity: {convert_mana_identity_to_emoji(variant_identity)}\n\n### Results\n{compute_variant_results(variant)}',
                )
                reply += f'\n\n### Showing 1 result for {query_info.summary}\n\n'
            elif result_count > 0:
                if len(queries) == 1:
                    embed = discord.Embed(
                        colour=discord.Colour.from_str('#d68fc5'),
                        title=f'View all results for "`{query}`" on Commander Spellbook',
                        url=query_info.url,
                    )
                reply += f'\n\n### Showing {len(results)} of {result_count} results for {query_info.summary}\n\n'
                reply += compute_variants_results(results)
            else:
                reply += f'\n\nNo results found for {query_info.summary}'
        except ApiException as e:
            data = e.data
            if isinstance(data, VariantsQueryValidationError):
                error_messages = data.q or []
                if message:
                    await message.remove_reaction('🔍', bot.user)  # type: ignore
                    await message.add_reaction('⚠')
                reply += f'\n\nThere {'is a problem' if len(error_messages) <= 1 else 'are problems'} with {query_info.summary}'
                if error_messages:
                    if len(error_messages) > 1:
                        reply += ':\n'
                        for error_message in error_messages:
                            reply += f'\n* {error_message}'
                    else:
                        reply += f'. {error_messages[0]}'
            else:
                if message:
                    await message.remove_reaction('🔍', bot.user)  # type: ignore
                    await message.add_reaction('❌')
                reply += f'\n\nFailed to fetch results for {query_info.summary}'
                if message:
                    chunks = discord_chunk(reply)
                    messages = await chunk_diff_async(
                        new_chunks=chunks,
                        add=lambda i, c: message.reply(**add_kwargs(i, c)),
                        update=lambda i, m, c: m.edit(content=c, suppress=embed is None or i != len(chunks) - 1, embed=embed if i == len(chunks) - 1 else None),
                        remove=lambda _, m: m.delete(),
                        old_chunks_wrappers=messages,
                        unwrap=lambda m: m.content,
                    )
                break
        if message:
            chunks = discord_chunk(reply)
            messages = await chunk_diff_async(
                new_chunks=chunks,
                add=lambda i, c: message.reply(**add_kwargs(i, c)),
                update=lambda i, m, c: m.edit(content=c, suppress=embed is None or i != len(chunks) - 1, embed=embed if i == len(chunks) - 1 else None),
                remove=lambda _, m: m.delete(),
                old_chunks_wrappers=messages,
                unwrap=lambda m: m.content,
            )
    if message:
        await message.remove_reaction('🔍', bot.user)  # type: ignore
    if interaction:
        chunks = discord_chunk(reply)
        await chunk_diff_async(
            new_chunks=chunks,
            add=lambda i, c: interaction.response.send_message(**add_kwargs(i, c)) if i == 0 else interaction.followup.send(**add_kwargs(i, c)),
        )


@bot.tree.command()
async def search(interaction: discord.Interaction, query: str):
    '''This command returns some results for a Commander Spellbook query.
    Same as {{query}}.

    Parameters
    -----------
    query: str
        The Commander Spellbook query, such as "id=WUB cards=2"
    '''
    if query:
        await handle_queries([query], interaction=interaction)
    else:
        await interaction.response.send_message(content='Missing query after command')


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if message.author.bot:
        return
    queries = parse_queries(message.content)
    if not queries:
        return
    await handle_queries(queries, message=message)


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
        if interaction.guild:
            await interaction.followup.send(content='I\'ve sent your results in a DM!')
            chunks = discord_chunk(reply)
            await chunk_diff_async(
                new_chunks=chunks,
                add=lambda _, c: interaction.user.send(content=c, suppress_embeds=True),
            )
        else:
            await chunk_diff_async(
                new_chunks=discord_chunk(reply),
                add=lambda _, c: interaction.followup.send(content=c, suppress_embeds=True),
            )
        if interaction.message:
            await interaction.message.remove_reaction('🔍', bot.user)  # type: ignore
            await interaction.message.add_reaction('✅')
    except ApiException:
        if interaction.message:
            await interaction.message.remove_reaction('🔍', bot.user)  # type: ignore
            await interaction.message.add_reaction('❌')
        await interaction.followup.send(content='Failed to fetch results.')


class FindMyCombosModal(ui.Modal, title='Find My Combos'):
    commanders = ui.TextInput(
        label='Commanders',
        placeholder='Codie, Vociferous Codex',
        style=discord.TextStyle.long,
        required=False,
        max_length=300,
    )
    main = ui.TextInput(
        label='Main',
        placeholder='Brainstorm\nPonder\n...',
        style=discord.TextStyle.long,
    )

    async def on_submit(self, interaction: discord.Interaction[commands.Bot]) -> None:
        await interaction.response.defer(ephemeral=interaction.guild is not None, thinking=True)
        if interaction.message is not None:
            await interaction.message.add_reaction('🔍')
        decklist = f'// Commanders\n{self.commanders.value}\n\n// Main\n{self.main.value}'
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
            await interaction.response.defer(ephemeral=interaction.guild is not None, thinking=True)
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
            await interaction.response.send_message('Invalid url provided.', ephemeral=interaction.guild is not None)
    else:
        await interaction.response.send_modal(FindMyCombosModal())


bot.run(os.getenv('KUBE_DISCORD_TOKEN', os.getenv('DISCORD_TOKEN', '')))
