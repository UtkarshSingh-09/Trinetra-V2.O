from abc import ABC, abstractmethod


class StorageClient(ABC):
    @abstractmethod
    def create_application(self, applicant_data: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_application(self, app_id: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def get_ucso(self, app_id: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def patch_namespace(self, app_id: str, namespace: str, data: dict, idempotency_key: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def add_note(self, app_id: str, note: str, author: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def upload_file(self, app_id: str, file_bytes: bytes, filename: str, doc_type: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_file(self, app_id: str, filename: str | None = None) -> tuple[bytes, str] | None:
        raise NotImplementedError

    @abstractmethod
    def get_file_by_key(self, storage_path: str) -> tuple[bytes, str] | None:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, app_id: str, event: dict) -> None:
        raise NotImplementedError
