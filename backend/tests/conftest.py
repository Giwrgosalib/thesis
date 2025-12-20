import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest


class _FakeAdmin:
    def command(self, name: str) -> Dict[str, Any]:
        # Simulate a healthy Mongo server response
        return {"ok": 1, "operation": name}


class _FakeCollection:
    def __init__(self) -> None:
        self._documents = []

    def count_documents(self, _filter: Dict[str, Any]) -> int:  # pragma: no cover - simple shim
        return len(self._documents)

    def find(self, *_args: Any, **_kwargs: Any):
        return iter(self._documents)

    def find_one(self, *_args: Any, **_kwargs: Any):
        return self._documents[0] if self._documents else None

    def update_many(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:  # pragma: no cover - shim
        return SimpleNamespace(modified_count=0)

    def update_one(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:  # pragma: no cover - shim
        return SimpleNamespace(modified_count=1)

    def delete_many(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:  # pragma: no cover - shim
        self._documents = []
        return SimpleNamespace(deleted_count=0)


class _FakeDatabase:
    def __init__(self) -> None:
        self._collections: Dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


class _FakeMongoClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.admin = _FakeAdmin()
        self._db = _FakeDatabase()

    def __getitem__(self, name: str) -> _FakeDatabase:
        return self._db


# Function scope to avoid cross-test state and keep monkeypatch happy.
@pytest.fixture()
def patched_backend(monkeypatch, tmp_path_factory):
    """
    Load the classic backend with a fake Mongo client and safe environment defaults.
    """
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/fake")
    monkeypatch.setenv("EBAY_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "dummy-secret")
    monkeypatch.setenv("EBAY_DEV_ID", "dummy-dev")
    monkeypatch.setenv("EBAY_RUNAME", "dummy-runame")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:5000")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("FRONTEND_BUILD_DIR", str(tmp_path_factory.mktemp("frontend_dist")))

    # Ensure the import uses the fake Mongo client instead of making a real network call.
    monkeypatch.setattr("pymongo.MongoClient", _FakeMongoClient)

    # Drop cached module to force a clean import with patches.
    sys.modules.pop("backend.app", None)
    app_module = importlib.import_module("backend.app")

    return app_module


@pytest.fixture()
def client(patched_backend):
    return patched_backend.app.test_client()
