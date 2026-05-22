from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from video_foundry.shared.cache import FileCache, build_cache_key
from video_foundry.shared.errors import AppError


NASA_SEARCH_URL = "https://images-api.nasa.gov/search"


class NasaSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nasa_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1)
    source_url: str = Field(min_length=1, max_length=2048)
    credit: str = Field(min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    asset_manifest_url: str | None = Field(default=None, max_length=2048)
    center: str | None = Field(default=None, max_length=120)
    date_created: str | None = Field(default=None, max_length=80)


class NasaSearchResponse(BaseModel):
    results: list[NasaSearchResult]


class NasaApiClient:
    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        cache: FileCache | None = None,
    ) -> None:
        self._client = http_client or httpx.Client(timeout=12.0, follow_redirects=True)
        self._cache = cache

    def search(self, query: str, *, page_size: int = 10) -> list[NasaSearchResult]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            raise AppError(
                code="nasa_query_required",
                message="NASA search query is required.",
                status_code=422,
                step="nasa_search",
                retryable=True,
                suggested_correction="Enter a search term.",
            )
        safe_page_size = min(50, max(1, page_size))
        cache_key = build_cache_key("nasa_search", {"q": normalized_query, "page_size": safe_page_size})
        if self._cache is not None:
            cached = self._cache.get_json(cache_key)
            if cached is not None:
                return _validate_search_response(cached).results

        payload = self._request_json(
            NASA_SEARCH_URL,
            params={"q": normalized_query, "media_type": "image", "page_size": str(safe_page_size)},
            step="nasa_search",
        )
        results = _parse_search_payload(payload)
        response = NasaSearchResponse(results=results)
        if self._cache is not None:
            self._cache.set_json(cache_key, response.model_dump(mode="json"))
        return response.results

    def resolve_image_url(self, result: NasaSearchResult) -> str:
        if result.asset_manifest_url:
            manifest = self._request_json(result.asset_manifest_url, params=None, step="nasa_asset_manifest")
            selected = _select_asset_url(manifest)
            if selected:
                return selected
        if result.image_url:
            return result.image_url
        raise AppError(
            code="nasa_image_url_missing",
            message="NASA result does not include a downloadable image URL.",
            status_code=502,
            step="nasa_import",
            retryable=True,
            suggested_correction="Choose a different NASA result.",
            details={"nasa_id": result.nasa_id},
        )

    def download_image(self, image_url: str) -> bytes:
        try:
            response = self._client.get(image_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                code="nasa_image_download_failed",
                message="NASA image download failed.",
                status_code=502,
                step="nasa_import",
                retryable=True,
                suggested_correction="Retry the import or choose another result.",
                details={"exception_type": type(exc).__name__},
            ) from exc
        content = response.content
        if not content:
            raise AppError(
                code="nasa_image_download_failed",
                message="NASA image download returned an empty file.",
                status_code=502,
                step="nasa_import",
                retryable=True,
                suggested_correction="Retry the import or choose another result.",
            )
        return content

    def _request_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None,
        step: str,
    ) -> Any:
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(
                code="nasa_api_unavailable",
                message="NASA API request failed.",
                status_code=502,
                step=step,
                retryable=True,
                suggested_correction="Retry later or refine the search query.",
                details={"exception_type": type(exc).__name__},
            ) from exc


def _validate_search_response(payload: dict[str, Any]) -> NasaSearchResponse:
    try:
        return NasaSearchResponse.model_validate(payload)
    except ValidationError as exc:
        raise AppError(
            code="nasa_cache_invalid",
            message="Cached NASA search response is invalid.",
            status_code=500,
            step="nasa_search",
            retryable=True,
            suggested_correction="Clear the NASA cache and retry.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def _parse_search_payload(payload: Any) -> list[NasaSearchResult]:
    items = ((payload or {}).get("collection") or {}).get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise AppError(
            code="nasa_api_response_invalid",
            message="NASA API response did not contain search items.",
            status_code=502,
            step="nasa_search",
            retryable=True,
            suggested_correction="Retry later or refine the search query.",
        )
    results: list[NasaSearchResult] = []
    for item in items:
        parsed = _parse_search_item(item)
        if parsed is not None:
            results.append(parsed)
    return results


def _parse_search_item(item: Any) -> NasaSearchResult | None:
    if not isinstance(item, dict):
        return None
    data_items = item.get("data")
    if not isinstance(data_items, list) or not data_items or not isinstance(data_items[0], dict):
        return None
    data = data_items[0]
    nasa_id = str(data.get("nasa_id") or "").strip()
    title = _single_line(str(data.get("title") or "NASA image").strip())
    description = _single_line(str(data.get("description") or data.get("description_508") or "").strip())
    if not nasa_id or not description:
        return None
    center = _single_line(str(data.get("center") or "").strip()) or None
    secondary_creator = _single_line(str(data.get("secondary_creator") or "").strip())
    credit = _credit_text(center=center, secondary_creator=secondary_creator)
    thumbnail_url = _first_link_href(item.get("links"))
    source_url = f"https://images.nasa.gov/details/{quote(nasa_id, safe='')}"
    return NasaSearchResult(
        nasa_id=nasa_id,
        title=title,
        description=description,
        source_url=source_url,
        credit=credit,
        image_url=thumbnail_url,
        thumbnail_url=thumbnail_url,
        asset_manifest_url=str(item.get("href") or "").strip() or None,
        center=center,
        date_created=str(data.get("date_created") or "").strip() or None,
    )


def _first_link_href(links: Any) -> str | None:
    if not isinstance(links, list):
        return None
    for link in links:
        if isinstance(link, dict) and str(link.get("href") or "").strip():
            return str(link["href"]).strip()
    return None


def _select_asset_url(payload: Any) -> str | None:
    urls: list[str] = []
    if isinstance(payload, list):
        urls = [str(item).strip() for item in payload if str(item).strip()]
    elif isinstance(payload, dict):
        collection_items = ((payload.get("collection") or {}).get("items") or [])
        if isinstance(collection_items, list):
            for item in collection_items:
                href = item.get("href") if isinstance(item, dict) else None
                if href:
                    urls.append(str(href).strip())
    image_urls = [url for url in urls if _looks_like_image_url(url)]
    if not image_urls:
        return None
    for token in ("~orig", "_orig", "~large", "_large"):
        for url in image_urls:
            if token in url.lower():
                return url
    return image_urls[-1]


def _looks_like_image_url(url: str) -> bool:
    lower = url.lower()
    return any(lower.split("?")[0].endswith(extension) for extension in (".jpg", ".jpeg", ".png", ".webp"))


def _credit_text(*, center: str | None, secondary_creator: str) -> str:
    parts = ["NASA"]
    if center and center.upper() != "NASA":
        parts.append(center)
    if secondary_creator:
        parts.append(secondary_creator)
    return " / ".join(_dedupe(parts))


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            output.append(normalized)
    return output


def _single_line(value: str) -> str:
    return " ".join(value.split())
