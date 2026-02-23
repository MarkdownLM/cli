"""Thin HTTP client for the markdownlm API.

All requests are scoped to the authenticated user — the server enforces
that each user can only read/write their own knowledge base.
"""

import sys
from typing import Any, Dict, List, Optional

import requests

from mdlm.config import get_api_key, get_api_url

# Timeout for all requests (connect, read) in seconds
_TIMEOUT = (10, 30)

VALID_CATEGORIES = {
    "architecture",
    "stack",
    "testing",
    "deployment",
    "security",
    "style",
    "dependencies",
    "error_handling",
    "business_logic",
    "general",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}")


class ApiClient:
    def __init__(self) -> None:
        self._api_key = get_api_key()
        self._base_url = get_api_url()
        self._session = requests.Session()
        # Never log the Authorization header
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _handle_response(self, resp: requests.Response) -> Dict[str, Any]:
        if resp.status_code == 401:
            print(
                "Error: Authentication failed. "
                "Check your API key with `mdlm configure`.",
                file=sys.stderr,
            )
            sys.exit(1)
        if resp.status_code == 403:
            print(
                "Error: Access denied. Your API key does not have permission.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not resp.ok:
            try:
                detail = resp.json().get("error", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise ApiError(resp.status_code, detail)
        return resp.json()

    def list_docs(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {}
        if category:
            params["category"] = category
        resp = self._session.get(
            self._url("/api/knowledge"), params=params, timeout=_TIMEOUT
        )
        data = self._handle_response(resp)
        return data.get("docs", [])

    def get_doc(self, doc_id: str) -> Dict[str, Any]:
        resp = self._session.get(
            self._url(f"/api/knowledge/{doc_id}"), timeout=_TIMEOUT
        )
        data = self._handle_response(resp)
        return data.get("doc", data)

    def create_doc(
        self, title: str, content: str, category: str
    ) -> Dict[str, Any]:
        payload = {"title": title, "content": content, "category": category}
        resp = self._session.post(
            self._url("/api/knowledge"), json=payload, timeout=_TIMEOUT
        )
        data = self._handle_response(resp)
        return data.get("doc", data)

    def update_doc(
        self,
        doc_id: str,
        title: str,
        content: str,
        category: str,
        change_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "title": title,
            "content": content,
            "category": category,
        }
        if change_reason:
            payload["change_reason"] = change_reason
        resp = self._session.put(
            self._url(f"/api/knowledge/{doc_id}"), json=payload, timeout=_TIMEOUT
        )
        data = self._handle_response(resp)
        return data.get("doc", data)

    def delete_doc(self, doc_id: str) -> None:
        resp = self._session.delete(
            self._url(f"/api/knowledge/{doc_id}"), timeout=_TIMEOUT
        )
        self._handle_response(resp)
