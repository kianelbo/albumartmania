import os
import random
from tempfile import NamedTemporaryFile

from PIL import Image


TWITTER_MAX_IMAGE_BYTES = 5 * 1024 * 1024


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


def resize_if_needed(file_path):
        if os.path.getsize(file_path) <= TWITTER_MAX_IMAGE_BYTES:
            return file_path
        img = Image.open(file_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        quality = 90
        while quality >= 20:
            tmp = NamedTemporaryFile(suffix=".jpg", delete=False)
            img.save(tmp, format="JPEG", quality=quality)
            tmp.close()
            if os.path.getsize(tmp.name) <= TWITTER_MAX_IMAGE_BYTES:
                return tmp.name
            os.unlink(tmp.name)
            quality -= 10
        scale = 0.9
        while scale >= 0.3:
            resized = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS,
            )
            tmp = NamedTemporaryFile(suffix=".jpg", delete=False)
            resized.save(tmp, format="JPEG", quality=85)
            tmp.close()
            if os.path.getsize(tmp.name) <= TWITTER_MAX_IMAGE_BYTES:
                return tmp.name
            os.unlink(tmp.name)
            scale -= 0.1
        return file_path
