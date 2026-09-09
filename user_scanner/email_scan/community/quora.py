import re

from curl_cffi.requests.exceptions import RequestException

from user_scanner.core.impersonate import impersonate_request_async
from user_scanner.core.result import Result

SHOW_URL = "https://www.quora.com"
QUERY_NAME = "LoginForm_loginInfoPreview_Query"
QUERY_HASH = "a2ba48cb37060d1ccfdc5790bfac3839536897e4f19488cb20db676e1817d37e"


async def validate_quora(email: str) -> Result:
    """Quiet login-preview probe. It uses no credentials and sends no email."""
    try:
        page = await impersonate_request_async(SHOW_URL, allow_redirects=True)
        formkey = re.search(r'"formkey":\s*"([a-f0-9]+)"', page.text)
        if page.status_code != 200 or not formkey:
            return Result.error(
                f"Could not load Quora login page: {page.status_code}",
                url=SHOW_URL,
            )

        response = await impersonate_request_async(
            f"{SHOW_URL}/graphql/gql_para_POST",
            "POST",
            params={"q": QUERY_NAME},
            headers={"quora-formkey": formkey.group(1)},
            json={
                "queryName": QUERY_NAME,
                "variables": {"email": email},
                "extensions": {"hash": QUERY_HASH},
            },
        )
        if response.status_code != 200:
            return Result.error(
                f"Unexpected Quora response: {response.status_code}",
                url=SHOW_URL,
            )

        preview = (response.json().get("data") or {}).get("loginInfoPreview")
        if not isinstance(preview, dict):
            return Result.error("Unexpected Quora response body", url=SHOW_URL)

        success = preview.get("success")
        error_type = preview.get("errorType")
        if success is True and error_type is None:
            return Result.taken(url=SHOW_URL, extra={"email_confirmed": True})
        if success is False and error_type == "email_not_found":
            return Result.available(url=SHOW_URL)
        if success is False and error_type == "email_unconfirmed":
            return Result.taken(url=SHOW_URL, extra={"email_confirmed": False})
        return Result.error(
            f"Unexpected Quora login state: {error_type}", url=SHOW_URL
        )
    except (RequestException, ValueError, AttributeError) as exc:
        return Result.error(exc, url=SHOW_URL)
