import os
import random
import asyncio
from dotenv import load_dotenv
from discord import *
import requests
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#Embed declarations
embed_next_player = Embed(title = "It's now your turn!", value = "Please play one of your cards!")
embed= Embed(title="Sueca", description="Bem vindos ao jogo da sueca!", color=0x2e6cbd)
embed.add_field(name = "Please React to This Message with your corresponding team to Enter the Game!", value = "We are waiting 30 seconds for people!")
embed.set_image(url = "https://i1.wp.com/etili.co/wp-content/uploads/2018/09/sueca.jpg?fit=900%2C665")
embed_invalid = Embed(title = "No people!", description = "No one wants to play sueca! Sad!",color = 0xd23b20)
embed_shit = Embed(title = "Too many people on one team!", description = "Aborting the game!",color=0x2e6cbd )
embed_player = Embed(title = "Welcome to the Game of Sueca!", description = "Here's your starting cards!", color=0x2e6cbd)
embed_player.add_field(name = "Use command !play <0 - 9> to play a card!", value = "You can use command !leave to leave the game anytime!")
embed_initial = Embed(title = "You are to make the first move!",description = "Go!",color = 0x2e6cbd)
embed_played = Embed(title = "Current State of The Game")
embed_green_round = Embed(title = "Epic Green Win!", description = "Green Takes The Round!",color =0x2e6cbd)
embed_blue_round = Embed(title = "Epic Blue Win!", description = "Blue Takes The Round!",color = 0x317adf)
embed_next_player = Embed(title = "It's your turn now. Please Play one of your cards!")
embed_fill_bots = Embed(title = "There are not enough humans!",description = "Populating the game with bots!",color=0x2e6cbd)
embed_no_humans = Embed(title = "The last human in the game has left!",description = "Aborting the game!",color =0xd23b20)


bot = commands.Bot(command_prefix='!')
deck = ["2O","3O","4O","5O","6O","7O","QO","JO","KO","AO",
        "2E","3E","4E","5E","6E","7E","QE","JE","KE","AE",
        "2C","3C","4C","5C","6C","7C","QC","JC","KC","AC",
        "2P","3P","4P","5P","6P","7P","QP","JP","KP","AP"]

cards_value = {"1": -1, "2":0, "3":0.1 , "4":0.2, "5":0.3, "6":0.4, "7":10, "Q":2,"J":3, "K":4, "A":11
    }
bot_names = ["Liam","Noah","William","James","Logan","Benjamin","Mason","Elijah","Oliver","Jacob","Lucas","Michael","Alexander","Ethan","Daniel","Matthew","Aiden","Henry","Joseph","Jackson"]
games = {} #dict matching players with games
game_ = [] #list for all the game objects

#perms for the sueca channels
perm1 = PermissionOverwrite()
perm1.read_messages = False #for everyone in the server
perm2 = PermissionOverwrite()
perm2.read_messages = True #for the user
perm3 = PermissionOverwrite() #for the bot, so he can eliminate the text channel
perm3.manage_channels = True
perm3.read_messages = True

class Game:
    def __init__(self,players,current_playing,trump,channel):
        self.current = current_playing
        self.last_winner = current_playing
        self.players = players
        self.trump = trump
        self.points_green = 0
        self.timeout = 30
        self.points_blue = 0
        self.current_board = []
        self.channel = channel
    def update_current(self):
        self.current = (self.current + 1) % 4
    def reset_timeout(self):
        self.timeout = 30
    def reduce_time(self):
        self.timeout = self.timeout - 5
    def update_current_board(self,play):
        self.current_board.append(play)
    def set_current(self,new_current):
        self.current = new_current
        self.last_winner = new_current
        self.current_board = []
        for player in self.players:
            player.make_play("")
    def update_points(self,team):
        total_points = 0
        for card in self.current_board:
            total_points += round(cards_value[card[0]])
        if team == "green":
            self.points_green += total_points
        else:
            self.points_blue += total_points

