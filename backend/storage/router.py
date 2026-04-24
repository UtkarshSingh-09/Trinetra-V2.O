from storage.base import StorageClient
from storage.actian_adapter import ActianStorageAdapter


def get_storage_client() -> StorageClient:
    return ActianStorageAdapter()
