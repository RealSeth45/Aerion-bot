import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

TOKEN = "MTUwMDgzMzg1MTM4MTkxMTYzMg.G2xYWO.x8_xebTPBbgVCjBSzErKNYsKekelre9etMn7Tc"

# Role IDs
CREATIVE_DIRECTOR = 1489266283890348226
MANAGER_ROLE = 1496533568149651538
MOD_ROLE = 1490457179000672336

# Ticket category
TICKET_CATEGORY_ID = 1489336819236475000

# Logging channel
LOG_CHANNEL_ID = 1500836989702897776

# Queue channel
QUEUE_CHANNEL_ID = 1489295574783102976

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

warnings = {}
commission_queue = []
queue_message_id = None  # will store the ID of the QUE! message


# ---------------------------------------------------
# PERMISSION CHECKS
# ---------------------------------------------------
def is_creative_director():
    async def predicate(interaction: discord.Interaction):
        return any(role.id == CREATIVE_DIRECTOR for role in interaction.user.roles)
    return app_commands.check(predicate)

def is_manager():
    async def predicate(interaction: discord.Interaction):
        return any(role.id == MANAGER_ROLE for role in interaction.user.roles) or \
               any(role.id == CREATIVE_DIRECTOR for role in interaction.user.roles)
    return app_commands.check(predicate)

def is_mod():
    async def predicate(interaction: discord.Interaction):
        return any(role.id in [MOD_ROLE, MANAGER_ROLE, CREATIVE_DIRECTOR] for role in interaction.user.roles)
    return app_commands.check(predicate)


# ---------------------------------------------------
# LOGGING HELPER
# ---------------------------------------------------
async def send_log(title, description, color=discord.Color.blue()):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Aerion Moderation Log")
    await channel.send(embed=embed)


# ---------------------------------------------------
# QUEUE HELPERS
# ---------------------------------------------------
def build_queue_embed(guild: discord.Guild) -> discord.Embed:
    header = (
        "# <:AerionBG:1489347300231876778>   QUE!\n\n"
        "**This message is updated every time a new order is placed. "
        "If we exceed 2 orders, they may not be added and you can assume we are not working on them yet.**\n\n"
    )

    lines = []
    for i in range(3):
        if i < len(commission_queue):
            entry = commission_queue[i]
            member = guild.get_member(entry["user_id"])
            mention = member.mention if member else f"<@{entry['user_id']}>"
            lines.append(f"> **{i+1}.** {mention} — {entry['order']}")
        else:
            lines.append(f"> Position {i+1}.")

    embed = discord.Embed(
        description=header + "\n".join(lines),
        color=discord.Color.blue()
    )
    return embed


async def update_queue_message(guild: discord.Guild):
    global queue_message_id
    channel = guild.get_channel(QUEUE_CHANNEL_ID)
    if not channel:
        return

    embed = build_queue_embed(guild)

    if queue_message_id is None:
        msg = await channel.send(embed=embed)
        queue_message_id = msg.id
    else:
        try:
            msg = await channel.fetch_message(queue_message_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            msg = await channel.send(embed=embed)
            queue_message_id = msg.id


# ---------------------------------------------------
# ON READY
# ---------------------------------------------------
@bot.event
async def on_ready():
    print(f"{bot.user} is online.")
    await bot.tree.sync()


# ---------------------------------------------------
# STATUS COMMAND (Creative Director only)
# ---------------------------------------------------
@bot.tree.command(name="status", description="Change the bot's status")
@is_creative_director()
async def status(interaction: discord.Interaction, text: str):
    await bot.change_presence(activity=discord.Game(name=text))
    await interaction.response.send_message(f"Status updated to: **{text}**")


# ---------------------------------------------------
# MODERATION COMMANDS
# ---------------------------------------------------
@bot.tree.command(name="warn", description="Warn a member")
@is_mod()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    warnings.setdefault(member.id, []).append(reason)
    await interaction.response.send_message(f"{member} has been warned. Reason: {reason}")

@bot.tree.command(name="warnings", description="View a member's warnings")
@is_mod()
async def view_warnings(interaction: discord.Interaction, member: discord.Member):
    user_warnings = warnings.get(member.id, [])
    if not user_warnings:
        await interaction.response.send_message(f"{member} has no warnings.")
        return
    formatted = "\n".join([f"{i+1}. {w}" for i, w in enumerate(user_warnings)])
    await interaction.response.send_message(f"Warnings for {member}:\n{formatted}")

@bot.tree.command(name="kick", description="Kick a member")
@is_mod()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"{member} has been kicked. Reason: {reason}")

