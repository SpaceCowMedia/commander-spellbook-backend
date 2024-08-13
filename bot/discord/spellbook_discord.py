import os
from discord.ext import commands
from discord import Intents, Interaction, Message, Guild, ui, TextStyle


intents = Intents(messages=True)
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)


@bot.command()
async def sync(ctx: commands.Context):
    await ctx.message.add_reaction('👍')
    await bot.tree.sync(guild=ctx.guild)
    print('Synced')


@bot.event
async def on_guild_join(guild: Guild):
    print(f'Joined guild: {guild.name}')
    await bot.tree.sync(guild=guild)


@bot.event
async def on_message(message: Message):
    await bot.process_commands(message)
    if message.author.bot:
        return
    if '{{' in message.content:
        await message.add_reaction('👀')


class FindMyCombosModal(ui.Modal, title='Find My Combos'):
    commanders = ui.TextInput(
        label='Commanders',
        placeholder='Codie, Vociferous Codex',
        style=TextStyle.long,
        required=False,
    )
    main = ui.TextInput(
        label='Main',
        placeholder='Brainstorm\nPonder\n...',
        style=TextStyle.long,
    )

    async def on_submit(self, interaction: Interaction[commands.Bot]) -> None:
        await interaction.response.send_message('Thanks for your submission!', ephemeral=True)


@bot.tree.command(name='find-my-combos')
async def find_my_combos(interaction: Interaction):
    await interaction.response.send_modal(FindMyCombosModal())


bot.run(os.getenv('DISCORD_TOKEN', ''))
