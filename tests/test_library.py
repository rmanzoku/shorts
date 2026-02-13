"""Tests for library module."""

import pytest

from oslo.library import (
    ImageMeta,
    add_image,
    list_images,
    load_image_meta,
    resolve_image_path,
    search_images,
)


@pytest.fixture()
def library_dir(tmp_path):
    """Create a temporary library directory with test images."""
    lib = tmp_path / "images"
    lib.mkdir()

    # Create test image files (1x1 PNG placeholder)
    (lib / "001_kokkai.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    (lib / "002_shibuya.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

    # Create YAML sidecars
    (lib / "001_kokkai.yml").write_text(
        "tags:\n  - 政治\n  - 国会議事堂\n  - 建物\n"
        'description: "国会議事堂の正面外観"\n'
        'source: "Unsplash"\n'
        'added: "2026-02-13"\n',
        encoding="utf-8",
    )
    (lib / "002_shibuya.yml").write_text(
        "tags:\n  - 渋谷\n  - 街\n  - 夜\n"
        'description: "渋谷のスクランブル交差点"\n'
        'source: ""\n'
        'added: "2026-02-13"\n',
        encoding="utf-8",
    )

    return lib


def test_resolve_image_path_png(library_dir):
    path = resolve_image_path("001_kokkai", library_dir)
    assert path.name == "001_kokkai.png"
    assert path.exists()


def test_resolve_image_path_jpg(library_dir):
    path = resolve_image_path("002_shibuya", library_dir)
    assert path.name == "002_shibuya.jpg"
    assert path.exists()


def test_resolve_image_path_not_found(library_dir):
    with pytest.raises(FileNotFoundError, match="Image not found for slug '999_missing'"):
        resolve_image_path("999_missing", library_dir)


def test_load_image_meta_basic(library_dir):
    meta = load_image_meta("001_kokkai", library_dir)
    assert isinstance(meta, ImageMeta)
    assert meta.slug == "001_kokkai"
    assert "政治" in meta.tags
    assert "国会議事堂" in meta.tags
    assert meta.description == "国会議事堂の正面外観"
    assert meta.source == "Unsplash"
    assert meta.added == "2026-02-13"


def test_load_image_meta_missing_sidecar(library_dir):
    """When no .yml sidecar exists, return defaults."""
    (library_dir / "003_test.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    meta = load_image_meta("003_test", library_dir)
    assert meta.slug == "003_test"
    assert meta.tags == ()
    assert meta.description == ""


def test_list_images(library_dir):
    images = list_images(library_dir)
    assert len(images) == 2
    slugs = [img.slug for img in images]
    assert "001_kokkai" in slugs
    assert "002_shibuya" in slugs


def test_list_images_empty(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert list_images(empty_dir) == []


def test_search_images_by_tag(library_dir):
    results = search_images(["政治"], library_dir)
    assert len(results) == 1
    assert results[0].slug == "001_kokkai"


def test_search_images_multiple_tags(library_dir):
    results = search_images(["政治", "建物"], library_dir)
    assert len(results) == 1
    assert results[0].slug == "001_kokkai"


def test_search_images_no_match(library_dir):
    results = search_images(["存在しないタグ"], library_dir)
    assert results == []


def test_search_images_case_insensitive(library_dir):
    """Tag matching should be case-insensitive."""
    (library_dir / "003_test.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    (library_dir / "003_test.yml").write_text(
        "tags:\n  - Tokyo\n  - Night\n", encoding="utf-8"
    )
    results = search_images(["tokyo"], library_dir)
    assert len(results) == 1


def test_add_image_auto_slug(library_dir, tmp_path):
    src = tmp_path / "my-photo.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    meta = add_image(src, library_dir=library_dir)
    assert meta.slug == "003_my-photo"
    assert (library_dir / "003_my-photo.png").exists()
    assert (library_dir / "003_my-photo.yml").exists()


def test_add_image_custom_slug(library_dir, tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    meta = add_image(
        src,
        slug="010_custom",
        tags=("テスト",),
        description="テスト画像",
        source="手動",
        library_dir=library_dir,
    )
    assert meta.slug == "010_custom"
    assert "テスト" in meta.tags


def test_add_image_duplicate_raises(library_dir, tmp_path):
    src = tmp_path / "kokkai.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    with pytest.raises(FileExistsError):
        add_image(src, slug="001_kokkai", library_dir=library_dir)


def test_add_image_unsupported_format(library_dir, tmp_path):
    src = tmp_path / "file.bmp"
    src.write_bytes(b"BM" + b"\x00" * 100)

    with pytest.raises(ValueError, match="Unsupported image format"):
        add_image(src, library_dir=library_dir)
