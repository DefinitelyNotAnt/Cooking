import os
import discord
from discord import app_commands
from PIL import Image
import random

AUDIT_ROLES = "Maincomm"
COOKING_ROLE = "Cooking"
MEDIA_FOLDER = "./joinmedia"
LOOT_TABLE = {
    "Cuck" : 0.8,
    "Mascot": 0.1,
    "Kanata": 0.05,
    "JCC":0.049,
    "Rishan": 0.001
}
RESULT_IMAGE_MAP = {
    "Cuck": ["cuck"],
    "Mascot": ["mascot"],
    "Kanata": ["kanata"],
    "JCC": ["jcc"],
    "Rishan": ["men"]
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

def compose_tenpull_image(image_paths):
    images = [Image.open(path).convert("RGBA") for path in image_paths]
    width, height = images[0].size
    grid_image = Image.new("RGBA", (width * 5, height * 2))

    for index, img in enumerate(images):
        x = (index % 5) * width
        y = (index // 5) * height
        grid_image.paste(img, (x, y))

    output_path = os.path.join(MEDIA_FOLDER, "temp_tenpull_result.png")
    grid_image.save(output_path)
    return output_path

#############################################
# Gacha Command Group                       #
#############################################

def roll_loot():
    items = list(LOOT_TABLE.keys())
    weights = list(LOOT_TABLE.values())
    return random.choices(items, weights=weights, k=1)[0]

gacha_group = app_commands.Group(name="gacha", description="Should you gacha")
@gacha_group.command(name="gacha", description="Let's go gambling")
async def gacha(interaction: discord.Interaction, tenpull: bool = False):
    try:
        await interaction.response.defer()

        pulls = 10 if tenpull else 1
        results = [roll_loot() for _ in range(pulls)]
        images = [random.choice(IMAGE_MAP[result]) for result in results]

        if tenpull:
            final_image = compose_tenpull_image(images)
            result_text = "\n".join(f"{i+1}. {results[i]}" for i in range(10))
        else:
            final_image = images[0]
            result_text = f"You got: **{results[0]}**"

        await interaction.followup.send(
            content=f"🎲 Your gamble results:\n{result_text}",
            file=discord.File(final_image)
        )

    except Exception as e:
        await interaction.followup.send(
            f"Your gamble results were so bad that it crashed.\nNever try again."
        )
        print(f"Error in gacha: {e}")

@gacha_group.command(name="coinflip", description="Heads or Tails")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.defer()
    result = random.choice(["Heads", "Tails"])
    await interaction.followup.send(
        content=f"🎲 You rolled: {result}"
    )
    return