class Player:
    def __init__(self,team,cards,user,isBot):
        self.team = team
        self.cards = cards
        self.user = user
        self.isBot = isBot
        self.play = ""
        if self.isBot:
            self.avatar = Image.open("PNG/bot.jpg")
        else:
            with requests.get(player.user.avatar_url) as r:
                img_data = r.content
            with open('image_name.jpg', 'wb') as handler:
                handler.write(img_data)
            self.avatar = Image.open('image_name.jpg')
    def add_channel(self,channel):
        self.channel = channel
    def make_play(self,play):
        self.play = play

async def continue_play(player_game):
    while True:
        if player_game.current == player_game.last_winner: #the round has ended
            winner = check_round_winner(player_game.current_board,player_game.trump)
            winner = (player_game.last_winner + winner) % 4
            if player_game.players[winner].team == "green":
                player_game.update_points("green")
                await player_game.channel.send(embed=embed_green_round)
            else:
                player_game.update_points("blue")
                await player_game.channel.send(embed=embed_blue_round)
            player_game.set_current(winner)
            if check_if_game_over(player_game.players[player_game.current]):
                for player in player_game.players:
                    if not player.isBot:
                        del games[player.user]
                        await player.channel.delete()
                    del player
                       
                embed_draw = Embed(title = "It's a draw! What a shame!")
                if player_game.points_green > player_game.points_blue:
                    embed_win_green = Embed(title = "It's an epic win for green team! Congrats guys!",value = "Green team has come out on top with {} points, while blue team scored only {} points!".format(player_game.points_green,player_game.points_blue))
                    await player_game.channel.send(embed = embed_win_green)
                elif player_game.points_blue > player_game.points_green:
                    embed_blue_win = Embed(title = "It's an epic win for blue team! Yay! So much win!",value = "Blue team has come out on top with {} points, while green team scored only {} points!".format(player_game.points_blue,player_game.points_green))
                    await player_game.channel.send(embed = embed_blue_win)
                else:
                    embed_draw = Embed(title = "It's a draw! What a shame!",value = "Both team score a total of {} points!".format(player_game.points_blue))
                    await player_game.channel.send(embed = embed_draw)
                del game_[game_.index(player_game)]
                del player_game
                return
        if player_game.players[player_game.current].isBot == False:
            await player_game.players[player_game.current].channel.send(embed = embed_next_player)
            image_path = create_hand_image(player_game.players[player_game.current].cards)
            await player_game.players[player_game.current].channel.send(file = File(image_path))
            player_game.reset_timeout()
            os.remove(image_path)
            return
        while player_game.players[player_game.current].isBot and len(player_game.current_board) != 4:
            play = bot_plays(player_game.players[player_game.current].cards,player_game.current_board,player_game.trump)
            player_game.players[player_game.current].make_play(play)
            index = player_game.players[player_game.current].cards.index(play)
            del player_game.players[player_game.current].cards[index]
            player_game.update_current_board(play)
            player_game.update_current()
            await player_game.channel.send(embed = embed_played)
            path = create_board_image(player_game)
            await player_game.channel.send(file = File(path))
            os.remove(path)
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='sueca')
async def sueca(ctx):
    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")
    await message.add_reaction("☑️")
    await asyncio.sleep(20)
    message = await message.channel.fetch_message(message.id)
    n_reacts = 0
    for reaction in message.reactions:
        n_reacts += reaction.count
    random.shuffle(deck)
    players = []
    i = 0
    team_map = {"✅":"green","☑️":"blue" }
    for reaction in message.reactions:
        team = team_map[reaction.emoji]
        if reaction.count > 3:
            await ctx.send(embed = embed_shit)
            return
        reactions = await reaction.users().flatten()
        reactions.pop(0)
        for user in reactions:
            for player in players:
                if player.user == user:
                    await ctx.send("One of you selected more than one team! Retard!")
                    return
            players.append(Player(team,deck[0+10*i:10+10*i],user,False))
            i = i + 1
           
    if len(players) == 0:
        await ctx.send(embed = embed_invalid)
        return
    #if there isnt enough people, fill the lobby with bots
    if len(players) < 4:
        await ctx.send(embed = embed_fill_bots)
        n_greens_bots = 2
        n_blues_bots = 2
        for player in players:
            if player.team == "blue":
                n_blues_bots -= 1
            else:
                n_greens_bots -= 1
        for a in range(0,n_blues_bots):
            bot_index = random.randint(0,len(bot_names)-1)
            bot_name = bot_names[bot_index]
            del bot_names[bot_index]
            players.append(Player("blue",deck[0+10*i:10+10*i],bot_name,True))
            print("Created a blue bot!")
            i = i + 1
        for a in range(0,n_greens_bots):
            bot_index = random.randint(0,len(bot_names)-1)
            bot_name = bot_names[bot_index]
            del bot_names[bot_index]
            players.append(Player("green",deck[0+10*i:10+10*i],bot_name,True))
            print("Created a green bot!")
            i = i + 1
    players.sort(key = lambda player:player.team,reverse = True)
    players[1],players[2] = players[2],players[1]
    trump = random.choice(["O","P","E","C"])
    map = {"O": "PNG/ouros.png", "P":"PNG/paus.jpg", "E":"PNG/espadas.jpg","C":"PNG/copas.png"}
    embed_trump = Embed(title = "The trump for this game will be...",description = "{}".format(trump),color = 0x2e6cbd)
    await ctx.send(embed = embed_trump)
    await ctx.send(file = File(map[trump]))
    new_game = Game(players,0,trump,ctx.channel)
    game_.append(new_game)
    guild = ctx.guild
    #get the category
    id_category = ctx.message.channel.category_id
    real_category = None
    for category in guild.categories:
        if category.id == id_category:
            real_category = category
    for player in players:
        if player.isBot:
            continue
        games[player.user] = new_game
        channel = await guild.create_text_channel("{}'s sueca playroom".format(player.user.name),category=real_category)
        await channel.set_permissions(guild.default_role, overwrite=perm1)
        await channel.set_permissions(player.user, overwrite=perm2)
        await channel.set_permissions(guild.me, overwrite=perm3)
        await channel.set_permissions(guild.owner, overwrite=perm1)
        print("Created the new channel!")
        player.add_channel(channel)
        await channel.send("{}".format(player.user.mention))
        await channel.send(embed = embed_player)
        image_path = create_hand_image(player.cards)
        await channel.send(file = File(image_path))
        os.remove(image_path)
    
    if new_game.players[new_game.current].isBot == False: 
        await new_game.players[new_game.current].channel.send(embed = embed_initial)
        return
 
    while new_game.players[new_game.current].isBot:
        play = bot_plays(new_game.players[new_game.current].cards,new_game.current_board,new_game.trump)
        new_game.players[new_game.current].make_play(play)
        index = new_game.players[new_game.current].cards.index(play)
        del new_game.players[new_game.current].cards[index]
        new_game.update_current_board(play)
        new_game.update_current()
        await new_game.channel.send(embed = embed_played)
        path = create_board_image(new_game)
        await new_game.channel.send(file = File(path))
    await new_game.players[new_game.current].channel.send(embed = embed_next_player)
   
