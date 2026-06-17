# python3
# -*- coding: utf-8 -*-

from pathlib import Path

from PIL import Image

from nonebot_plugin_message_storage.services.images import maybe_compress_jpeg

ASSET_DIR = Path(__file__).resolve().parent / "assets"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}


def test_assets_cover_expected_fixture_count():
    assets = [path for path in ASSET_DIR.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES]

    assert len(assets) == 11


def test_all_assets_can_be_compressed_to_readable_images():
    for asset in ASSET_DIR.iterdir():
        if asset.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        compressed = maybe_compress_jpeg(asset.read_bytes())
        assert len(compressed) > 0

        image = Image.open(asset)
        assert image.width > 0
        assert image.height > 0
