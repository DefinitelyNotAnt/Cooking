import os
import discord
from discord import app_commands
from PIL import Image
import random

COOKING_ROLE = "Cooking"
MEDIA_FOLDER = "./joinmedia"
LOOT_TABLE = {
    "Men": 0.55,
    "Mascot": 0.20,
    "Kanata": 0.099,
    "JCC": 0.15,
    "reveal": 0.001
}
RESULT_IMAGE_MAP = {
    "Men": ["men"],
    "Mascot": ["mascot"],
    "Kanata": ["kanata"],
    "JCC": ["jcc"],
    "Reveal": ["reveal"]
}
RARITY_COLORS = {
    "Cuck": 0x808080,
    "Mascot": 0x00FFFF,
    "Kanata": 0xFFD700,
    "JCC": 0xFF69B4,
    "Reveal": 0x800080
}


def load_images_by_category():
    image_map = {key: [] for key in RESULT_IMAGE_MAP}
    for filename in os.listdir(MEDIA_FOLDER):
        if filename.endswith((".png", ".jpg", ".jpeg", ".gif")):
            for key, keywords in RESULT_IMAGE_MAP.items():
                if any(k in filename.lower() for k in keywords):
                    image_map[key].append(os.path.join(MEDIA_FOLDER, filename))
    return image_map


IMAGE_MAP = load_images_by_category()


def compose_pulls_image(image_paths, tile_size=(250, 250)):
    width, height = tile_size
    images = [Image.open(path).convert("RGBA").resize((width, height), Image.LANCZOS) for path in image_paths]
    grid_width = width * 5
    grid_height = height * ((len(images) + 4) // 5)
    grid_image = Image.new("RGBA", (grid_width, grid_height), (0, 0, 0, 0))
    for index, img in enumerate(images):
        x = (index % 5) * width
        y = (index // 5) * height
        grid_image.paste(img, (x, y), img)
    output_path = os.path.join(MEDIA_FOLDER, "temp_tenpull_result.png")
    grid_image.save(output_path)
    return output_path


def roll_loot():
    items = list(LOOT_TABLE.keys())
    weights = list(LOOT_TABLE.values())
    return random.choices(items, weights=weights, k=1)[0]


gacha_group = app_commands.Group(name="gacha", description="Should you gacha")


@gacha_group.command(name="gacha", description="Let's go gambling")
async def gacha(interaction: discord.Interaction, pulls: int = 1):
    print("Pulls: " + str(pulls))
    if pulls > 30:
        pulls = 30
    elif pulls < 1:
        pulls = 1

    async def do_pull():
        results = [roll_loot() for _ in range(pulls)]
        images = [random.choice(IMAGE_MAP[result]) for result in results]
        return results, images

    async def send_result(results, images):
        pages = [results[i:i + 10] for i in range(0, len(results), 10)]
        image_pages = [images[i:i + 10] for i in range(0, len(images), 10)]

        def summarize_all(results_full):
            summary = {}
            for result in results_full:
                summary[result] = summary.get(result, 0) + 1
            return "\n".join(f"{item} ×{count}" for item, count in summary.items())

        def get_embed_and_file(page_index):
            final_image = compose_pulls_image(image_pages[page_index], tile_size=(250, 250))
            overall_highest = min(results, key=lambda r: LOOT_TABLE[r])
            color = RARITY_COLORS.get(overall_highest, 0xFFFFFF)
            embed = discord.Embed(
                title=f"🌰 Gacha Result (Page {page_index + 1}/{len(pages)})",
                description=summarize_all(results),
                color=color
            )
            file = discord.File(final_image, filename="result.png")
            embed.set_image(url="attachment://result.png")
            return embed, file

        return pages, image_pages, get_embed_and_file

    try:
        if interaction.response.is_done():
            followup = interaction.followup
        else:
            await interaction.response.defer()
            followup = interaction.followup

        results, images = await do_pull()
        pages, image_pages, get_embed_and_file = await send_result(results, images)
        current_page = 0

        if "Reveal" in results:
            await followup.send(
                f"🗣️🔥 **LEGENDARY DROP!!!** 🔥🗣️\n{interaction.user.mention} just pulled the **FULL ART**!\nEveryone bow 🙇‍♂️"
            )

        embed, file = get_embed_and_file(current_page)
        message = await followup.send(embed=embed, file=file)

        await message.add_reaction("⬅️")
        await message.add_reaction("🔁")
        await message.add_reaction("➡️")

        def check(reaction, user):
            return (
                user == interaction.user and
                str(reaction.emoji) in ["⬅️", "➡️", "🔁"] and
                reaction.message.id == message.id
            )

        while True:
            try:
                reaction, user = await interaction.client.wait_for("reaction_add", timeout=60.0, check=check)
                emoji = str(reaction.emoji)

                if emoji == "⬅️" and current_page > 0:
                    current_page -= 1
                elif emoji == "➡️" and current_page < len(pages) - 1:
                    current_page += 1
                elif emoji == "🔁":
                    try:
                        os.remove(os.path.join(MEDIA_FOLDER, "temp_tenpull_result.png"))
                    except:
                        pass
                    results, images = await do_pull()
                    pages, image_pages, get_embed_and_file = await send_result(results, images)
                    current_page = 0
                    if "Reveal" in results:
                        await followup.send(
                            f"🗣️🔥 **LEGENDARY DROP!!!** 🔥🗣️\n{interaction.user.mention} just pulled the **FULL ART**!\nEveryone bow 🙇‍♂️"
                        )

                embed, file = get_embed_and_file(current_page)
                await message.edit(embed=embed, attachments=[file])
                await message.clear_reactions()
                await message.add_reaction("⬅️")
                await message.add_reaction("🔁")
                await message.add_reaction("➡️")

            except Exception as e:
                print(f"Timeout or error in pagination: {e}")
                break

        try:
            os.remove(os.path.join(MEDIA_FOLDER, "temp_tenpull_result.png"))
        except Exception as cleanup_error:
            print(f"Failed to delete temp image: {cleanup_error}")

    except Exception as e:
        if not interaction.response.is_done():
            await interaction.response.send_message("Your gamble results were so bad that it crashed.\nNever try again.")
        else:
            await interaction.followup.send("Your gamble results were so bad that it crashed.\nNever try again.")
        print(f"Error in gacha: {e}")


@gacha_group.command(name="coinflip", description="Heads or Tails")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.defer()
    result = random.choice(["Heads", "Tails"])
    await interaction.followup.send(content=f"🎲 You rolled: {result}")
    return


custom_group = app_commands.Group(name="custom", description="For the bot to do stuff")


@custom_group.command(name="welcome", description="Welcome a member")
async def welcome(interaction: discord.Interaction, user: discord.User = None):
    try:
        media_folder = "./joinmedia"
        images = [
            f for f in os.listdir(media_folder)
            if f.endswith(('.png', '.jpg', '.jpeg', '.gif')) and not f.startswith('temp_')
        ]

        if not images:
            await interaction.response.send_message("No images found in the media folder.", ephemeral=True)
            return

        random_image = os.path.join(media_folder, random.choice(images))
        mention = user.mention if user else interaction.user.mention

        await interaction.response.send_message(
            content=(
                f"Welcome!! {mention}\n"
                f"For you, here's what you can do here.\n"
                f"You can view <#1338038250685726820> to find out the various channels, "
                f"or you can first introduce yourself at <#1338021134612041739>!"
            ),
            file=discord.File(random_image)
        )
    except Exception as e:
        print(f"Error in /welcome: {e}")
        await interaction.response.send_message("Something went wrong while sending the welcome message.", ephemeral=True)
