"""
Minimal client for the QuantConnect Cloud REST API v2.

Docs: https://www.quantconnect.com/docs/v2/cloud-platform/api-reference

Auth: requires QUANTCONNECT_USER_ID and QUANTCONNECT_API_TOKEN env vars
(get these from quantconnect.com -> My Account -> Security -> "Request Email
With Token"). Every request is signed with a fresh HMAC-style hash of the
token + current unix timestamp; the raw token itself is never sent.
"""
import base64
import hashlib
import os
import time
import typing

import requests

BASE_URL = "https://www.quantconnect.com/api/v2"


def _auth_headers() -> dict:
    user_id = os.environ["QUANTCONNECT_USER_ID"]
    api_token = os.environ["QUANTCONNECT_API_TOKEN"]

    timestamp = str(int(time.time()))
    hashed_token = hashlib.sha256(f"{api_token}:{timestamp}".encode("utf-8")).hexdigest()
    authentication = base64.b64encode(f"{user_id}:{hashed_token}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {authentication}",
        "Timestamp": timestamp,
    }


def _post(endpoint: str, payload: typing.Optional[dict] = None) -> dict:
    response = requests.post(
        f"{BASE_URL}/{endpoint}",
        headers=_auth_headers(),
        json=payload or {},
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success", False):
        raise RuntimeError(f"QuantConnect API error on {endpoint}: {body}")
    return body


def create_project(name: str, language: str = "C#") -> dict:
    return _post("projects/create", {"name": name, "language": language})


def read_project(project_id: int) -> dict:
    return _post("projects/read", {"projectId": project_id})


def create_file(project_id: int, name: str, content: str) -> dict:
    return _post("files/create", {"projectId": project_id, "name": name, "content": content})


def update_file(project_id: int, name: str, content: str) -> dict:
    return _post("files/update", {"projectId": project_id, "name": name, "content": content})


def delete_file(project_id: int, name: str) -> dict:
    return _post("files/delete", {"projectId": project_id, "name": name})


def create_compile(project_id: int) -> dict:
    return _post("compile/create", {"projectId": project_id})


def read_compile(project_id: int, compile_id: str) -> dict:
    return _post("compile/read", {"projectId": project_id, "compileId": compile_id})


def create_backtest(project_id: int, compile_id: str, backtest_name: str) -> dict:
    return _post("backtests/create", {
        "projectId": project_id,
        "compileId": compile_id,
        "backtestName": backtest_name,
    })


def read_backtest(project_id: int, backtest_id: str) -> dict:
    return _post("backtests/read", {"projectId": project_id, "backtestId": backtest_id})


def wait_for_compile(project_id: int, compile_id: str, timeout_seconds: int = 120, poll_seconds: int = 3) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = read_compile(project_id, compile_id)
        if result["state"] != "InQueue":
            return result
        time.sleep(poll_seconds)
    raise TimeoutError(f"Compile {compile_id} did not finish within {timeout_seconds}s")


def wait_for_backtest(project_id: int, backtest_id: str, timeout_seconds: int = 600, poll_seconds: int = 5) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = read_backtest(project_id, backtest_id)
        backtest = result["backtest"]
        if backtest.get("completed"):
            return backtest
        time.sleep(poll_seconds)
    raise TimeoutError(f"Backtest {backtest_id} did not finish within {timeout_seconds}s")