@bot.command(name = "leave")
async def leave(ctx):
    bot_name = random.choice(bot_names)
    user = ctx.message.author
    try:
        player_game = games[user]
    except:
        await ctx.send("You are not in any game at the moment!")
        return
    for i in range(0,len(player_game.players)):
        if player_game.players[i].user == user:#replace the guy that's leaving with a bot
            team = player_game.players[i].team
            play = player_game.players[i].play
            cards = player_game.players[i].cards
            await player_game.players[i].channel.delete()
            del player_game.players[i]
            new_bot = Player(team,cards,bot_name,True)
            new_bot.make_play(play)
            player_game.players.insert(i,new_bot)
            break
    for player in player_game.players:
        if player.isBot == False:
            return
    await player_game.channel.send(embed = embed_no_humans)
    del games[user]
    del game_[game_.index(player_game)]

@bot.command(name = "play")
async def play(ctx,arg):
    user = ctx.message.author
    try:
        player_game = games[user]
    except:
        return
    if player_game.players[player_game.current].user == user and ctx.channel == player_game.players[player_game.current].channel:
        try:
            arg = int(arg)
        except:
            await ctx.send("Not a valid argument. Please try again!")
            return
        if arg not in range(0,len(player_game.players[player_game.current].cards)):
            await ctx.send("Not a valid argument. Please try again!")
            return

        play = player_game.players[player_game.current].cards[arg]
        if player_game.current_board != [] and is_illegal(play,player_game.current_board,player_game.players[player_game.current].cards):
            await ctx.send("That's Not a Valid Play right now! Renúncia dass")
            return
        player_game.players[player_game.current].make_play(play)
        del player_game.players[player_game.current].cards[arg]
        player_game.update_current_board(play)
        player_game.update_current()
        await player_game.channel.send(embed = embed_played)
        #create the image that represents the current board
        path = create_board_image(player_game)
        await player_game.channel.send(file = File(path))
        os.remove(path)
        await continue_play(player_game)
        return
    else:
        return

