import discord
import aiohttp
import code
import traceback
from html import unescape

from discord.utils import escape_markdown
from discord.channel import TextChannel

from database.manager import DatabaseManager

from classes.enums import Color, Stats
from classes.views import ManageView, ScoreboardView, MultipleChallFoundView, MultipleUserFoundView
from constants import PING_DEV, PING_ROLE_ROOTME

from database.models.auteur_model import Auteur
from database.models.scoreboard_model import Scoreboard
from database.models.challenge_model import Challenge

import utils.messages as utils

Auteurs = list[Auteur]
Challenges = list[Challenge]

async def init_start(channel: TextChannel) -> None:
    """First time running message"""

    message_title = f"Welcome ! :smile:"

    message = f'This seems to be the first time running the bot, please wait while the database is being initialized !'

    embed = discord.Embed(color=Color.INFO_BLUE.value, title=message_title, description=message)
    await channel.send(embed=embed)

async def incorrect_usage(channel: TextChannel) -> None:

    message_title = 'Error :frowning:'
    message = f'See !help'
    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)
    await channel.send(embed=embed)


async def init_end(channel: TextChannel) -> None:
    """Initialization complete"""

    message_title = f'All done !'

    message = f'You can now add users ! See !help for more infos'

    embed = discord.Embed(color=Color.INFO_BLUE.value, title=message_title, description=message)
    await channel.send(embed=embed)

async def panic_message(channel: TextChannel, error, where):
    """Send panic message"""
    ping = f'<@{PING_DEV}>'
    message = f"ERROR in **{where}**"
    message += f'\n Type {type(error)}: **{error}**\n\n'
    error_msg = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    limit = 4096 - len(message)
    if len(error_msg) > limit:
        nb = (len(error_msg)//limit)+1
        for i in range(nb):
            message_title = f":fire: Kernel Panic {i+1}/{nb} :fire:"
            the_message = message + error_msg[:min([limit, len(error_msg)])]
            print('len',len(the_message))
            embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=the_message)
            await channel.send(ping,embed=embed)
            error_msg = error_msg[min([limit, len(error_msg)]):]
            message_title = f":fire: Kernel Panic {1}/{(len(error_msg)//1024)+1} :fire:"
    else:
        message_title = ":fire: Kernel Panic :fire:"
        message += f'\n\n'+error_msg
        embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)
        await channel.send(ping,embed=embed)


async def send_new_solve(channel: TextChannel, chall: Challenge, aut: Auteur, above: tuple[str, int], is_blood: bool) -> None:
    """Posts a new solve in the right channel"""

    if is_blood:
        emoji = ':drop_of_blood:'
    elif chall.difficulty == "Très difficile":
        emoji = ':fire:'
    else:
        emoji = ':partying_face:'

    message_title = f'New challenge solved by {escape_markdown(aut.username)} {emoji}'

    val = [val for val in chall.validation_chall if val.auteur_id == aut.idx][0]

    message = f' • {unescape(chall.title)} ({chall.score} points)'
    message += f'\n • Category: {chall.category}'
    message += f'\n • Difficulty: {chall.difficulty}'
    message += f'\n • New score: {aut.score}'
    message += f'\n • Date: {val.date.strftime("%d/%m/%y %Hh%Mm%Ss")}'

    embed = discord.Embed(color=Color.NEW_YELLOW.value, title=message_title, description=message)

    if above[1]:
        footer = f'{above[1] - aut.score} points to overtake {above[0]}'
        embed.set_footer(text=footer)

    await channel.send(embed=embed)


async def send_new_challenge(channel: TextChannel, chall: Challenge) -> None:
    """Posts a new challenge in the right channel"""

    ping = f'<@&{PING_ROLE_ROOTME}>'
    message_title = f'New Challenge ! :open_mouth:'

    message = f' • {unescape(chall.title)} ({chall.score} points)'
    message += f'\n • Category: {chall.category}'
    message += f'\n • Difficulty: {chall.difficulty}'

    embed = discord.Embed(color=Color.NEW_YELLOW.value, title=message_title, description=message)
    await channel.send(ping, embed=embed)


async def scoreboard_choice(channel: TextChannel, db_manager: DatabaseManager) -> None:
    view = ScoreboardView(channel, db_manager)
    await channel.send('Choose which scoreboard: ', view=view)

async def daily_scoreboard(channel: TextChannel, scoreboard) -> None:
    scoreboard.sort(key=lambda x: x[1], reverse=True)
    message = ''
    for user in scoreboard:
        message += f' • • • {escape_markdown(user[0])} --> {user[1]} \n'
    embed = discord.Embed(color=Color.SCOREBOARD_WHITE.value, title="Daily Scoreboard", description=message)
    await channel.send(embed=embed)

