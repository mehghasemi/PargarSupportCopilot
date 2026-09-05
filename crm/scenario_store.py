"""Portable JSON storage for scenario definitions and application settings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SCENARIO_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "scenarios.json"
)


class ScenarioStore:
    """File-backed store for operational scenario configuration.

    The JSON file is portable: copy it with the application to transfer
    scenario definitions and settings to another local installation.
    """

    def __init__(self, path: str | Path = DEFAULT_SCENARIO_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _default(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "updated_at": None,
            "settings": {"storage": "json-file", "crm_write_operations": 0},
            "scenarios": [],
        }

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            payload = self._default()
            self.write(payload)
            return payload
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("فایل ذخیره‌سازی سناریوها قابل خواندن نیست.") from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("scenarios", []), list
        ):
            raise ValueError("ساختار فایل ذخیره‌سازی سناریوها معتبر نیست.")
        payload.setdefault("schema_version", 1)
        payload.setdefault("settings", self._default()["settings"])
        return payload

    def write(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict) or not isinstance(
            payload.get("scenarios"), list
        ):
            raise ValueError("فهرست سناریوها باید به‌صورت آرایه ارسال شود.")
        normalized = {
            "schema_version": int(payload.get("schema_version", 1)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "settings": payload.get("settings")
            if isinstance(payload.get("settings"), dict)
            else self._default()["settings"],
            "scenarios": payload["scenarios"],
        }
        for scenario in normalized["scenarios"]:
            if not isinstance(scenario, dict) or not scenario.get("id"):
                raise ValueError("هر سناریو باید شناسه معتبر داشته باشد.")
            if not isinstance(scenario.get("steps", []), list):
                raise ValueError("مراحل هر سناریو باید به‌صورت آرایه باشند.")
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return normalized
