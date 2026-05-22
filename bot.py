

from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv
import random
import tempfile
from dataclasses import dataclass, field
from contextlib import suppress
from pathlib import Path
from typing import Final


import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")

BOT_DELAY = 0.3
ROUND_DELAY = 1.5
ASSET_DIR: Final = Path("PNG")
CARD_SUIT_TO_ASSET: Final = {"P": "C", "C": "H", "E": "S", "O": "D"}
TRUMP_IMAGES: Final = {
    "O": ASSET_DIR / "ouros.png",
    "P": ASSET_DIR / "paus.jpg",
    "E": ASSET_DIR / "espadas.jpg",
    "C": ASSET_DIR / "copas.png",
}

DECK: Final = [
    f"{rank}{suit}"
    for suit in ["O", "E", "C", "P"]
    for rank in ["2", "3", "4", "5", "6", "7", "Q", "J", "K", "A"]
]

CARD_POINTS: Final = {
    "2": 0,
    "3": 0,
    "4": 0,
    "5": 0,
    "6": 0,
    "7": 10,
    "Q": 2,
    "J": 3,
    "K": 4,
    "A": 11,
}

CARD_STRENGTH: Final = {
    "2": 1,
    "3": 2,
    "4": 3,
    "5": 4,
    "6": 5,
    "Q": 6,
    "J": 7,
    "K": 8,
    "7": 9,
    "A": 10,
}