@bot.tree.command(name="timeout", description="Timeout a member")
@is_mod()
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(until, reason=reason)
    await interaction.response.send_message(f"{member} has been timed out for {minutes} minutes.")

@bot.tree.command(name="ban", description="Ban a member")
@is_manager()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"{member} has been banned. Reason: {reason}")


# ---------------------------------------------------
# QUEUE COMMANDS
# ---------------------------------------------------
@bot.tree.command(name="queue", description="View the commission queue")
async def queue_cmd(interaction: discord.Interaction):
    embed = build_queue_embed(interaction.guild)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="queue_remove", description="Remove a user from the commission queue")
@is_creative_director()
async def queue_remove(interaction: discord.Interaction, member: discord.Member):
    global commission_queue
    before_len = len(commission_queue)
    commission_queue = [e for e in commission_queue if e["user_id"] != member.id]
    after_len = len(commission_queue)

    await update_queue_message(interaction.guild)

    if before_len == after_len:
        await interaction.response.send_message(f"{member.mention} was not in the queue.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Removed {member.mention} from the queue.", ephemeral=True)

@bot.tree.command(name="queue_clear", description="Clear the commission queue")
@is_creative_director()
async def queue_clear(interaction: discord.Interaction):
    commission_queue.clear()
    await update_queue_message(interaction.guild)
    await interaction.response.send_message("Commission queue cleared.", ephemeral=True)


# ---------------------------------------------------
# TICKET SYSTEM
# ---------------------------------------------------
class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    user_id = discord.ui.TextInput(label="User ID")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = interaction.guild.get_member(int(self.user_id.value))
            await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
            await interaction.response.send_message(f"Added {user.mention} to the ticket.")
        except:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)

class RemoveUserModal(discord.ui.Modal, title="Remove User from Ticket"):
    user_id = discord.ui.TextInput(label="User ID")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = interaction.guild.get_member(int(self.user_id.value))
            await interaction.channel.set_permissions(user, overwrite=None)
            await interaction.response.send_message(f"Removed {user.mention} from the ticket.")
        except:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)

class QueueAddModal(discord.ui.Modal, title="Add Commission to Queue"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="User ID of the client")
    order = discord.ui.TextInput(label="Order Details", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.user_id.value)
            commission_queue.append({
                "user_id": uid,
                "order": self.order.value
            })
            await update_queue_message(interaction.guild)
            member = interaction.guild.get_member(uid)
            mention = member.mention if member else f"<@{uid}>"
            await interaction.response.send_message(
                f"Added {mention} to the commission queue at position **{len(commission_queue)}**.",
                ephemeral=True
            )
        except:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)

