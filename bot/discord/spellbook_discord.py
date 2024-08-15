import os
import re
import discord
import logging
from itertools import chain
from urllib.parse import quote_plus as encode_query
from discord.ext import commands
from discord import ui, utils
from anonymous_spellbook_client import AnonymousSpellbookClient
from kiota_abstractions.api_error import APIError
from spellbook_client import RequestConfiguration
from spellbook_client.models.variant import Variant
from spellbook_client.models.deck_request import DeckRequest
from discord_utils import discord_chunk, chunk_diff_async


intents = discord.Intents(messages=True)
intents.message_content = True
bot = commands.Bot(
    command_prefix='?',
    intents=intents,
    description='Powered by [Commander Spellbook](https://commanderspellbook.com/)',
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
administration_guilds = [int(guild) for guild in (os.getenv(f'ADMIN_GUILD__{i}') for i in range(10)) if guild is not None]
administration_users = [int(user) for user in (os.getenv(f'ADMIN_USER__{i}') for i in range(10)) if user is not None]
API = AnonymousSpellbookClient(base_url=os.getenv('SPELLBOOK_API_URL', ''))
WEBSITE_URL = os.getenv('SPELLBOOK_WEBSITE_URL', '')
MAX_SEARCH_RESULTS = 8


@bot.command()
async def sync(ctx: commands.Context):
    if ctx.guild is not None and ctx.guild.id in administration_guilds or ctx.author.id in administration_users:
        await ctx.message.add_reaction('👍')
        await bot.tree.sync(guild=ctx.guild)
        await ctx.message.remove_reaction('👍', bot.user)
        await ctx.message.add_reaction('✅')


@bot.tree.command()
async def invite(interaction: discord.Interaction):
    invite_link = utils.oauth_url(bot.user.id, permissions=permissions)
    button = ui.Button(label='Invite', url=invite_link, style=discord.ButtonStyle.link)
    view = ui.View()
    view.add_item(button)
    await interaction.response.send_message('Invite me to your server!', view=view)


@bot.event
async def on_guild_join(guild: discord.Guild):
    logging.info(f'Joined guild: {guild.name}')
    await bot.tree.sync(guild=guild)


QUERY_REGEX = re.compile(r'{{(.*?)}}')


def compute_variant_name(variant: Variant):
    return ' + '.join(chain(
        ((f'{card.quantity}x ' if card.quantity > 1 else '') + card.card.name for card in variant.uses),
        ((f'{template.quantity}x ' if template.quantity > 1 else '') + template.template.name for template in variant.requires),
    ))


def compute_variant_results(variant: Variant):
    return '\n'.join(
        (f'{result.quantity}x ' if result.quantity > 1 else '') + result.feature.name
        for result in variant.produces
    )


def convert_mana_identity_to_emoji(identity: str):
    return identity \
        .replace('C', '<:manac:673716795667906570>') \
        .replace('W', '<:manaw:673716795991130151>') \
        .replace('U', '<:manau:673716795890335747>') \
        .replace('B', '<:manab:673716795651391519>') \
        .replace('R', '<:manar:673716795978285097>') \
        .replace('G', '<:manag:673716795491876895>')


def compute_variants_results(variants: list[Variant]):
    result = ''
    for variant in variants:
        variant_url = f'{WEBSITE_URL}/combo/{variant.id}'
        variant_name = compute_variant_name(variant)
        variant_results = ', '.join(result.feature.name for result in variant.produces[:4]) + ('...' if len(variant.produces) > 4 else '')
        result += f'* {convert_mana_identity_to_emoji(variant.identity)} [{variant_name} ➜ {variant_results}]({variant_url}) (in {variant.popularity} decks)\n'
    return result


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if message.author.bot:
        return
    queries = []
    for match in QUERY_REGEX.finditer(message.content):
        query = match.group(1).strip()
        if query:
            queries.append(query)
    if not queries:
        return
    await message.add_reaction('🔍')
    embed: discord.Embed | None = None
    reply = ''
    messages: list[discord.Message] = []
    for query in queries:
        patched_query = query
        if not any(f'{key}:' in patched_query for key in ('legal', 'banned', 'format')):
            patched_query += ' format:commander'
        query_url = f'{WEBSITE_URL}/search/?q={encode_query(query)}'
        query_summary = f'["`{query}`"]({query_url})'
        try:
            result = await API.variants.get(
                request_configuration=RequestConfiguration[API.variants.VariantsRequestBuilderGetQueryParameters](
                    query_parameters=API.variants.VariantsRequestBuilderGetQueryParameters(
                        q=patched_query,
                        limit=MAX_SEARCH_RESULTS,
                        ordering='-popularity',
                    ),
                ),
            )
            if len(queries) == 1 and len(result.results) == 1:
                variant = result.results[0]
                variant_url = f'{WEBSITE_URL}/combo/{variant.id}'
                match variant.identity[:1]:
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
                    description=f'### Identity: {convert_mana_identity_to_emoji(variant.identity)}\n\n### Results\n{compute_variant_results(variant)}',
                )
                reply += f'\n\n### Showing 1 result for {query_summary}\n\n'
            elif len(result.results) > 0:
                if len(queries) == 1:
                    embed = discord.Embed(
                        colour=discord.Colour.from_str('#d68fc5'),
                        title=f'View all results for "`{query}`" on Commander Spellbook',
                        url=query_url,
                    )
                limit_results = min(MAX_SEARCH_RESULTS, len(result.results))
                reply += f'\n\n### Showing {limit_results} of {result.count} results for {query_summary}\n\n'
                reply += compute_variants_results(result.results[:limit_results])
            else:
                reply += f'\n\nNo results found for {query_summary}'
            chunks = discord_chunk(reply)
            messages = await chunk_diff_async(
                new_chunks=chunks,
                add=lambda i, c: message.reply(content=c, suppress_embeds=embed is None or i != len(chunks) - 1, embed=embed if i == len(chunks) - 1 else None),
                update=lambda i, m, c: m.edit(content=c, suppress=embed is None or i != len(chunks) - 1, embed=embed if i == len(chunks) - 1 else None),
                remove=lambda _, m: m.delete(),
                old_chunks_wrappers=messages,
                unwrap=lambda m: m.content,
            )
        except APIError:
            await message.remove_reaction('🔍', bot.user)
            await message.add_reaction('❌')
            reply += f'\n\nFailed to fetch results for `{query}`'
            chunks = discord_chunk(reply)
            messages = await chunk_diff_async(
                new_chunks=chunks,
                add=lambda i, c: message.reply(content=c, suppress_embeds=embed is None or i != len(chunks) - 1, embed=embed if i == len(chunks) - 1 else None),
                update=lambda i, m, c: m.edit(content=c, suppress=embed is None or i != len(chunks) - 1, embed=embed if i == len(chunks) - 1 else None),
                remove=lambda _, m: m.delete(),
                old_chunks_wrappers=messages,
                unwrap=lambda m: m.content,
            )
            break
    await message.remove_reaction('🔍', bot.user)