async def show_image(channel: TextChannel) -> None:
    embed = discord.Embed(color=Color.SCOREBOARD_WHITE.value)
    file = discord.File("/tmp/file.png", filename="image.png")
    embed.set_image(url="attachment://image.png")
    await channel.send(file=file,embed=embed)

async def scoreboard(channel: TextChannel, database_manager: DatabaseManager, name: str) -> None:

    sc = await database_manager.get_scoreboard(name)
    if not sc:
        await utils.cant_find_scoreboard(channel, name)
        return

    users = sc.users

    if not users:
       embed = discord.Embed(color=0xff0000, title='Error', description=f'No users in scoreboard {sc.name} :frowning:')

    else:
       users.sort(key=lambda x: x.score, reverse=True)
       message_title = f'Scoreboard {sc.name}'
       message = ''
       for user in users:
           message += f' • • • {escape_markdown(user.username)} --> {user.score} \n'

       embed = discord.Embed(color=Color.SCOREBOARD_WHITE.value, title=message_title, description=message)

    await channel.send(embed=embed)


async def added_ok(channel: TextChannel, username: str) -> None:

    message_title = 'Success'
    message = f'{escape_markdown(username)} was successfully added :+1:'

    embed = discord.Embed(color=Color.SUCCESS_GREEN.value, title=message_title, description=message)
    await channel.send(embed=embed)

async def cant_find_user(channel: TextChannel, data: str) -> None:

    message_title = 'Error'
    message = f'Cant find user {escape_markdown(data)} :frowning:'

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)

    await channel.send(embed=embed)

async def cant_find_challenge(channel: TextChannel, data: str) -> None:

    message_title = 'Error'
    message = f'Cant find challenge {escape_markdown(data)} :frowning:'

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)

    await channel.send(embed=embed)

async def cant_find_scoreboard(channel: TextChannel, data: str) -> None:

    message_title = 'Error'
    message = f'Cant find scoreboard {escape_markdown(data)} :frowning:'

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)

    await channel.send(embed=embed)

async def cant_create_scoreboard(channel: TextChannel) -> None:

    message_title = 'Error'
    message = f'Cant create scoreboard with empty name :frowning:'

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)

    await channel.send(embed=embed)

async def removed_ok(channel: TextChannel, username: str) -> None:

    message_title = 'Success'
    message = f'{escape_markdown(username)} was succesfully removed :wave:'

    embed = discord.Embed(color=Color.SUCCESS_GREEN.value, title=message_title, description=message)
    await channel.send(embed=embed)


async def possible_users(channel: TextChannel, db_manager: DatabaseManager, auteurs: Auteurs) -> None:

    message = f'Multiple users found :'

    view = MultipleUserFoundView(channel, db_manager, auteurs)

    await channel.send(message, view=view)

async def many_users(channel: TextChannel, auteurs: Auteurs) -> None:

    message_title = 'Possibles users'

    message = ''
    for auteur in auteurs:
        message += f' • • • {escape_markdown(auteur.username)}: {auteur.score} points --> ID {auteur.idx}\n'

    embed = discord.Embed(color=Color.INFO_BLUE.value, title=message_title, description=message)
    await channel.send(embed=embed)


async def who_solved(channel: TextChannel, chall: Challenge, Session) -> None:

    message_title = f'Solvers of {unescape(chall.title)} :sunglasses:'
    message = ''
    with Session.begin() as session:
        chall = session.merge(chall)

        for auteur in chall.solvers:
            if auteur is None:
                continue
            message += f' • • • {escape_markdown(auteur.username)}\n'


    embed = discord.Embed(color=Color.INFO_BLUE.value, title=message_title, description=message)
    await channel.send(embed=embed)


async def many_challenges(channel: TextChannel, challenges: Challenges) -> None:

    message_title = f'Multiple challenges found :thinking:'

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title)

    first_column = ''
    second_column = ''
    for chall in challenges:
        first_column += f'\n{unescape(chall.title)}'
        second_column += f'\n{chall.idx}'

    embed.add_field(name=f'Title', value=first_column, inline=True)
    embed.add_field(name=f'ID', value=second_column, inline=True)

    await channel.send(embed=embed)

async def multiple_challenges(channel: TextChannel, challenges: Challenges, Session) -> None:

    message = f'Multiple challenges found :'

    view = MultipleChallFoundView(channel, challenges, Session)

    await channel.send(message, view=view)



