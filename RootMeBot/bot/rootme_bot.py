import discord
import asyncio
import functools
import traceback
import time

from database.manager import DatabaseManager
from database.models.challenge_model import Challenge
from database.models.auteur_model import Auteur

from notify.manager import NotificationManager

from discord.ext import commands
from discord.ext.commands.context import Context
from discord import Embed

from classes.error import *
from classes.challenge import ChallengeData
from classes.auteur import AuteurData

from constants import BOT_PREFIX, LOG_PATH

import utils.messages as utils



class RootMeBot():

    def __init__(self, database_manager: DatabaseManager, notification_manager: NotificationManager, *args, **kwargs) -> None:

        self.intents = discord.Intents.default()
        self.description = """A discord bot to keep up with your progression on www.root-me.org"""
        self.bot = commands.Bot(command_prefix=BOT_PREFIX, description=self.description, intents=self.intents)
        
        self.notification_manager = notification_manager
        self.database_manager = database_manager
    
        self.init_done = False

    async def banned(self):
        await self.bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Game(name="Banned 😞"))

    async def unbanned(self):
        await self.bot.change_presence(status=discord.Status.online, activity=discord.Game(name="😎"))


    async def after_init(self, func):
        print("Check OK after_init")
        return self.init_done

    def check_channel(self):
        async def predicate(context):
            return context.message.channel.id == self.BOT_CHANNEL
        return commands.check(predicate)

    def get_command_args(self, context: commands.context.Context) -> list[str]:
        """Returns args from message"""
        return context.message.content.strip().split()[1:]

    async def init_db(self) -> None:
        """Checks if the database seems populated or not (first run)"""
        await self.bot.wait_until_ready()
        await self.unbanned()
        print("Starting...")
        channel = self.bot.get_channel(self.BOT_CHANNEL)

        if self.database_manager.count_challenges() < 300:

            await utils.init_start(channel)
            await self.database_manager.update_challenges(init=True)
            await utils.init_end(channel)

        print("Done")
        self.init_done = True
        print(self.init_done)


    async def cron_display(self) -> None:
        """Checks if there are new enqueued solves or challenges, and posts them in the right channel"""

        await self.bot.wait_until_ready()

        while not self.init_done:
            await asyncio.sleep(1)
        
        channel = self.bot.get_channel(self.BOT_CHANNEL)

        while True:

            for aut, chall, score_above in self.notification_manager.get_solve_queue():
                if chall:
                    db_chall = await self.database_manager.get_challenge_from_db(chall.idx) 
                    if len(db_chall.solvers) <= 2:
                        is_blood = True
                    else:
                        is_blood = False
                    await utils.send_new_solve(channel, chall, aut, score_above, is_blood)
                    

            for chall in self.notification_manager.get_chall_queue():
                await utils.send_new_challenge(channel, chall)

            await asyncio.sleep(1)

    async def cron_check_challs(self) -> None:
        """Checks for new challs"""
        
        await self.bot.wait_until_ready()

        while not self.init_done:
            await asyncio.sleep(1)

        print("OK challs")
        while True:
            
            await self.database_manager.update_challenges()
            await asyncio.sleep(300)


    async def cron_check_solves(self) -> None:
        """Checks for new solves"""
        await self.bot.wait_until_ready()

        while not self.init_done:
            await asyncio.sleep(1)
        
        print("OK solves")

        while True:

            await self.database_manager.update_users()
            await asyncio.sleep(1)

    def catch(self):
        @self.bot.event
        async def on_ready():
                    for server in self.bot.guilds:
                        print(f'RootMeBot is starting on the following server: "{server.name}" !')



        @self.bot.command(description='Remove user by ID', pass_context=True)
        @commands.check(self.after_init)
        @self.check_channel()
        async def remove_user(context: Context):
            """<id or username>"""

            args = self.get_command_args(context)
            if len(args) < 1:
                await utils.usage(context.message.channel)
                return
            args = str(' '.join(args))

            try:
                idx = int(args)

                aut = await self.database_manager.remove_user_from_db(idx)  
                if aut:
                    await utils.removed_ok(context.message.channel, aut.username)
                else:
                    #Case where username is full numbers
                    args = str(args)
                    raise ValueError()

            except ValueError:
                auteurs = await self.database_manager.remove_user_from_db_by_name(args)
                if len(auteurs) > 1:
                    await utils.multiple_users(context.message.channel, auteurs)
                elif len(auteurs) == 0:
                    await utils.cant_find_user(context.message.channel, args)
                else:
                    await utils.removed_ok(context.message.channel, args)
    

        @self.bot.command(description='Show scoreboard')
        @commands.check(self.after_init)
        @self.check_channel()
        async def scoreboard(context: Context) -> None:
            """ """

            await utils.scoreboard(context.message.channel, self.database_manager)

        @self.bot.command(description='Add user by ID')
        @commands.check(self.after_init)
        @self.check_channel()
        async def add_user_id(context: Context) -> None:
            """<id>"""
            args = self.get_command_args(context)
            if len(args) < 1:
                await utils.usage(context.message.channel)
                return

            try:
                idx = int(args[0])
            except ValueError:
                await utils.incorrect_usage(context.message.channel, args[0])
                return

            aut = await self.database_manager.add_user(idx)
            if aut:
                await utils.added_ok(context.message.channel, aut.username)
            else:
                await utils.cant_find_user(context.message.channel, idx)

        @self.bot.command(description='Add user by name')
        @commands.check(self.after_init)
        @self.check_channel()
        async def add_user(context: Context) -> None:
            """<username>"""
            username = ' '.join(self.get_command_args(context))
            auteurs = await self.database_manager.search_user(username)
            if len(auteurs) > 1:
                await utils.possible_users(context.message.channel, auteurs)
            elif len(auteurs) == 1:
                aut = await self.database_manager.add_user(auteurs[0].idx)
                await utils.added_ok(context.message.channel, aut.username)
            else:
                await utils.cant_find_user(context.message.channel, username)


        @self.bot.command(description='Create a new scoreboard')
        @commands.check(self.after_init)
        @self.check_channel()
        async def add_scoreboard(context: Context) -> None:
            """<scoreboard name>"""

            args = ' '.join(self.get_command_args(context))
            
            scoreboard = await self.database_manager.get_scoreboard(args)
            if not scoreboard:
                scoreboard = await self.database_manager.create_scoreboard(args)

            await utils.add_scoreboard(context.message.channel, scoreboard)




        @self.bot.command(description='Change the lang for the next search')
        @commands.check(self.after_init)
        @self.check_channel()
        async def user_lang(context: Context) -> None:
            """<lang>"""
            args = self.get_command_args(context)
            
            if len(args) < 1:
                await utils.usage(context.message.channel)
                return

            lang = args[0].lower()

            if lang in ["en", "fr", "es", "ru", "de"]:
                self.database_manager.rootme_api.lang = lang

                #Send OK message
                if lang == "en":
                    lang = "gb"
                
                await utils.lang(context.message.channel, lang)
                return
            else:
                await utils.unknown_lang(context.message.channel, lang)



        @self.bot.command(description='Search user by username')
        @commands.check(self.after_init)
        @self.check_channel()
        async def search_user(context: Context) -> None:
            """<username>"""
            
            args = self.get_command_args(context)
            if len(args) < 1:
                await utils.usage(context.message.channel)
                return
            search = str(' '.join(args))
            
            auteurs = await self.database_manager.search_user(search)
            
            if auteurs:
                await utils.possible_users(context.message.channel, auteurs)
            else:
                await utils.cant_find_user(context.message.channel, search)

            
        @self.bot.command(description='Shows stats of a user')
        @commands.check(self.after_init)
        @self.check_channel()
        async def profile(context: Context) -> None:
            """<id or username>"""

            args = self.get_command_args(context)
            if len(args) < 1:
                await utils.usage(context.message.channel)
                return

            search = str(' '.join(args))

            try:
                search_id = int(search)
                auteur = await self.database_manager.get_user_from_db(search_id)

            except ValueError:
                auteurs = await self.database_manager.search_user_from_db(search)

                if len(auteurs) == 0:
                    await utils.cant_find_user(context.message.channel, search)
                    return
                elif len(auteurs) > 1:
                    await utils.multiple_users(context.message.channel, auteurs)
                    return
                else:
                    auteur = auteurs[0]
            

            image_profile = await self.database_manager.rootme_api.get_image_png(auteur.idx)
            
            if not image_profile:
                image_profile = await self.database_manager.rootme_api.get_image_jpg(auteur.idx)
            if not image_profile:
                image_profile = 'https://www.root-me.org/IMG/auton0.png'

            stats_glob = await self.database_manager.get_stats()

            await utils.profile(context.message.channel, auteur, stats_glob, image_profile)




        @self.bot.command(description='Shows who solved a challenge')
        @commands.check(self.after_init)
        @self.check_channel()
        async def who_solved(context: Context) -> None:
            """<challenge name or id>"""

            args = self.get_command_args(context)
            if len(args) < 1:
                await utils.usage(context.message.channel)
                return
            search = str(' '.join(args))

            try:
                #Search by id
                search_id = int(search)

                chall = await self.database_manager.get_challenge_from_db(search_id)                
                
                if chall:
                    await utils.who_solved(context.message.channel, chall)
                else:
                    await utils.cant_find_challenge(context.message.channel, search)

            except ValueError:
                #Search by name
                results = await self.database_manager.search_challenge_from_db(search)
                if len(results) > 1:
                    await utils.multiple_challenges(context.message.channel, results)
                
                elif len(results) == 1:
                    chall = results[0]
                    await utils.who_solved(context.message.channel, chall)

                else:
                    await utils.cant_find_challenge(context.message.channel, search)

    def start(self, TOKEN, BOT_CHANNEL):
        """Starts the bot"""
        
        self.BOT_CHANNEL = BOT_CHANNEL
        print("START")
        self.catch()
        self.bot.loop.create_task(self.init_db())
        self.check_solves = self.bot.loop.create_task(self.cron_check_solves())
        self.check_challs = self.bot.loop.create_task(self.cron_check_challs())
        self.bot.loop.create_task(self.cron_display())


        self.bot.run(TOKEN)







        
