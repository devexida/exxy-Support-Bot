import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
from flask import Flask
from threading import Thread
from typing import Optional

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


# -------------------------
# BOT SETUP
# -------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# STATE (LOCK SYSTEM)
# -------------------------
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
                "A staff member will be with you shortly "
                "to support your deal as a middle man."
            )
        )

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
            description=(
                f"{self.final_message}\n\n"
                f"**User Input:**\n{self.input.value}"
            ),
            color=discord.Color.blurple()
        )

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
# TICKET VIEW
# -------------------------
class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    def lock_view(self, interaction: discord.Interaction):
        """Disable all buttons and lock channel"""
        self.disable_all_items()
        locked_ticket_channels.add(interaction.channel.id)
        return self

    @discord.ui.button(label="Make a Deal", style=discord.ButtonStyle.green)
    async def make_deal(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)

        embed = discord.Embed(
            title="Make a Deal",
            description="Are you a...",
            color=discord.Color.green()
        )

        await interaction.message.edit(view=self)

        await interaction.response.send_message(embed=embed, view=BuyerSellerView())

    @discord.ui.button(label="Cancel a Deal", style=discord.ButtonStyle.red)
    async def cancel_deal(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)
        await interaction.message.edit(view=self)

        await interaction.response.send_modal(
            GenericModal(
                "Cancel Deal",
                "Describe the deal you want to cancel",
                "A staff member will be with you shortly to assist you."
            )
        )

    @discord.ui.button(label="Report a Scammer", style=discord.ButtonStyle.red)
    async def report_scammer(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)
        await interaction.message.edit(view=self)

        await interaction.response.send_modal(
            GenericModal(
                "Report Scammer",
                "Username and User ID",
                "Please provide more information and screenshots. Staff will be with you shortly."
            )
        )

    @discord.ui.button(label="Report a Problem", style=discord.ButtonStyle.blurple)
    async def report_problem(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)
        await interaction.message.edit(view=self)

        await interaction.response.send_modal(
            GenericModal(
                "Problem Report",
                "Describe the problem",
                "Staff will be with you shortly to resolve the problem."
            )
        )

    @discord.ui.button(label="Make a Refund", style=discord.ButtonStyle.gray)
    async def refund(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)
        await interaction.message.edit(view=self)

        await interaction.response.send_modal(
            GenericModal(
                "Refund Request",
                "Deal Information",
                "Please provide deal information, payment methods, seller/buyer names and middle man names. Staff will be with you shortly."
            )
        )

    @discord.ui.button(label="Partner With Us", style=discord.ButtonStyle.green)
    async def partner(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)
        await interaction.message.edit(view=self)

        await interaction.response.send_modal(
            GenericModal(
                "Partnership Request",
                "Social Media Link",
                "A staff member will review it shortly and let you know if we are interested."
            )
        )

    @discord.ui.button(label="Something Else", style=discord.ButtonStyle.gray)
    async def something_else(self, interaction: discord.Interaction, button):

        if interaction.channel.id in locked_ticket_channels:
            return await interaction.response.send_message(
                "This ticket option is already locked.",
                ephemeral=True
            )

        self.lock_view(interaction)
        await interaction.message.edit(view=self)

        await interaction.response.send_modal(
            GenericModal(
                "Something Else",
                "Leave a message",
                "A staff member will be with you shortly."
            )
        )


# -------------------------
# TICKET SYSTEM
# -------------------------
@bot.event
async def on_guild_channel_create(channel):

    if isinstance(channel, discord.TextChannel):

        if channel.category and channel.category.id == TICKETS_CATEGORY_ID:

            embed = discord.Embed(
                title="Welcome",
                description=(
                    "Thanks for choosing **eXXy Services**.\n\n"
                    "How can we assist you today?"
                ),
                color=discord.Color.blurple()
            )

            await channel.send(embed=embed, view=TicketView())


# -------------------------
# READY
# -------------------------
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
