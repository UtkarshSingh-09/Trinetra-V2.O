from storage.base import StorageClient
from storage.postgres_adapter import PostgresStorageAdapter


def get_storage_client() -> StorageClient:
    return PostgresStorageAdapter()

