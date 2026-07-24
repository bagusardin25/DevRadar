"""Content-addressed raw document storage (S3-compatible or local/memory)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.config import Settings
from app.ingestion.fetcher import FetchedDocument


@dataclass(slots=True)
class RawDocumentRef:
    storage_key: str
    content_hash: str
    byte_size: int
    content_type: str | None
    etag: str | None = None
    last_modified: str | None = None
    canonical_url: str = ""
    http_status: int | None = None
    # Set when a DB row is created by a higher layer.
    raw_document_id: UUID | None = None
    reused_existing: bool = False


class DocumentStorage(Protocol):
    async def store_document(self, document: FetchedDocument) -> RawDocumentRef: ...

    async def exists(self, content_hash: str) -> bool: ...

    async def get_bytes(self, storage_key: str) -> bytes: ...


def content_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_key_for_hash(content_hash: str, *, prefix: str = "raw") -> str:
    # Shard by first 2 hex chars for filesystem friendliness.
    return f"{prefix}/{content_hash[:2]}/{content_hash}"


class InMemoryDocumentStorage:
    """Test double: holds blobs in process memory."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.meta: dict[str, RawDocumentRef] = {}

    async def store_document(self, document: FetchedDocument) -> RawDocumentRef:
        digest = document.content_hash or content_hash_bytes(document.body)
        key = storage_key_for_hash(digest)
        reused = key in self.objects
        if not reused:
            self.objects[key] = document.body
        ref = RawDocumentRef(
            storage_key=key,
            content_hash=digest,
            byte_size=len(document.body),
            content_type=document.content_type,
            etag=document.etag,
            last_modified=document.last_modified,
            canonical_url=document.final_url,
            http_status=document.status_code,
            reused_existing=reused,
        )
        self.meta[key] = ref
        return ref

    async def exists(self, content_hash: str) -> bool:
        return storage_key_for_hash(content_hash) in self.objects

    async def get_bytes(self, storage_key: str) -> bytes:
        return self.objects[storage_key]


class LocalFilesystemStorage:
    """Dev storage under a local directory (no MinIO required)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def store_document(self, document: FetchedDocument) -> RawDocumentRef:
        digest = document.content_hash or content_hash_bytes(document.body)
        key = storage_key_for_hash(digest)
        path = self._path(key)
        reused = path.exists()
        if not reused:
            path.write_bytes(document.body)
        return RawDocumentRef(
            storage_key=key,
            content_hash=digest,
            byte_size=len(document.body),
            content_type=document.content_type,
            etag=document.etag,
            last_modified=document.last_modified,
            canonical_url=document.final_url,
            http_status=document.status_code,
            reused_existing=reused,
        )

    async def exists(self, content_hash: str) -> bool:
        return self._path(storage_key_for_hash(content_hash)).exists()

    async def get_bytes(self, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()


class S3DocumentStorage:
    """S3-compatible object storage via boto3 (MinIO in local compose)."""

    def __init__(self, settings: Settings) -> None:
        import boto3
        from botocore.client import Config

        self._bucket = settings.object_storage_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
            config=Config(signature_version="s3v4"),
        )

    async def store_document(self, document: FetchedDocument) -> RawDocumentRef:
        # boto3 is sync; wrap usage is fine for worker processes.
        digest = document.content_hash or content_hash_bytes(document.body)
        key = storage_key_for_hash(digest)
        reused = await self.exists(digest)
        if not reused:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=document.body,
                ContentType=document.content_type or "application/octet-stream",
            )
        return RawDocumentRef(
            storage_key=key,
            content_hash=digest,
            byte_size=len(document.body),
            content_type=document.content_type,
            etag=document.etag,
            last_modified=document.last_modified,
            canonical_url=document.final_url,
            http_status=document.status_code,
            reused_existing=reused,
        )

    async def exists(self, content_hash: str) -> bool:
        key = storage_key_for_hash(content_hash)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    async def get_bytes(self, storage_key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=storage_key)
        return obj["Body"].read()  # type: ignore[no-any-return]


def build_document_storage(settings: Settings) -> DocumentStorage:
    backend = getattr(settings, "object_storage_backend", "local")
    if backend == "memory":
        return InMemoryDocumentStorage()
    if backend == "s3":
        return S3DocumentStorage(settings)
    root = getattr(settings, "object_storage_local_path", "./data/raw")
    return LocalFilesystemStorage(root)