class TicketControls(discord.ui.View):
    def __init__(self, opener_id):
        super().__init__(timeout=None)
        self.opener_id = opener_id
        self.claimed = False

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == MANAGER_ROLE for role in interaction.user.roles):
            return await interaction.response.send_message("Only managers can claim tickets.", ephemeral=True)

        if self.claimed:
            return await interaction.response.send_message("This ticket is already claimed.", ephemeral=True)

        self.claimed = True
        button.disabled = True
        await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in [MANAGER_ROLE, CREATIVE_DIRECTOR] for role in interaction.user.roles):
            return await interaction.response.send_message("You cannot close this ticket.", ephemeral=True)

        opener = interaction.guild.get_member(self.opener_id)
        if opener:
            await interaction.channel.set_permissions(opener, view_channel=False)
        await interaction.response.send_message("Ticket closed.")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.gray)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in [MANAGER_ROLE, CREATIVE_DIRECTOR] for role in interaction.user.roles):
            return await interaction.response.send_message("You cannot delete this ticket.", ephemeral=True)

        await interaction.response.send_message("Deleting ticket...", ephemeral=True)
        await interaction.channel.delete()

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.green)
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in [MANAGER_ROLE, CREATIVE_DIRECTOR] for role in interaction.user.roles):
            return await interaction.response.send_message("You cannot add users.", ephemeral=True)

        await interaction.response.send_modal(AddUserModal())

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.red)
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in [MANAGER_ROLE, CREATIVE_DIRECTOR] for role in interaction.user.roles):
            return await interaction.response.send_message("You cannot remove users.", ephemeral=True)

        await interaction.response.send_modal(RemoveUserModal())

    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.blurple)
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == MANAGER_ROLE for role in interaction.user.roles):
            return await interaction.response.send_message("Only managers can transfer tickets.", ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        opener = guild.get_member(self.opener_id)

        # Remove manager access
        for role in guild.roles:
            if role.id == MANAGER_ROLE:
                await channel.set_permissions(role, view_channel=False)

        # Keep Creative Director + opener
        cd_role = guild.get_role(CREATIVE_DIRECTOR)
        if cd_role:
            await channel.set_permissions(cd_role, view_channel=True, send_messages=True)
        if opener:
            await channel.set_permissions(opener, view_channel=True, send_messages=True)

        # Rename channel
        new_name = f"🔴-ticket-{opener.name if opener else 'user'}"
        await channel.edit(name=new_name)

        # Disable claim
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Claim":
                child.disabled = True

        await interaction.response.send_message("This ticket has been transferred to Creative Director support.")

class TicketPanel(discord.ui.View):
    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        opener = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            opener: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(MANAGER_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(CREATIVE_DIRECTOR): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{opener.name}",
            overwrites=overwrites,
            category=category
        )

        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title="🎨 Commission Ticket Opened",
            description=(
                "Thank you for opening a commission ticket!\n"
                "Please fill out the form below:\n\n"
                "**Roblox Username:**\n"
                "**Usernames in GFX:**\n"
                "**Type (Mat / Glossy):**\n"
                "**Background:**\n"
                "**Pose Reference:**\n"
                "**Extra:**\n\n"
                "A staff member will claim your ticket shortly."
            ),
            color=discord.Color.blue()
        )

        await channel.send(embed=embed, view=TicketControls(opener.id))

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.gray)
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == CREATIVE_DIRECTOR for role in interaction.user.roles):
            return await interaction.response.send_message("Only the Creative Director can use settings.", ephemeral=True)

        await interaction.response.send_modal(QueueAddModal())


# ---------------------------------------------------
# TICKET PANEL COMMAND (Creative Director only)
# ---------------------------------------------------
@bot.tree.command(name="ticketpanel", description="Send the ticket panel to a channel")
@is_creative_director()
@app_commands.describe(channel="Channel to send the panel to")
async def ticketpanel(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="Support Tickets",
        description="Click the button below to open a support ticket.",
        color=discord.Color.blue()
    )
    await channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message(f"Ticket panel sent to {channel.mention}", ephemeral=True)


# ---------------------------------------------------
# LOGGING EVENTS (trimmed but functional)
# ---------------------------------------------------
@bot.event
async def on_message_delete(message):
    if not message.author.bot:
        await send_log("🗑️ Message Deleted", f"**Author:** {message.author}\n**Content:** {message.content}", discord.Color.red())

@bot.event
async def on_message_edit(before, after):
    if not before.author.bot and before.content != after.content:
        await send_log("✏️ Message Edited", f"**Before:** {before.content}\n**After:** {after.content}", discord.Color.orange())

@bot.event
async def on_member_join(member):
    await send_log("👋 Member Joined", f"{member} joined the server.", discord.Color.green())

@bot.event
async def on_member_remove(member):
    await send_log("🚪 Member Left", f"{member} left the server.", discord.Color.red())


# ---------------------------------------------------
# RUN BOT
# ---------------------------------------------------
bot.run(TOKEN)
