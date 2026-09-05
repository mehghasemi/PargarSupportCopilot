"""Read-only Dynamics CRM REST client using the current Windows account."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

try:
    from requests_negotiate_sspi import HttpNegotiateAuth
except ImportError:  # pragma: no cover
    HttpNegotiateAuth = None


class CrmError(RuntimeError):
    """Safe, user-facing CRM integration error."""


@dataclass(frozen=True)
class CrmConfig:
    base_url: str = "https://crm.baridsoft.ir/Main/api/data/v9.0"
    timeout_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "CrmConfig":
        return cls(
            base_url=os.getenv(
                "PARGAR_CRM_BASE_URL",
                "https://crm.baridsoft.ir/Main/api/data/v9.0",
            ).rstrip("/"),
            timeout_seconds=int(os.getenv("PARGAR_CRM_TIMEOUT", "30")),
        )


class CrmClient:
    """Minimal GET-only client for Case, Note, Task and Knowledge Base."""

    ENTITY_SETS = {
        "case": "incidents",
        "note": "annotations",
        "task": "tasks",
        "knowledge_base": "knowledgearticles",
    }

    def __init__(self, config: CrmConfig | None = None):
        if HttpNegotiateAuth is None:
            raise CrmError(
                "کتابخانه requests-negotiate-sspi نصب نیست؛ "
                "ابتدا requirements.txt را نصب کنید."
            )
        self.config = config or CrmConfig.from_environment()
        self.session = requests.Session()
        self.session.auth = HttpNegotiateAuth()
        self.session.headers.update({
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Prefer": 'odata.include-annotations="OData.Community.Display.V1.FormattedValue"',
        })

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        try:
            response = self.session.get(
                self.config.base_url + path,
                params=params,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CrmError(f"ارتباط با CRM برقرار نشد: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text[:500].strip()
            raise CrmError(
                f"CRM پاسخ {response.status_code} برگرداند."
                + (f" جزئیات: {detail}" if detail else "")
            )
        try:
            return response.json()
        except ValueError as exc:
            raise CrmError("پاسخ CRM JSON معتبر نیست.") from exc

    def who_am_i(self) -> dict[str, Any]:
        return self._get("/WhoAmI")

    def list_records(
        self,
        entity: str,
        *,
        select: list[str] | None = None,
        filter_expression: str | None = None,
        top: int = 50,
        order_by: str | None = None,
    ) -> dict[str, Any]:
        try:
            entity_set = self.ENTITY_SETS[entity]
        except KeyError as exc:
            raise CrmError(f"Entity مجاز نیست: {entity}") from exc
        params: dict[str, Any] = {"$top": min(max(int(top), 1), 500)}
        if select:
            params["$select"] = ",".join(select)
        if filter_expression:
            params["$filter"] = filter_expression
        if order_by:
            params["$orderby"] = order_by
        return self._get("/" + entity_set, params=params)

    def list_cases(self, *, filter_expression: str | None = None, top: int = 50):
        return self.list_records(
            "case",
            select=[
                "incidentid", "ticketnumber", "title", "description",
                "createdon", "modifiedon", "statecode", "statuscode",
                "casetypecode", "brd_productcategory", "brd_incidenttype",
            ],
            filter_expression=filter_expression,
            top=top,
            order_by="createdon desc",
        )

    def list_notes(self, *, top: int = 50):
        return self.list_records(
            "note",
            select=["annotationid", "subject", "notetext", "createdon", "modifiedon"],
            top=top,
            order_by="createdon desc",
        )

    def list_case_notes(self, case_id: str, *, top: int = 100):
        return self.list_records(
            "note",
            select=[
                "annotationid", "subject", "notetext", "createdon", "modifiedon",
                "_objectid_value",
            ],
            filter_expression=f"_objectid_value eq {case_id}",
            top=top,
            order_by="createdon desc",
        )

    def list_tasks(self, *, top: int = 50):
        return self.list_records(
            "task",
            select=["activityid", "subject", "description", "createdon", "modifiedon"],
            top=top,
            order_by="createdon desc",
        )

    def list_case_tasks(self, case_id: str, *, top: int = 100):
        return self.list_records(
            "task",
            select=[
                "activityid", "subject", "description", "createdon", "modifiedon",
                "_regardingobjectid_value",
            ],
            filter_expression=f"_regardingobjectid_value eq {case_id}",
            top=top,
            order_by="createdon desc",
        )

    def list_case_posts(self, case_id: str, *, top: int = 100):
        return self._get(
            "/posts",
            params={
                "$select": (
                    "postid,text,createdon,modifiedon,source,type,"
                    "_regardingobjectid_value,_createdby_value,_modifiedby_value"
                ),
                "$filter": f"_regardingobjectid_value eq {case_id}",
                "$top": min(max(int(top), 1), 500),
                "$orderby": "createdon desc",
            },
        )

    def list_knowledge_articles(self, *, top: int = 50):
        return self.list_records(
            "knowledge_base",
            select=[
                "knowledgearticleid", "title", "articlepublicnumber",
                "statecode", "statuscode", "content", "modifiedon",
            ],
            top=top,
            order_by="modifiedon desc",
        )

    def list_views(self, *, entity_logical_name: str | None = None, top: int = 100):
        params: dict[str, Any] = {
            "$select": "savedqueryid,name,returnedtypecode,fetchxml,isdefault",
            "$top": min(max(int(top), 1), 500),
            "$orderby": "name asc",
        }
        if entity_logical_name:
            safe = entity_logical_name.replace("'", "''")
            params["$filter"] = f"returnedtypecode eq '{safe}'"
        return self._get("/savedqueries", params=params)

    def list_personal_views(
        self, *, entity_logical_name: str | None = None, top: int = 100
    ):
        params: dict[str, Any] = {
            "$select": "userqueryid,name,returnedtypecode,fetchxml",
            "$top": min(max(int(top), 1), 500),
            "$orderby": "name asc",
        }
        if entity_logical_name:
            safe = entity_logical_name.replace("'", "''")
            params["$filter"] = f"returnedtypecode eq '{safe}'"
        return self._get("/userqueries", params=params)

    def list_all_case_views(self, *, top: int = 500) -> list[dict[str, Any]]:
        system = self.list_views(entity_logical_name="incident", top=top).get("value", [])
        personal = self.list_personal_views(
            entity_logical_name="incident", top=top
        ).get("value", [])
        return [
            {
                "id": row.get("savedqueryid"),
                "name": row.get("name"),
                "is_default": row.get("isdefault", False),
                "view_type": "system",
                "fetchxml": row.get("fetchxml"),
            }
            for row in system
        ] + [
            {
                "id": row.get("userqueryid"),
                "name": row.get("name"),
                "is_default": False,
                "view_type": "personal",
                "fetchxml": row.get("fetchxml"),
            }
            for row in personal
        ]

    def load_view_cases(self, view_id: str, *, top: int = 100, view_type: str = "system"):
        """Execute a saved Case view through its FetchXML using GET only."""
        if not view_id or any(ch in view_id for ch in "'?$"):
            raise CrmError("شناسه View معتبر نیست.")
        entity = "userqueries" if view_type == "personal" else "savedqueries"
        select = (
            "userqueryid,name,returnedtypecode,fetchxml"
            if view_type == "personal"
            else "savedqueryid,name,returnedtypecode,fetchxml,isdefault"
        )
        payload = self._get(
            f"/{entity}({quote(view_id, safe='-')})",
            params={"$select": select},
        )
        if payload.get("returnedtypecode") != "incident":
            raise CrmError("View انتخاب‌شده مربوط به Case نیست.")
        fetch_xml = payload.get("fetchxml")
        if not fetch_xml:
            raise CrmError("View انتخاب‌شده FetchXML قابل اجرا ندارد.")
        return payload, self._get(
            "/incidents",
            params={
                "fetchXml": fetch_xml,
                "$top": min(max(int(top), 1), 500),
            },
        )

    def get_case_context(self, case_id: str):
        if not case_id or any(ch in case_id for ch in "'?$"):
            raise CrmError("شناسه Case معتبر نیست.")
        return self._get(
            f"/incidents({quote(case_id, safe='-')})",
            params={
                "$select": (
                    "incidentid,ticketnumber,title,description,createdon,"
                    "modifiedon,statecode,statuscode"
                ),
            },
        )
