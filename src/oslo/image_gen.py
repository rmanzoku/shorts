"""Image generation client supporting OpenAI and Google Gemini (Nano Banana)."""

import base64
import math
from io import BytesIO
from pathlib import Path

import click
from PIL import Image

from oslo.config import ImageGenConfig, VideoConfig
from oslo.text_processor import Scene
from oslo.utils import retry_on_rate_limit


class ImageGenerator:
    def __init__(
        self,
        openai_api_key: str,
        image_config: ImageGenConfig,
        video_config: VideoConfig,
        google_api_key: str = "",
    ):
        self.config = image_config
        self.video_config = video_config
        self._openai_api_key = openai_api_key
        self._google_api_key = google_api_key
        self._openai_client = None
        self._gemini_client = None

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self._openai_api_key)
        return self._openai_client

    def _get_gemini_client(self):
        if self._gemini_client is None:
            from google import genai

            self._gemini_client = genai.Client(api_key=self._google_api_key)
        return self._gemini_client

    @retry_on_rate_limit()
    def generate_image(self, prompt: str, output_path: Path) -> Path:
        """Generate a single image from a prompt, resize, and save to disk."""
        if self.config.provider == "gemini":
            return self._generate_gemini(prompt, output_path)
        return self._generate_openai(prompt, output_path)

    def _generate_openai(self, prompt: str, output_path: Path) -> Path:
        """Generate image using OpenAI gpt-image-1."""
        client = self._get_openai_client()
        result = client.images.generate(
            model=self.config.model,
            prompt=prompt,
            size=self.config.size,
            quality=self.config.quality,
        )
        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes))

        image = image.resize(
            (self.video_config.width, self.video_config.height), Image.LANCZOS
        )
        image.save(str(output_path), format="PNG")
        return output_path

    def _generate_gemini(self, prompt: str, output_path: Path) -> Path:
        """Generate image using Google Gemini (Nano Banana)."""
        from google.genai import types

        client = self._get_gemini_client()
        response = client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=self.config.aspect_ratio,
                ),
            ),
        )

        # Extract image from response parts
        image = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                image = Image.open(BytesIO(image_bytes))
                break

        if image is None:
            raise RuntimeError("Gemini API returned no image data")

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
                    provider = self.config.provider
                    click.echo(
                        f"  Generating image ({provider}) "
                        f"for scene {scene.index + 1}/{len(scenes)}..."
                    )
                self.generate_image(scene.image_prompt, image_path)
            image_paths.append(image_path)
        return image_paths
