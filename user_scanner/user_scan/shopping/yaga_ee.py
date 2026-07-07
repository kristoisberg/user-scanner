import html
import json
import re
from urllib.parse import quote

from user_scanner.core.helpers import get_random_user_agent
from user_scanner.core.orchestrator import generic_validate
from user_scanner.core.result import Result


def validate_yaga_ee(user: str) -> Result:
    user = user.strip().lower()
    url = f"https://www.yaga.ee/{quote(user, safe='')}"

    if not user:
        return Result.error("Username cannot be empty", url=url)

    if re.search(r"[/#?\x00-\x1f\x7f]", user):
        return Result.error("Username contains unsafe URL path characters", url=url)

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def process(response):
        if response.status_code != 200:
            return Result.error(
                f"Unexpected response status: {response.status_code}",
            )

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            response.text,
            re.DOTALL,
        )
        if not match:
            return Result.error("Could not find Next.js data")

        try:
            data = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError:
            return Result.error("Could not parse Next.js data")

        page_props = data.get("props", {}).get("pageProps", {})
        shop = page_props.get("initialShop")

        if shop is None:
            return Result.available()

        if not isinstance(shop, dict):
            return Result.error("Unexpected shop data")

        if shop.get("activeSlug") != user:
            return Result.error("Unexpected shop slug")

        owner = shop.get("owner") or {}
        extra = {}
        if shop.get("id"):
            extra["id"] = shop.get("id")
        if shop.get("name"):
            extra["name"] = shop.get("name")
        if shop.get("description"):
            extra["description"] = shop.get("description")
        if owner.get("firstName") or owner.get("first_name"):
            extra["owner_first_name"] = owner.get("firstName") or owner.get("first_name")
        if owner.get("lastName") or owner.get("last_name"):
            extra["owner_last_name"] = owner.get("lastName") or owner.get("last_name")

        return Result.taken(extra=extra)

    return generic_validate(
        url,
        process,
        headers=headers,
        show_url=url,
        follow_redirects=True,
    )
