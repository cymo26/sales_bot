"""Raw Livespace CRM REST client.

Sole owner of Livespace-specific endpoint paths, auth mechanics, and field
names. Everything outside this file deals with the normalized dataclasses
below (LivespaceContactMatch, LivespaceDeal) or a LivespaceError — never raw
Livespace JSON — so if a field name turns out to be wrong, or Livespace
changes its API, only this file needs to change.

Verified against the real Livespace Postman collection the user supplied
(Livespace_API_Docs.json) — the hosted docs at api-docs.livespace.io are an
unfetchable JS-rendered SPA, so this collection's real, working example
requests/responses are the source of truth here, not guesses.

Auth is a signed-session flow, not a static header:
  1. POST /_Api/auth_call/_api_method/getToken (form-encoded body:
     _api_auth=key&_api_key=<API_KEY>) -> {"data": {"token", "session_id"}}
  2. api_sha = SHA1(API_KEY + token + API_SECRET)
  3. Every entity call embeds _api_auth/_api_key/_api_sha/_api_session
     directly in its JSON request body (not headers, not query params).

Every HTTP response is 200 — the real outcome lives in the JSON body's
`status`/`result` fields ({"data", "error", "result": <code>, "status": bool}).
There is no Retry-After/429 anywhere in this API; retries below react to
`result` codes and network failures instead.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

# 560-564: auth-specific errors (bad/expired token or session) -> refetch the
# session once and retry. 500/520: general/DB error, presumably transient ->
# retry with backoff. Everything else (400/420/550, or an unrecognized code)
# is a shape/validation problem retrying can't fix.
_AUTH_ERROR_CODES = {560, 561, 562, 563, 564}
_RETRYABLE_ERROR_CODES = {500, 520}
_MAX_ATTEMPTS = 3


class LivespaceError(Exception):
    """Any Livespace call that didn't end in a usable result — network
    failure, exhausted retries, or an error envelope. Callers never see a
    raw httpx exception or the API's {status: false} shape directly."""


@dataclass
class LivespaceSession:
    token: str
    session_id: str
    sha: str


@dataclass
class LivespaceContactMatch:
    contact_id: str
    company_id: str | None
    owner_name: str | None
    owner_email: str | None


@dataclass
class LivespaceDeal:
    deal_id: str
    name: str
    status: str
    owner_name: str | None


def _sign(api_key: str, token: str, api_secret: str) -> str:
    return hashlib.sha1(f"{api_key}{token}{api_secret}".encode()).hexdigest()


async def get_session(client: httpx.AsyncClient, settings: Settings) -> LivespaceSession:
    """Fetches a fresh token + session_id. Livespace's own docs say these
    "need to be fetched each time before sending a request" — we fetch once
    per logical sync operation (one lead check, or once per sweep batch) and
    reuse it across every call in that operation, rather than literally
    per-call, to avoid doubling request volume for no benefit."""
    url = f"{settings.livespace_base_url}/_Api/auth_call/_api_method/getToken"
    try:
        resp = await client.post(
            url,
            data={"_api_auth": "key", "_api_key": settings.livespace_api_key},
            timeout=settings.livespace_timeout_seconds,
        )
        body = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise LivespaceError(f"auth request failed: {e}") from e

    if not body.get("status") or "data" not in body:
        raise LivespaceError(f"auth failed: result={body.get('result')} error={body.get('error')}")

    token = body["data"]["token"]
    session_id = body["data"]["session_id"]
    sha = _sign(settings.livespace_api_key, token, settings.livespace_api_secret)
    return LivespaceSession(token=token, session_id=session_id, sha=sha)


def _auth_body(settings: Settings, session: LivespaceSession) -> dict:
    return {
        "_api_auth": "key",
        "_api_key": settings.livespace_api_key,
        "_api_sha": session.sha,
        "_api_session": session.session_id,
    }


async def _call(
    client: httpx.AsyncClient,
    settings: Settings,
    session: LivespaceSession,
    method: str,
    path: str,
    params: dict,
    *,
    _retried_auth: bool = False,
) -> dict:
    """Calls `path` with `params` merged onto the auth fields. Retries on
    network failures and transient (500/520) result codes with exponential
    backoff; on an auth-error result code, refetches the session once and
    retries the same call before giving up. Returns the parsed response
    body's "data" payload on success; raises LivespaceError otherwise."""
    url = f"{settings.livespace_base_url}{path}"
    body = {**_auth_body(settings, session), **params}

    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.request(method, url, json=body, timeout=settings.livespace_timeout_seconds)
            parsed = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            last_error = e
        else:
            if parsed.get("status"):
                return parsed.get("data") or {}

            result_code = parsed.get("result")
            if result_code in _AUTH_ERROR_CODES and not _retried_auth:
                fresh = await get_session(client, settings)
                return await _call(client, settings, fresh, method, path, params, _retried_auth=True)
            if result_code not in _RETRYABLE_ERROR_CODES:
                raise LivespaceError(f"{path} failed: result={result_code} error={parsed.get('error')}")
            last_error = LivespaceError(f"{path} transient error: result={result_code}")

        if attempt < _MAX_ATTEMPTS - 1:
            await asyncio.sleep((2**attempt) + random.uniform(0, 0.5))

    raise LivespaceError(f"{path} failed after {_MAX_ATTEMPTS} attempts: {last_error}")


async def find_contact_by_email(
    client: httpx.AsyncClient, settings: Settings, session: LivespaceSession, email: str
) -> LivespaceContactMatch | None:
    data = await _call(
        client, settings, session, "GET", "/Contact/getAll",
        {"type": "contact", "emails": email, "limit": 1},
    )
    contacts = data.get("contact") or []
    if not contacts:
        return None
    c = contacts[0]
    return LivespaceContactMatch(
        contact_id=c["id"],
        company_id=c.get("company_id"),
        owner_name=c.get("owner_name"),
        owner_email=c.get("owner_email"),
    )


async def find_active_deal(
    client: httpx.AsyncClient,
    settings: Settings,
    session: LivespaceSession,
    contact_id: str,
    company_id: str | None = None,
) -> LivespaceDeal | None:
    params: dict = {"contacts": contact_id, "status": "open", "limit": 1}
    if company_id:
        params["comapnies"] = company_id  # sic — real (misspelled) Livespace param name, not ours
    data = await _call(client, settings, session, "GET", "/Deal/getAll", params)
    # Defensive: filter to status == "open" explicitly rather than trusting
    # the server-side filter alone (section A: "open" is the sole definition
    # of active, everything else — including statuses we haven't seen — is
    # treated as not active).
    open_deals = [d for d in (data.get("deal") or []) if d.get("status") == "open"]
    if not open_deals:
        return None
    d = open_deals[0]
    return LivespaceDeal(deal_id=d["id"], name=d["name"], status=d["status"], owner_name=d.get("owner_name"))
