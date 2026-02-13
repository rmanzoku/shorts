"""OpenAI image generation client."""

import base64
import math
from io import BytesIO
from pathlib import Path

import click
from openai import OpenAI
from PIL import Image

from oslo.config import ImageGenConfig, VideoConfig
from oslo.text_processor import Scene
from oslo.utils import retry_on_rate_limit


class ImageGenerator:
    def __init__(self, api_key: str, config: ImageGenConfig, video_config: VideoConfig):
        self.client = OpenAI(api_key=api_key)
        self.config = config
        self.video_config = video_config

    @retry_on_rate_limit()
    def generate_image(self, prompt: str, output_path: Path) -> Path:
        """Generate a single image from a prompt, resize, and save to disk."""
        result = self.client.images.generate(
            model=self.config.model,
            prompt=prompt,
            size=self.config.size,
            quality=self.config.quality,
        )
        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes))

        # Resize to exact video dimensions
        image = image.resize(
            (self.video_config.width, self.video_config.height), Image.LANCZOS
        )
        image.save(str(output_path), format="PNG")
        return output_path

    def copy_and_resize_library_image(self, slug: str, output_path: Path) -> Path:
        """Copy a library image, resizing to video dimensions with cover+center crop."""
        from oslo.library import resolve_image_path

        source = resolve_image_path(slug)
        image = Image.open(str(source)).convert("RGB")

        target_w = self.video_config.width
        target_h = self.video_config.height
        img_w, img_h = image.size

        # Cover: scale so smallest dimension fills target (ceil to avoid 1px shortage)
        scale = max(target_w / img_w, target_h / img_h)
        new_w = math.ceil(img_w * scale)
        new_h = math.ceil(img_h * scale)
        image = image.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        image = image.crop((left, top, left + target_w, top + target_h))

        image.save(str(output_path), format="PNG")
        return output_path

    def generate_all_scenes(
        self, scenes: list[Scene], temp_dir: Path, verbose: bool = False
    ) -> list[Path]:
        """Generate images for all scenes. Returns list of image file paths."""
        image_paths = []
        for scene in scenes:
            image_path = temp_dir / f"scene_{scene.index:03d}.png"
            if scene.library_image:
                if verbose:
                    click.echo(
                        f"  Using library image '{scene.library_image}' "
                        f"for scene {scene.index + 1}/{len(scenes)}..."
                    )
                self.copy_and_resize_library_image(scene.library_image, image_path)
            else:
                if verbose:
                    click.echo(
                        f"  Generating image for scene {scene.index + 1}/{len(scenes)}..."
                    )
                self.generate_image(scene.image_prompt, image_path)
            image_paths.append(image_path)
        return image_paths
