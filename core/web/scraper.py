from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

import httpx


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text_parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            stripped = data.strip()
            if stripped:
                self._text_parts.append(stripped)

    @property
    def text(self) -> str:
        return "\n".join(self._text_parts)


def extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text


_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_url(url: str, timeout: int = 30) -> Optional[dict]:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=timeout, headers=_DEFAULT_HEADERS)
        resp.raise_for_status()
        html = resp.text
        title = ""
        for line in html.splitlines():
            if "<title" in line.lower():
                import re
                m = re.search(r"<title[^>]*>(.*?)</title>", line, re.IGNORECASE | re.DOTALL)
                if m:
                    title = m.group(1).strip()
                    break
        text = extract_text(html)
        return {
            "title": title,
            "content": text,
            "url": url,
            "html": html[:50000],
        }
    except httpx.HTTPError:
        return None
