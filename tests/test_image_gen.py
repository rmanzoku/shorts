"""Tests for image generation module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from oslo.config import ImageGenConfig, VideoConfig
from oslo.image_gen import ImageGenerator


@pytest.fixture
def video_config():
    return VideoConfig(width=1080, height=1920)


@pytest.fixture
def gemini_config():
    return ImageGenConfig(
        provider="gemini",
        model="gemini-3-pro-image-preview",
        aspect_ratio="9:16",
    )


@pytest.fixture
def openai_config():
    return ImageGenConfig(
        provider="openai",
        model="gpt-image-1",
        size="1024x1536",
        quality="medium",
    )


class TestImageGeneratorInit:
    def test_default_config_is_gemini(self):
        config = ImageGenConfig()
        assert config.provider == "gemini"
        assert config.model == "gemini-3-pro-image-preview"
        assert config.aspect_ratio == "9:16"

    def test_openai_config(self, openai_config):
        assert openai_config.provider == "openai"
        assert openai_config.model == "gpt-image-1"

    def test_lazy_client_init(self, gemini_config, video_config):
        gen = ImageGenerator(
            openai_api_key="test-openai",
            image_config=gemini_config,
            video_config=video_config,
            google_api_key="test-google",
        )
        assert gen._openai_client is None
        assert gen._gemini_client is None


class TestGeminiGeneration:
    def test_generate_gemini_image(self, gemini_config, video_config, tmp_path):
        gen = ImageGenerator(
            openai_api_key="",
            image_config=gemini_config,
            video_config=video_config,
            google_api_key="test-google",
        )

        # Create a fake image to return
        fake_image = Image.new("RGB", (512, 768), color="blue")
        from io import BytesIO

        buf = BytesIO()
        fake_image.save(buf, format="PNG")
        fake_image_bytes = buf.getvalue()

        mock_part = MagicMock()
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = fake_image_bytes

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        gen._gemini_client = mock_client

        output = tmp_path / "test.png"
        result = gen.generate_image("test prompt", output)

        assert result == output
        assert output.exists()
        img = Image.open(output)
        assert img.size == (1080, 1920)

        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-3-pro-image-preview"
        assert call_kwargs.kwargs["contents"] == "test prompt"

    def test_generate_gemini_no_image_raises(self, gemini_config, video_config, tmp_path):
        gen = ImageGenerator(
            openai_api_key="",
            image_config=gemini_config,
            video_config=video_config,
            google_api_key="test-google",
        )

        mock_part = MagicMock()
        mock_part.inline_data = None

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        gen._gemini_client = mock_client

        with pytest.raises(RuntimeError, match="Gemini API returned no image data"):
            gen.generate_image("test prompt", tmp_path / "fail.png")


class TestOpenAIGeneration:
    def test_generate_openai_image(self, openai_config, video_config, tmp_path):
        gen = ImageGenerator(
            openai_api_key="test-openai",
            image_config=openai_config,
            video_config=video_config,
        )

        import base64
        from io import BytesIO

        fake_image = Image.new("RGB", (1024, 1536), color="red")

        buf = BytesIO()
        fake_image.save(buf, format="PNG")
        fake_b64 = base64.b64encode(buf.getvalue()).decode()

        mock_data = MagicMock()
        mock_data.b64_json = fake_b64

        mock_result = MagicMock()
        mock_result.data = [mock_data]

        mock_client = MagicMock()
        mock_client.images.generate.return_value = mock_result
        gen._openai_client = mock_client

        output = tmp_path / "test.png"
        result = gen.generate_image("test prompt", output)

        assert result == output
        assert output.exists()
        img = Image.open(output)
        assert img.size == (1080, 1920)

        mock_client.images.generate.assert_called_once_with(
            model="gpt-image-1",
            prompt="test prompt",
            size="1024x1536",
            quality="medium",
        )


class TestProviderDispatch:
    def test_dispatches_to_gemini(self, gemini_config, video_config):
        gen = ImageGenerator(
            openai_api_key="",
            image_config=gemini_config,
            video_config=video_config,
            google_api_key="test",
        )
        with patch.object(gen, "_generate_gemini") as mock:
            mock.return_value = Path("test.png")
            gen.generate_image("prompt", Path("test.png"))
            mock.assert_called_once()

    def test_dispatches_to_openai(self, openai_config, video_config):
        gen = ImageGenerator(
            openai_api_key="test",
            image_config=openai_config,
            video_config=video_config,
        )
        with patch.object(gen, "_generate_openai") as mock:
            mock.return_value = Path("test.png")
            gen.generate_image("prompt", Path("test.png"))
            mock.assert_called_once()
