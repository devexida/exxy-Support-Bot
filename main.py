import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
from flask import Flask
from threading import Thread
from typing import Optional
import asyncio

load_dotenv()

# -------------------------
# FLASK KEEP ALIVE
# -------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is online!"

def run_web():
    app.run(host="0.0.0.0", port=10000)


# -------------------------
# ENV
# -------------------------
TOKEN = os.getenv("TOKEN")

OWNER_ROLE_ID = int(os.getenv("OWNER_ROLE_ID"))
DEAL_LOGS_CHANNEL_ID = int(os.getenv("DEAL_LOGS_CHANNEL_ID"))
TICKETS_CATEGORY_ID = int(os.getenv("TICKETS_CATEGORY_ID"))

# Banner image URL
BANNER_URL = "https://imgur.com/gallery/exxy-H03NJKC"

# Replace with your pfp.png hosted link (GitHub raw, imgur, discord CDN, etc.)
REVIEW_PFP_URL = "https://your-hosted-link-to-pfp.png"  # ← CHANGE THIS


# -------------------------
# BOT SETUP
# -------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

locked_ticket_channels = set()


# -------------------------
# OWNER CHECK
# -------------------------
def owner_check(interaction: discord.Interaction):
    return any(role.id == OWNER_ROLE_ID for role in interaction.user.roles)


# =========================
# REVIEW SYSTEM
# =========================
class ReviewButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Leave a Review", style=discord.ButtonStyle.blurple, emoji="⭐")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ReviewModal())


class ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent
        self.add_item(ReviewButton())


class ReviewModal(discord.ui.Modal, title="Leave a Review"):
    service = discord.ui.TextInput(
        label="Service / Product",
        placeholder="Youtube Service / Premium",
        required=True,
        style=discord.TextStyle.short
    )
    
    price = discord.ui.TextInput(
        label="Price",
        placeholder="$15",
        required=True,
        style=discord.TextStyle.short
    )
    
    rating = discord.ui.TextInput(
        label="Rating (1-5)",
        placeholder="5",
        required=True,
        max_length=1,
        style=discord.TextStyle.short
    )
    
    comment = discord.ui.TextInput(
        label="Comment",
        placeholder="Your honest feedback...",
        required=True,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Validate rating
        try:
            rating_num = int(self.rating.value)
            if not 1 <= rating_num <= 5:
                return await interaction.response.send_message(
                    "Rating must be between 1 and 5!", ephemeral=True
                )
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a valid number (1-5) for rating!", ephemeral=True
            )

        stars = "⭐" * rating_num

        embed = discord.Embed(
            title="New Review from a Buyer",
            color=discord.Color.blurple()
        )

        if REVIEW_PFP_URL:
            embed.set_thumbnail(url=REVIEW_PFP_URL)

        embed.add_field(
            name="Service Details",
            value=f"**{self.service.value}**",
            inline=False
        )
        embed.add_field(name="Price", value=self.price.value, inline=True)
        embed.add_field(
            name="Rating",
            value=f"{stars} **({rating_num}/5)**",
            inline=True
        )
        embed.add_field(
            name="Comment",
            value=self.comment.value or "No comment provided.",
            inline=False
        )

        embed.set_footer(
            text=f"Reviewed by {interaction.user} • {discord.utils.format_dt(discord.utils.utcnow())}"
        )

        # Post review with button
        view = ReviewView()
        await interaction.channel.send(embed=embed, view=view)

        await interaction.response.send_message("✅ Thank you! Your review has been posted.", ephemeral=True)


# -------------------------
# /vouch_start Command
# -------------------------
@bot.tree.command(name="vouch_start", description="Post the review button panel (Owner only)")
async def vouch_start(interaction: discord.Interaction):
    if not owner_check(interaction):
        return await interaction.response.send_message(
            "You do not have permission.", ephemeral=True
        )

    embed = discord.Embed(
        title="⭐ Leave a Review",
        description="Share your experience with our services!\nYour feedback is greatly appreciated.",
        color=discord.Color.blurple()
    )
    embed.set_image(url=BANNER_URL)

    view = ReviewView()

    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Review panel posted successfully!", ephemeral=True)


# ========================
# YOUR EXISTING CODE BELOW
# ========================

class ChannelButton(discord.ui.View):
    def __init__(self, button_text, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label=button_text,
                url=channel.jump_url
            )
        )


@bot.tree.command(name="panel", description="Create a panel")
@app_commands.describe(
    text="Panel Text",
    button="Enable button?",
    button_text="Button Text",
    channel="Channel Button Leads To"
)
async def panel(
    interaction: discord.Interaction,
    text: str,
    button: bool,
    button_text: Optional[str] = None,
    channel: Optional[discord.TextChannel] = None
):
    if not owner_check(interaction):
        return await interaction.response.send_message(
            "You do not have permission.", ephemeral=True
        )

    embed = discord.Embed(description=text, color=discord.Color.blurple())
    embed.set_image(url=BANNER_URL)

    if button and channel and button_text:
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=button_text, url=channel.jump_url))
        await interaction.channel.send(embed=embed, view=view)
    else:
        await interaction.channel.send(embed=embed)

    await interaction.response.send_message("Panel sent.", ephemeral=True)


# ... (All your other commands and events: deal-log, tickets, etc.) ...

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


# -------------------------
# START SERVICES
# -------------------------
web_thread = Thread(target=run_web, daemon=True)
web_thread.start()

bot.run(TOKEN)