def check_if_game_over(player_curr):
    if len(player_curr.cards) == 0:
        return True
    else:
        return False
def check_round_winner(current_board,trump):
    #check if a trump card was played
    max_trump = "1"
    for card in current_board:
        if card[1] == trump and cards_value[card[0]] > cards_value[max_trump[0]]:
            max_trump = card
    if max_trump == "1":
        naipe = current_board[0][1]
        for card in current_board:
            if card[1] == naipe and cards_value[card[0]] > cards_value[max_trump[0]]:
                max_trump = card
    print("Round Winner- ",max_trump)
    return current_board.index(max_trump)

def create_hand_image(cards):
    translation = {"P":"C", "C":"H", "E":"S", "O":"D"}
    fnt = ImageFont.truetype('arial.ttf', 170)
    img_temp = Image.open("./PNG/{}.png".format(cards[0][0] + translation[cards[0][1]]))
    dst = Image.new('RGB', (img_temp.width * len(cards), img_temp.height))
    acc_width = 0
    i = 0
    for card in cards:
        img_temp = Image.open("./PNG/{}.png".format(card[0] + translation[card[1]]))
        dst.paste(img_temp,(acc_width,0))
        d = ImageDraw.Draw(dst)
        d.text((acc_width + img_temp.width - 110 ,10),str(i),font = fnt,fill = (0,95,255))
        acc_width += img_temp.width
        i += 1

    path = "PNG/{}.png".format(random.randint(1,10000))
    print("Should have created an image!")
    dst.save(path)
    return path

