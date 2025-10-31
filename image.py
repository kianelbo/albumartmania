import random
from PIL import Image

def crop_image(image_path, output_path="./cropped", reveal_ratio=0.25):
    with Image.open(image_path) as img:
        width, height = img.size

        crop_width = int(width * reveal_ratio)
        crop_height = int(height * reveal_ratio)

        x_start = random.randint(0, width - crop_width)
        y_start = random.randint(0, height - crop_height)

        cropped = img.crop((x_start, y_start, x_start + crop_width, y_start + crop_height))
        ext = image_path.split(".")[-1]
        output_path = f"{output_path}.{ext}"
        cropped.save(output_path)

    return output_path
