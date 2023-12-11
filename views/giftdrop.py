import discord, asyncio
import functions as func

class GiftButton(discord.ui.Button):
    def __init__(self, **kwargs):

        self.gift_owner: int = None
        self.naughty_list: list[int] = [941709022560682080,406986532205887488, 751737106803720244]

        super().__init__(
            emoji="🎁",
            style=discord.ButtonStyle.green,
            **kwargs
        )

    async def callback(self, interaction: discord.Interaction) -> None:

        self.view: GiftDropView

        if interaction.user.id in self.naughty_list:
            return await interaction.response.send_message(f"<:IUsanta:786519160083447838> You're on Santa's naughty list, <@{interaction.user.id}>! No gifts for you!")

        if owner_id := self.gift_owner:
            if owner_id != interaction.user.id:
                return await interaction.response.send_message(f"<:IUsanta:786519160083447838> Santa's sleigh delivered this gift to <@{owner_id}>")
            else:
                return await interaction.response.send_message(
                    "Oh, ho, ho! You already received this gift! Naughty or nice, you can't claim it twice!"
                )

        self.gift_owner = interaction.user.id
        await func.update_user(interaction.user.id, {"$inc": {"gifts": 1}})
        self.view.claimed_users.add(interaction.user)
        
        self.disabled = True
        self.style = discord.ButtonStyle.gray

        await interaction.message.edit(view=self.view)

        await interaction.response.send_message(f"{interaction.user.mention} is on Santa's nice list and has received a Christmas gift!")



class GiftDropView(discord.ui.View):
    def __init__(self, image_link: str, *, timeout: float | None = None):
        super().__init__(timeout=timeout)

        self.image_link: str = image_link
        self.claimed_users: set[discord.Member] = set()
        self.message: discord.Message = None

        for i in range(3):
            self.add_item(GiftButton(custom_id=str(i)))

    async def timeout_count(self):
        await asyncio.sleep(360)
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True

        await self.message.edit(
            content=f"Tinsel time's up! This Drop has melted away like a snowflake in the sun❄️[.]({self.image_link})",
            view=self
        )
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user in self.claimed_users:
            await interaction.response.send_message("Oh, ho, ho! Naughty or nice, you can't claim twice!", ephemeral=True)
            return False
        
        return True