DECKLIST_LINE_REGEX = re.compile(r'^(?:\d+x?\s+)?(.*?)(?:(?:\s+<\w+>)?\s+\[\w+\](?:\s+\(\w+\))?)?$')


def process_decklist(decklist: str) -> list[str]:
    result = []
    for line in decklist.split('\n'):
        line = line.strip()
        if line and not line.startswith('//'):
            match = DECKLIST_LINE_REGEX.match(line)
            if match:
                result.append(match.group(1).strip())
    return result


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
        if interaction.message is not None:
            await interaction.message.add_reaction('🔍')
        commanders = process_decklist(self.commanders.value)
        main = process_decklist(self.main.value)
        try:
            result = await API.find_my_combos.post(
                body=DeckRequest(
                    commanders=commanders,
                    main=main,
                )
            )
            reply = f'## Find My Combos results for your deck\n### Deck identity: {convert_mana_identity_to_emoji(result.results.identity)}\n'
            if len(result.results.included) > 0:
                reply += f'### {len(result.results.included)} combos found\n'
                reply += compute_variants_results(result.results.included)
            if len(result.results.included_by_changing_commanders) > 0:
                reply += f'### {len(result.results.included_by_changing_commanders)} combos found by changing commanders\n'
                reply += compute_variants_results(result.results.included_by_changing_commanders)
            if len(result.results.almost_included) > 0:
                reply += f'### {len(result.results.almost_included)} potential combos found\n'
                reply += compute_variants_results(result.results.almost_included)
            if len(result.results.almost_included_by_changing_commanders) > 0:
                reply += f'### {len(result.results.almost_included_by_changing_commanders)} potential combos found by changing commanders with the same color identity\n'
                reply += compute_variants_results(result.results.almost_included_by_changing_commanders)
            if len(result.results.almost_included_by_adding_colors) > 0:
                reply += f'### {len(result.results.almost_included_by_adding_colors)} potential combos found by adding colors to the identity\n'
                reply += compute_variants_results(result.results.almost_included_by_adding_colors)
            if len(result.results.almost_included_by_adding_colors_and_changing_commanders) > 0:
                reply += f'### {len(result.results.almost_included_by_adding_colors_and_changing_commanders)} potential combos found by changing commanders and their color identities\n'
                reply += compute_variants_results(result.results.almost_included_by_adding_colors_and_changing_commanders)
            if len(result.results.included) == 0 \
                and len(result.results.included_by_changing_commanders) == 0 \
                    and len(result.results.almost_included) == 0 \
                    and len(result.results.almost_included_by_changing_commanders) == 0 \
                    and len(result.results.almost_included_by_adding_colors) == 0 \
                    and len(result.results.almost_included_by_adding_colors_and_changing_commanders) == 0:
                reply += 'No combos found.'
            if interaction.guild is not None:
                chunks = discord_chunk(reply)
                await chunk_diff_async(
                    new_chunks=chunks,
                    add=lambda _, c: interaction.user.send(content=c, suppress_embeds=True),
                )
                await interaction.response.send_message('I\'ve sent your results in a DM!', ephemeral=True)
            else:
                await chunk_diff_async(
                    new_chunks=discord_chunk(reply),
                    add=lambda i, c: interaction.response.send_message(content=c, suppress_embeds=True) if i == 0 else interaction.user.send(content=c, suppress_embeds=True),
                )
            if interaction.message:
                await interaction.message.remove_reaction('🔍', bot.user)
                await interaction.message.add_reaction('✅')
        except APIError:
            if interaction.message is not None:
                await interaction.message.remove_reaction('🔍', bot.user)
                await interaction.message.add_reaction('❌')
            else:
                await interaction.response.send_message('Failed to fetch results.', ephemeral=True)


@bot.tree.command(name='find-my-combos')
async def find_my_combos(interaction: discord.Interaction):
    await interaction.response.send_modal(FindMyCombosModal())


bot.run(os.getenv('DISCORD_TOKEN', ''))
