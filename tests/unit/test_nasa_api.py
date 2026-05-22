from __future__ import annotations

from pathlib import Path

import httpx

from video_foundry.shared.cache import FileCache
from video_foundry.sources.nasa_api import NasaApiClient, NasaSearchResult


def test_nasa_search_parses_reduced_metadata_and_uses_cache(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["media_type"] == "image"
        return httpx.Response(
            200,
            json={
                "collection": {
                    "items": [
                        {
                            "href": "https://images-api.nasa.gov/asset/PIA00001",
                            "data": [
                                {
                                    "nasa_id": "PIA00001",
                                    "title": "Moon",
                                    "description": "Official lunar source description.",
                                    "center": "JPL",
                                    "secondary_creator": "Example Mission",
                                    "date_created": "2026-01-01T00:00:00Z",
                                }
                            ],
                            "links": [{"href": "https://images-assets.nasa.gov/thumb.jpg"}],
                        }
                    ]
                }
            },
        )

    client = NasaApiClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache=FileCache(tmp_path / "cache", namespace="nasa"),
    )

    first = client.search("moon", page_size=1)
    second = client.search("moon", page_size=1)

    assert calls == 1
    assert first == second
    assert first[0].source_url == "https://images.nasa.gov/details/PIA00001"
    assert first[0].credit == "NASA / JPL / Example Mission"


def test_nasa_asset_manifest_prefers_original_image() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                "https://images-assets.nasa.gov/PIA00001~thumb.jpg",
                "https://images-assets.nasa.gov/PIA00001~orig.jpg",
            ],
        )

    client = NasaApiClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    image_url = client.resolve_image_url(
        NasaSearchResult(
            nasa_id="PIA00001",
            title="Moon",
            description="Description",
            source_url="https://images.nasa.gov/details/PIA00001",
            credit="NASA",
            asset_manifest_url="https://images-api.nasa.gov/asset/PIA00001",
        )
    )

    assert image_url.endswith("~orig.jpg")