BOT_NAMES = [
    "Liam", "Noah", "William", "James", "Logan", "Benjamin", "Mason",
    "Elijah", "Oliver", "Jacob", "Lucas", "Michael", "Alexander", "Ethan",
    "Daniel", "Matthew", "Aiden", "Henry", "Joseph", "Jackson",
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

games_by_user_id: dict[int, "Game"] = {}
active_games: list["Game"] = []


@dataclass
class Player:
    team: str
    cards: list[str]
    user: discord.User | discord.Member | str
    is_bot: bool = False
    play: str = ""
    channel: discord.TextChannel | None = None
    avatar: Image.Image | None = None

    @property
    def display_name(self) -> str:
        return f"Bot {self.user}" if self.is_bot else self.user.display_name

    async def load_avatar(self) -> None:
        if self.is_bot:
            self.avatar = Image.open(ASSET_DIR / "bot.jpg").convert("RGB")
            return

        avatar_bytes = await self.user.display_avatar.read()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(avatar_bytes)
            tmp_path = Path(tmp.name)

        try:
            self.avatar = Image.open(tmp_path).convert("RGB")
        finally:
            tmp_path.unlink(missing_ok=True)


@dataclass
class Game:
    players: list[Player]
    current: int
    trump: str
    channel: discord.TextChannel
    last_winner: int = field(init=False)
    points_green: int = 0
    points_blue: int = 0
    current_board: list[str] = field(default_factory=list)
    round_image_messages: list[discord.Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.last_winner = self.current

    @property
    def current_player(self) -> Player:
        return self.players[self.current]

    def advance_turn(self) -> None:
        self.current = (self.current + 1) % 4

    def add_play(self, card: str) -> None:
        self.current_board.append(card)

    def start_new_round(self, winner_index: int) -> None:
        self.current = winner_index
        self.last_winner = winner_index
        self.current_board.clear()
        for player in self.players:
            player.play = ""

    def award_trick_points(self, team: str) -> None:
        total = sum(CARD_POINTS[card[0]] for card in self.current_board)
        if team == "green":
            self.points_green += total
        else:
            self.points_blue += total


def make_embed(title: str, description: str = "", color: int = 0x2E6CBD) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


async def send_image(channel: discord.abc.Messageable, image_path: Path) -> discord.Message:
    try:
        return await channel.send(file=discord.File(image_path))
    finally:
        image_path.unlink(missing_ok=True)


@bot.event
async def on_ready() -> None:
    assert bot.user is not None
    print(f"{bot.user} connected to Discord.")


@bot.command(name="sueca")
async def sueca(ctx: commands.Context) -> None:
    lobby_embed = make_embed("Sueca", "Bem-vindos ao jogo da Sueca!")
    lobby_embed.add_field(
        name="React with your team to enter",
        value="✅ green team | ☑️ blue team. Waiting 20 seconds.",
        inline=False,
    )
    lobby_embed.set_image(url="https://i1.wp.com/etili.co/wp-content/uploads/2018/09/sueca.jpg?fit=900%2C665")

    message = await ctx.send(embed=lobby_embed)
    for emoji in ["✅", "☑️"]:
        await message.add_reaction(emoji)

    await asyncio.sleep(20)
    message = await message.channel.fetch_message(message.id)

    shuffled_deck = DECK.copy()
    random.shuffle(shuffled_deck)

    players: list[Player] = []
    team_by_emoji = {"✅": "green", "☑️": "blue"}

    for reaction in message.reactions:
        team = team_by_emoji.get(str(reaction.emoji))
        if team is None:
            continue

        users = [user async for user in reaction.users() if not user.bot]
        if len(users) > 2:
            await ctx.send(embed=make_embed("Too many players on one team", "Aborting the game.", 0xD23B20))
            return

        for user in users:
            if any(not p.is_bot and p.user.id == user.id for p in players):
                await ctx.send("One player selected more than one team. Aborting.")
                return
            hand = shuffled_deck[len(players) * 10 : len(players) * 10 + 10]
            player = Player(team=team, cards=hand, user=user)
            await player.load_avatar()
            players.append(player)

    if not players:
        await ctx.send(embed=make_embed("No players", "No one joined the game.", 0xD23B20))
        return

    await fill_with_bots(players, shuffled_deck, ctx)

    players.sort(key=lambda player: player.team, reverse=True)
    players[1], players[2] = players[2], players[1]

    trump = random.choice(["O", "P", "E", "C"])
    await ctx.send(embed=make_embed("Trump suit", trump))
    if TRUMP_IMAGES[trump].exists():
        await ctx.send(file=discord.File(TRUMP_IMAGES[trump]))

    game = Game(players=players, current=0, trump=trump, channel=ctx.channel)
    active_games.append(game)

    await create_private_rooms(ctx, game)
    await announce_trump_to_players(game)
    await continue_play(game)


async def fill_with_bots(players: list[Player], shuffled_deck: list[str], ctx: commands.Context) -> None:
    if len(players) >= 4:
        return

    await ctx.send(embed=make_embed("Not enough humans", "Filling the game with bots."))
    needed = {"green": 2, "blue": 2}
    for player in players:
        needed[player.team] -= 1

    used_bot_names = set()
    for team, count in needed.items():
        for _ in range(count):
            available_names = [name for name in BOT_NAMES if name not in used_bot_names]
            bot_name = random.choice(available_names or BOT_NAMES)
            used_bot_names.add(bot_name)
            hand_start = len(players) * 10
            bot_player = Player(team=team, cards=shuffled_deck[hand_start : hand_start + 10], user=bot_name, is_bot=True)
            await bot_player.load_avatar()
            players.append(bot_player)


async def create_private_rooms(ctx: commands.Context, game: Game) -> None:
    assert ctx.guild is not None
    category = ctx.channel.category

    hidden = discord.PermissionOverwrite(read_messages=False)
    visible = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    bot_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)

    for player in game.players:
        if player.is_bot:
            continue

        games_by_user_id[player.user.id] = game
        channel = await ctx.guild.create_text_channel(
            name=f"{player.user.display_name}-sueca-playroom",
            category=category,
        )
        await channel.set_permissions(ctx.guild.default_role, overwrite=hidden)
        await channel.set_permissions(player.user, overwrite=visible)
        if ctx.guild.me:
            await channel.set_permissions(ctx.guild.me, overwrite=bot_perms)

        player.channel = channel
        await channel.send(player.user.mention)
        await channel.send(embed=make_embed("Welcome to Sueca", "Use `!play <card number>` or `!p <card number>`. Use `!leave` to leave."))
        await send_image(channel, create_hand_image(player.cards))


async def announce_trump_to_players(game: Game) -> None:
    for player in game.players:
        if player.is_bot or player.channel is None:
            continue
        await player.channel.send(embed=make_embed("Trump suit", game.trump))
        if TRUMP_IMAGES[game.trump].exists():
            await player.channel.send(file=discord.File(TRUMP_IMAGES[game.trump]))


@bot.command(name="leave")
async def leave(ctx: commands.Context) -> None:
    user = ctx.author
    game = games_by_user_id.get(user.id)
    if game is None:
        await ctx.send("You are not in a game right now.")
        return

    bot_name = random.choice(BOT_NAMES)
    for index, player in enumerate(game.players):
        if not player.is_bot and player.user.id == user.id:
            replacement = Player(player.team, player.cards, bot_name, is_bot=True, play=player.play)
            await replacement.load_avatar()
            if player.channel:
                await player.channel.delete()
            game.players[index] = replacement
            games_by_user_id.pop(user.id, None)
            break

    if all(player.is_bot for player in game.players):
        await game.channel.send(embed=make_embed("No humans left", "Aborting the game.", 0xD23B20))
        finish_game(game)


@bot.command(name="play", aliases=["p","P","Play","PLAY"])
async def play(ctx: commands.Context, card_index: int | None = None) -> None:
    game = games_by_user_id.get(ctx.author.id)
    if game is None:
        return

    current_player = game.current_player
    if current_player.is_bot or current_player.user.id != ctx.author.id or ctx.channel != current_player.channel:
        return

    if card_index is None or card_index not in range(len(current_player.cards)):
        await ctx.send("Not a valid card number. Please try again.")
        return

    selected_card = current_player.cards[card_index]
    if game.current_board and is_illegal(selected_card, game.current_board, current_player.cards):
        await ctx.send("Invalid play: you must follow suit if you can.")
        return

    await play_card(game, current_player, card_index)
    await continue_play(game)


async def continue_play(game: Game) -> None:
    while True:
        if len(game.current_board) == 4:
            relative_winner = check_round_winner(game.current_board, game.trump)
            winner_index = (game.last_winner + relative_winner) % 4
            winner = game.players[winner_index]
            game.award_trick_points(winner.team)
            await send_to_private_channels(game, embed=make_embed(f"{winner.team.title()} wins the round!"))
            await asyncio.sleep(ROUND_DELAY)
            await delete_round_images(game)
            game.start_new_round(winner_index)

            if not game.current_player.cards:
                await end_game(game)
                return

        current_player = game.current_player

        # Quality of life: if a human has only one card, play it automatically.
        if not current_player.is_bot and len(current_player.cards) == 1:
            await play_card(game, current_player, 0)
            continue

        if not current_player.is_bot:
            if current_player.channel:
                await current_player.channel.send(current_player.user.mention)
                await current_player.channel.send(embed=make_embed("It's your turn", "Please play one of your cards."))
                await send_image(current_player.channel, create_hand_image(current_player.cards))
            return

        card = bot_plays(current_player.cards, game.current_board, game.trump)
        card_index = current_player.cards.index(card)
        await play_card(game, current_player, card_index)


async def play_card(game: Game, player: Player, card_index: int) -> None:
    card = player.cards.pop(card_index)
    player.play = card
    game.add_play(card)
    game.advance_turn()
    await send_board_state_to_players(game)


async def send_to_private_channels(game: Game, *, content: str | None = None, embed: discord.Embed | None = None) -> None:
    for player in game.players:
        if player.is_bot or player.channel is None:
            continue
        await player.channel.send(content=content, embed=embed)


async def send_board_state_to_players(game: Game) -> None:
    for player in game.players:
        if player.is_bot or player.channel is None:
            continue
        message = await send_image(player.channel, create_board_image(game))
        await asyncio.sleep(BOT_DELAY)
        game.round_image_messages.append(message)


async def delete_round_images(game: Game) -> None:
    for message in game.round_image_messages:
        with suppress(discord.NotFound, discord.Forbidden, discord.HTTPException):
            await message.delete()

    game.round_image_messages.clear()


async def end_game(game: Game) -> None:
    if game.points_green > game.points_blue:
        result = f"Green wins with {game.points_green} points. Blue scored {game.points_blue}."
    elif game.points_blue > game.points_green:
        result = f"Blue wins with {game.points_blue} points. Green scored {game.points_green}."
    else:
        result = f"It's a draw. Both teams scored {game.points_blue} points."

    await delete_round_images(game)
    await send_to_private_channels(game, embed=make_embed("Game over", result))
    await game.channel.send(embed=make_embed("Game over", result))

    for player in game.players:
        if not player.is_bot:
            games_by_user_id.pop(player.user.id, None)
            if player.channel:
                await player.channel.delete()

    finish_game(game)


def finish_game(game: Game) -> None:
    if game in active_games:
        active_games.remove(game)


def check_round_winner(current_board: list[str], trump: str) -> int:
    winning_card = current_board[0]
    leading_suit = current_board[0][1]

    for card in current_board[1:]:
        if card_wins(card, winning_card, trump, leading_suit):
            winning_card = card

    return current_board.index(winning_card)


def create_hand_image(cards: list[str]) -> Path:
    if not cards:
        raise ValueError("Cannot create a hand image with no cards.")

    font = load_font(170)
    card_images = [load_card_image(card) for card in cards]
    width = sum(image.width for image in card_images)
    height = max(image.height for image in card_images)
    output = Image.new("RGB", (width, height), "white")

    x = 0
    draw = ImageDraw.Draw(output)
    for index, image in enumerate(card_images):
        output.paste(image, (x, 0))
        draw.text((x + image.width - 110, 10), str(index), font=font, fill=(0, 95, 255))
        x += image.width

    return save_temp_image(output)


def create_board_image(game: Game) -> Path:
    font = load_font(60)
    card_size = (220, 320)
    avatar_size = (300, 272)

    output = Image.new("RGB", (1920, 1080), (190, 190, 190))
    draw = ImageDraw.Draw(output)

    positions = [
        ((30, 404), (350, 404), (10, 404)),
        ((1110, 70), (850, 70), (1090, 70)),
        ((1590, 404), (1300, 404), (1570, 404)),
        ((510, 798), (850, 750), (490, 798)),
    ]

    for index, player in enumerate(game.players):
        avatar = (player.avatar or Image.open(ASSET_DIR / "bot.jpg")).resize(avatar_size)
        card = load_card_image(player.play).resize(card_size) if player.play else Image.open(ASSET_DIR / "default.jpg").resize(card_size)
        avatar_xy, card_xy, team_bar_xy = positions[index]
        team_color = (0, 153, 0) if player.team == "green" else (51, 51, 255)
        output.paste(Image.new("RGB", (20, avatar_size[1]), team_color), team_bar_xy)
        output.paste(avatar, avatar_xy)
        output.paste(card, card_xy)
        draw.text((avatar_xy[0], max(0, avatar_xy[1] - 70)), player.display_name, font=font, fill=(0, 0, 0))

    draw.text((10, 20), f"Green Team Points: {game.points_green}", fill=(0, 0, 0), font=font)
    draw.text((1320, 1010), f"Blue Team Points: {game.points_blue}", fill=(0, 0, 0), font=font)

    return save_temp_image(output)


def load_card_image(card: str) -> Image.Image:
    asset_name = f"{card[0]}{CARD_SUIT_TO_ASSET[card[1]]}.png"
    return Image.open(ASSET_DIR / asset_name).convert("RGB")


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_name in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def save_temp_image(image: Image.Image) -> Path:
    temp = tempfile.NamedTemporaryFile(prefix="sueca_", suffix=".png", delete=False)
    temp.close()
    path = Path(temp.name)
    image.save(path)
    return path


def is_illegal(play: str, board: list[str], cards: list[str]) -> bool:
    leading_suit = board[0][1]
    can_follow_suit = any(card[1] == leading_suit for card in cards)
    return can_follow_suit and play[1] != leading_suit


def bot_plays(cards: list[str], current_board: list[str], trump: str) -> str:
    legal_cards = cards
    if current_board:
        same_suit = [card for card in cards if card[1] == current_board[0][1]]
        if same_suit:
            legal_cards = same_suit
    else:
        non_trumps = [card for card in cards if card[1] != trump]
        if non_trumps:
            legal_cards = non_trumps

    high, low = get_min_and_max_values(legal_cards)

    if not current_board:
        return high

    winning_cards = [card for card in legal_cards if card_wins(card, current_board[0], trump, current_board[0][1])]
    return min(winning_cards, key=lambda card: CARD_STRENGTH[card[0]]) if winning_cards else low


def card_wins(card1: str, card2: str, trump: str, leading_suit: str | None = None) -> bool:
    if card1[1] == trump and card2[1] != trump:
        return True
    if card2[1] == trump and card1[1] != trump:
        return False

    if leading_suit is not None:
        if card1[1] == leading_suit and card2[1] != leading_suit:
            return True
        if card2[1] == leading_suit and card1[1] != leading_suit:
            return False

    if card1[1] != card2[1]:
        return False

    return CARD_STRENGTH[card1[0]] > CARD_STRENGTH[card2[0]]


def get_min_and_max_values(possible_plays: list[str]) -> tuple[str, str]:
    high = max(possible_plays, key=lambda card: CARD_STRENGTH[card[0]])
    low = min(possible_plays, key=lambda card: CARD_STRENGTH[card[0]])
    return high, low


bot.run(TOKEN)
