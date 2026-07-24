"""Content-addressed storage tests."""

from __future__ import annotations

import pytest

from app.ingestion.fetcher import FetchedDocument
from app.ingestion.storage import (
    InMemoryDocumentStorage,
    LocalFilesystemStorage,
    content_hash_bytes,
    storage_key_for_hash,
)


def _doc(body: bytes, url: str = "https://example.com/a") -> FetchedDocument:
    return FetchedDocument(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        body=body,
        content_hash=content_hash_bytes(body),
    )


class TestInMemoryStorage:
    @pytest.mark.asyncio
    async def test_store_and_get(self) -> None:
        store = InMemoryDocumentStorage()
        ref = await store.store_document(_doc(b"hello"))
        assert ref.byte_size == 5
        assert ref.reused_existing is False
        data = await store.get_bytes(ref.storage_key)
        assert data == b"hello"

    @pytest.mark.asyncio
    async def test_duplicate_hash_reused(self) -> None:
        store = InMemoryDocumentStorage()
        body = b"same-bytes"
        r1 = await store.store_document(_doc(body, url="https://a.example/1"))
        r2 = await store.store_document(_doc(body, url="https://b.example/2"))
        assert r1.content_hash == r2.content_hash
        assert r1.storage_key == r2.storage_key
        assert r2.reused_existing is True
        assert len(store.objects) == 1


class TestLocalFilesystemStorage:
    @pytest.mark.asyncio
    async def test_local_store(self, tmp_path) -> None:
        store = LocalFilesystemStorage(tmp_path)
        ref = await store.store_document(_doc(b"on-disk"))
        assert await store.exists(ref.content_hash)
        assert (tmp_path / ref.storage_key).read_bytes() == b"on-disk"
        # second write reuses
        ref2 = await store.store_document(_doc(b"on-disk"))
        assert ref2.reused_existing is True

    def test_storage_key_sharding(self) -> None:
        h = "abcdef0123456789" + "0" * 48
        key = storage_key_for_hash(h)
        assert key.startswith("raw/ab/")
