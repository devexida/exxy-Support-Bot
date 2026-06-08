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

# Banner image URL (update this with your GitHub raw link)
BANNER_URL = "https://github.com/devexida/exxy-Support-Bot/main/Banner.png" # ← CHANGE THIS


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


# -------------------------
# PANEL BUTTON VIEW
# -------------------------
class ChannelButton(discord.ui.View):
    def __init__(self, button_text, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label=button_text,
                url=channel.jump_url
            )
        )


# -------------------------
# /panel
# -------------------------
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
            "You do not have permission.",
            ephemeral=True
        )

    embed = discord.Embed(
        description=text,
        color=discord.Color.blurple()
    )
    embed.set_image(url=BANNER_URL)  # Banner at top

    if button and channel and button_text:
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=button_text,
                url=channel.jump_url
            )
        )
        await interaction.channel.send(embed=embed, view=view)
    else:
        await interaction.channel.send(embed=embed)

    await interaction.response.send_message(
        "Panel sent.",
        ephemeral=True
    )


# -------------------------
# /deal-log
# -------------------------
@bot.tree.command(name="deal-log")
async def deal_log(
    interaction: discord.Interaction,
    seller_name: str,
    buyer_name: str,
    product: str,
    price: str,
    payment_method: str,
    text: Optional[str] = None
):

    if not owner_check(interaction):
        return await interaction.response.send_message(
            "You do not have permission.",
            ephemeral=True
        )

    channel = bot.get_channel(DEAL_LOGS_CHANNEL_ID)

    if channel is None:
        return await interaction.response.send_message(
            "Deal log channel not found.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="An order has been finished ✅",
        color=discord.Color.green()
    )
    embed.set_image(url=BANNER_URL)  # Banner

    embed.add_field(name="Seller", value=seller_name, inline=False)
    embed.add_field(name="Buyer", value=buyer_name, inline=False)
    embed.add_field(name="Product", value=product, inline=False)
    embed.add_field(name="Price", value=price, inline=False)
    embed.add_field(name="Payment Method", value=payment_method, inline=False)

    if text:
        embed.add_field(name="Additional Information", value=text, inline=False)

    await channel.send(embed=embed)

    await interaction.response.send_message(
        "Deal log posted.",
        ephemeral=True
    )


# -------------------------
# MODALS
# -------------------------
class DealModal(discord.ui.Modal, title="Deal Information"):

    product = discord.ui.TextInput(label="Product")
    price = discord.ui.TextInput(label="Price")
    partner = discord.ui.TextInput(label="Deal Partner")
    payment = discord.ui.TextInput(label="Payment Method")

    async def on_submit(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="Deal Request Submitted",
            color=discord.Color.green(),
            description=(
                "Thank you for your information.\n\n"
                "A staff member will be with you shortly."
            )
        )
        embed.set_image(url=BANNER_URL)

        embed.add_field(name="Product", value=self.product.value, inline=False)
        embed.add_field(name="Price", value=self.price.value, inline=False)
        embed.add_field(name="Deal Partner", value=self.partner.value, inline=False)
        embed.add_field(name="Payment Method", value=self.payment.value, inline=False)

        await interaction.response.send_message(embed=embed)


class GenericModal(discord.ui.Modal):

    def __init__(self, title_text, field_label, final_message):
        super().__init__(title=title_text)
        self.final_message = final_message

        self.input = discord.ui.TextInput(
            label=field_label,
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            description=f"{self.final_message}\n\n**User Input:**\n{self.input.value}",
            color=discord.Color.blurple()
        )
        embed.set_image(url=BANNER_URL)
        await interaction.response.send_message(embed=embed)


# -------------------------
# BUYER / SELLER VIEW
# -------------------------
class BuyerSellerView(discord.ui.View):

    @discord.ui.button(label="Seller", style=discord.ButtonStyle.green)
    async def seller(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(DealModal())

    @discord.ui.button(label="Buyer", style=discord.ButtonStyle.blurple)
    async def buyer(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(DealModal())


# -------------------------
# IMPROVED TICKET OPTIONS - Using Select Menu
# -------------------------
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Make a Deal", value="make_deal", emoji="🤝", description="Start a new deal"),
            discord.SelectOption(label="Cancel a Deal", value="cancel_deal", emoji="❌", description="Cancel an existing deal"),
            discord.SelectOption(label="Report a Scammer", value="report_scammer", emoji="🚨", description="Report fraud"),
            discord.SelectOption(label="Report a Problem", value="report_problem", emoji="⚠️", description="Technical issue"),
            discord.SelectOption(label="Make a Refund", value="refund", emoji="💰", description="Request refund"),
            discord.SelectOption(label="Partner With Us", value="partner", emoji="👥", description="Business partnership"),
            discord.SelectOption(label="Something Else", value="something_else", emoji="❓", description="Other inquiry"),
        ]
        super().__init__(placeholder="Select an option...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message("This ticket has already been handled.", ephemeral=True)

        value = self.values[0]

        # Lock the ticket
        locked_ticket_channels.add(interaction.channel.id)
        # Disable select
        self.disabled = True
        for item in self.view.children:
            item.disabled = True

        await interaction.response.edit_message(view=self.view)

        await asyncio.sleep(0.5)  # Small delay for smooth UX

        if value == "make_deal":
            embed = discord.Embed(
                title="Make a Deal",
                description="Are you a...",
                color=discord.Color.green()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed, view=BuyerSellerView())

        elif value == "cancel_deal":
            embed = discord.Embed(
                description="A staff member will help you shortly with your cancellation.",
                color=discord.Color.blurple()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed)

        elif value == "report_scammer":
            embed = discord.Embed(
                description="Please provide more info and screenshots.\nStaff will review shortly.",
                color=discord.Color.red()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed)

        elif value == "report_problem":
            embed = discord.Embed(
                description="Staff will assist you shortly with your issue.",
                color=discord.Color.blurple()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed)

        elif value == "refund":
            embed = discord.Embed(
                description="Provide all deal details for refund review.",
                color=discord.Color.blurple()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed)

        elif value == "partner":
            embed = discord.Embed(
                description="We will review your partnership request shortly.",
                color=discord.Color.green()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed)

        else:  # something_else
            embed = discord.Embed(
                description="Staff will be with you shortly.",
                color=discord.Color.blurple()
            )
            embed.set_image(url=BANNER_URL)
            await interaction.followup.send(embed=embed)


class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# -------------------------
# REGISTER VIEW
# -------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


# -------------------------
# TICKET SYSTEM
# -------------------------
@bot.event
async def on_guild_channel_create(channel):
    if isinstance(channel, discord.TextChannel) and channel.category and channel.category.id == TICKETS_CATEGORY_ID:
        await asyncio.sleep(3)  # Wait 3 seconds before showing options

        embed = discord.Embed(
            title="Welcome",
            description="Thanks for choosing **eXXy Services**.\n\nHow can we assist you today?",
            color=discord.Color.blurple()
        )
        embed.set_image(url=BANNER_URL)  # Banner at top

        await channel.send(embed=embed, view=TicketView())


# -------------------------
# START SERVICES
# -------------------------
web_thread = Thread(target=run_web, daemon=True)
web_thread.start()

bot.run(TOKEN)