async def multiple_users(channel: TextChannel, auteurs: Auteurs) -> None:
    message_title = f'Multiple users match :thinking:'
    first_column = ''
    second_column = ''
    third_column = ''

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title)

    for aut in auteurs:
        first_column += f'\n{escape_markdown(aut.username)}'
        second_column +=  f'\n{aut.score}'
        third_column +=  f'\n{aut.idx}'

    embed.add_field(name=f'Username', value=first_column, inline=True)
    embed.add_field(name=f'Score', value=second_column, inline=True)
    embed.add_field(name=f'ID', value=third_column, inline=True)
    await channel.send(embed=embed)


async def profile(channel: TextChannel, data: tuple[str, int, int], solves: dict, stats_glob: list[int], image_url: str) -> None:

    username, score, rank = data

    message_title = f'Profile of {username}'

    first_column = f'**\nWeb Client**'
    first_column += f'\n{solves[Stats.WEB_CLIENT]}/{stats_glob[Stats.WEB_CLIENT]}'
    first_column += f'\n**App-Script**'
    first_column += f'\n{solves[Stats.APP_SCRIPT]}/{stats_glob[Stats.APP_SCRIPT]}'
    first_column += f'\n**Programmation**'
    first_column += f'\n{solves[Stats.PROGRAMMING]}/{stats_glob[Stats.PROGRAMMING]}'
    first_column += f'\n**Cracking**'
    first_column += f'\n{solves[Stats.CRACKING]}/{stats_glob[Stats.CRACKING]}'
    first_column += f'\n**Reseau**'
    first_column += f'\n{solves[Stats.NETWORK]}/{stats_glob[Stats.NETWORK]}'
    first_column += f'\n**App-Système**'
    first_column += f'\n{solves[Stats.APP_SYSTEM]}/{stats_glob[Stats.APP_SYSTEM]}'

    second_column = f'**\nWeb Serveur**'
    second_column += f'\n{solves[Stats.WEB_SERVER]}/{stats_glob[Stats.WEB_SERVER]}'
    second_column += f'\n**Cryptanalyse**'
    second_column += f'\n{solves[Stats.CRYPTANALYSIS]}/{stats_glob[Stats.CRYPTANALYSIS]}'
    second_column += f'\n**Steganographie**'
    second_column += f'\n{solves[Stats.STEGANOGRAPHY]}/{stats_glob[Stats.STEGANOGRAPHY]}'
    second_column += f'\n**Realiste**'
    second_column += f'\n{solves[Stats.REALIST]}/{stats_glob[Stats.REALIST]}'
    second_column += f'\n**Forensic**'
    second_column += f'\n{solves[Stats.FORENSICS]}/{stats_glob[Stats.FORENSICS]}'

    embed = discord.Embed(color=Color.INFO_BLUE.value, title=message_title)

    embed.add_field(name=f'Score: {score}', value=first_column, inline=True)
    embed.add_field(name=f'**\n**', value=f'**\n**', inline=True)
    embed.add_field(name=f'Rank: {rank}', value=second_column, inline=True)

    embed.set_thumbnail(url=image_url)


    await channel.send(embed=embed)



async def usage(channel: TextChannel) -> None:


    message_title = f'Error'
    message = f'Incorrect usage, see !help'

    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)
    await channel.send(embed=embed)

async def lang(channel: TextChannel, lang: str) -> None:

    message_title = f"Lang changed"
    message = f'The lang for the next search has been updated ! :flag_{lang}:'
    embed = discord.Embed(color=Color.SUCCESS_GREEN.value, title=message_title, description=message)
    await channel.send(embed=embed)

async def unknown_lang(channel: TextChannel, lang: str) -> None:
    message_title = f"Unknown lang"
    message = f'Can\'t find lang {escape_markdown(lang)}. Available languages are : "en", "fr", "de", "es", "ru"'
    embed = discord.Embed(color=Color.ERROR_RED.value, title=message_title, description=message)
    await channel.send(embed=embed)


async def add_scoreboard(channel: TextChannel, sc: Scoreboard) -> None:
    message_title = f"Scoreboard Created"
    message = f'Scoreboard {escape_markdown(sc.name)} was successfully created :+1:'
    embed = discord.Embed(color=Color.SUCCESS_GREEN.value, title=message_title, description=message)
    await channel.send(embed=embed)

async def manage_user(channel: TextChannel, db_manager: DatabaseManager, auteur: Auteur) -> None:
    message_title = 'Edit user'
    message = f'Choose the scoreboards {escape_markdown(auteur.username)} is part of'
    view = ManageView(db_manager, auteur)
    embed = discord.Embed(color=Color.SCOREBOARD_WHITE.value, title=message_title, description=message)
    await channel.send(embed=embed, view=view)