def create_board_image(game):
    images = []
    names = []
    translation = {"P":"C", "C":"H", "E":"S", "O":"D"}
    card_width = 220
    avatar_width = 300
    avatar_height = 272
    card_height = 320
    fnt = ImageFont.truetype('arial.ttf', 60)
    for player in game.players:
        if player.play != "":
            card = Image.open("PNG/{}.png".format(player.play[0] + translation[player.play[1]])).resize((card_width,card_height))
        else:
            card = Image.open("PNG/default.jpg").resize((card_width,card_height))
        if player.isBot:
            names.append("Bot {}".format(player.user))
        else:
            names.append(player.user.name)
        images.append([player.avatar.resize((avatar_width,avatar_height)),card])

    dst = Image.new('RGB', (1920,1080),(190,190,190))
    rect_green = Image.new("RGB", (20,avatar_height), (0,153,0))
    rect_blue = Image.new("RGB", (20,avatar_height), (51,51,255))
    dst.paste(images[0][0],(30,dst.height//2 - avatar_height//2))
    dst.paste(rect_green,(10,dst.height//2 - avatar_height//2))
    dst.paste(images[0][1],(50 + avatar_width, dst.height//2 - avatar_height//2))
    dst.paste(images[1][0],(dst.width//2 + avatar_width//2,70))
    dst.paste(rect_blue,(dst.width//2 + avatar_width//2 - 20,70))
    dst.paste(images[1][1],(dst.width//2 - card_width//2, 70))
    dst.paste(images[2][0],(dst.width - avatar_width - 30,dst.height// 2 - avatar_height //2))
    dst.paste(rect_green,(dst.width - avatar_width - 50,dst.height// 2 - avatar_height //2))
    dst.paste(images[2][1],(dst.width - avatar_width - card_width - 70, dst.height// 2 - avatar_height //2))
    dst.paste(images[3][0],(dst.width//2 - avatar_width - 150,dst.height - avatar_height - 10))
    dst.paste(rect_blue,(dst.width//2 - avatar_width - 170,dst.height - avatar_height - 10))
    dst.paste(images[3][1],(dst.width//2 - card_width//2, dst.height - card_height - 10))
    d = ImageDraw.Draw(dst)
    d.text((10,20),"Green Team Points:{}".format(game.points_green),fill = (0,0,0),font = fnt)
    d.text((dst.width - 550,dst.height - 60),"Blue Team Points:{}".format(game.points_blue),fill = (0,0,0),font = fnt)
    d.text((10,dst.height // 2 - avatar_height//2 - 70),names[0],font = fnt,fill = (0,0,0))
    d.text((dst.width//2 + avatar_width//2 + 10,10), names[1],font = fnt,fill = (0,0,0))
    d.text((dst.width - avatar_width - 40,dst.height//2 - avatar_height//2 - 75), names[2],font = fnt,fill = (0,0,0))
    d.text((dst.width//2 - avatar_width - 150,dst.height - avatar_height - 80), names[3],font = fnt,fill = (0,0,0))
    path = "PNG/{}.png".format(random.randint(1,10000))
    print("Should have created an image!")
    dst.save(path)
    return path

def is_illegal(play,board,cards):
    can_match = False
    for card in cards:
        if card[1] == board[0][1]:
            can_match = True
            break
    print(can_match)
    if can_match and play[1] == board[0][1]:
        return False
    if not can_match:
        return False
    else:
        return True
def bot_plays(cards,current_board,trump):
    if current_board == []:
        possible_plays = [card for card in cards if card[1] != trump]
        if possible_plays == []:
            possible_plays = cards
        max_value, min_value = get_min_and_max_values(possible_plays)
        return max_value

    else:
        possible_plays = [card for card in cards if card[1] == current_board[0][1]]
        if possible_plays == []:
            possible_plays = cards
        print(possible_plays)
        max_value, min_value = get_min_and_max_values(possible_plays)
        trump_card = ""
        for card in possible_plays:
            if card[1] == trump:
                trump_card = card
        print(max_value,min_value,trump_card)
        if len(current_board) == 2:
            if card_wins(current_board[0],current_board[1],trump): #checks if the first card wins over the second
                return max_value
            elif (trump_card != "") and (cards_value[current_board[0][0]] > 1 or cards_value[current_board[1][0]] > 1):
                return trump_card
            else:                
                return min_value
        else:
            winning_cards = []
            if len(current_board) == 1:
                for card in possible_plays:
                    if card_wins(card,current_board[0],trump):
                        winning_cards.append(card)
            else:
                if card_wins(current_board[1],current_board[0],trump) and card_wins(current_board[1],current_board[2],trump):
                    return max_value
                for card in possible_plays:
                    if card_wins(card,current_board[0],trump) and card_wins(card,current_board[2],trump):
                        winning_cards.append(card)
            if winning_cards == []:
                return min_value
            else:
                for card in winning_cards:
                    if card[1] != trump: #if theres a winning_card that isnt a trump the bot will play it, otherwise play a trump
                        return card
                return random.choice(winning_cards)


def card_wins(card1,card2,trump):
    if card1[1] == trump and card2[1] != trump:
        return True
    if card2[1] == trump and card1[1] != trump:
        return False
    if cards_value[card1[0]] > cards_value[card2[0]]:
        return True
    else:
        return False

def get_min_and_max_values(possible_plays):
    max_value = possible_plays[0]
    min_possible_value = possible_plays[0]
    for card in possible_plays:
        if cards_value[card[0]] > cards_value[max_value[0]]:
            max_value = card
        if cards_value[card[0]] < cards_value[min_possible_value[0]]:
            min_possible_value = card
    return [max_value,min_possible_value]

bot.run(TOKEN)