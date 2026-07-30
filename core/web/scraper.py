import io
import re
from html.parser import HTMLParser
from typing import Optional

import httpx


def _extract_pdf_text(content: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text.strip() or None
    except Exception:
        return None


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


def _clean_text(text: str) -> str:
    lines = text.split("\n")
    seen: set[str] = set()
    clean: list[str] = []
    skip_prefixes = (
        "home", "about", "contact", "privacy", "terms", "cookie", "copyright",
        "all rights reserved", "follow us", "subscribe", "share", "tags", "categories",
        "related posts", "related articles", "related notes", "read more", "view all",
        "show more", "click here", "learn more", "powered by", "©", "facebook",
        "twitter", "instagram", "youtube", "linkedin", "whatsapp", "telegram",
    )

    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        lower = stripped.lower()
        if lower in seen:
            continue
        if re.match(r'^https?://\S+$', stripped):
            continue
        if any(lower.startswith(p) for p in skip_prefixes):
            continue
        seen.add(lower)
        clean.append(stripped)
    return "\n".join(clean)


_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Not/A)Brand";v="99", "Google Chrome";v="125", "Chromium";v="125"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
}


_CHALLENGE_KEYWORDS = [
    "cf-browser-venue", "cf-challenge", "__cf_chl", "challenge-platform",
    "Client Challenge", "Checking your browser", "DDoS protection",
    "Attention Required", "just a moment",
]


def _looks_like_challenge_page(title: str, html: str) -> bool:
    if len(html) > 50000:
        return False
    title_lower = title.lower()
    if "challenge" in title_lower or "just a moment" in title_lower:
        return True
    html_lower = html.lower()
    for kw in _CHALLENGE_KEYWORDS:
        if kw.lower() in html_lower:
            return True
    if html.count("<script") > 10 and len(html) < 10000 and "<noscript>" in html_lower:
        return True
    return False


def fetch_url(url: str, timeout: int = 30) -> Optional[dict]:
    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=timeout,
            headers=_DEFAULT_HEADERS,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            text = _extract_pdf_text(resp.content)
            if text:
                return {
                    "title": url.split("/")[-1].replace(".pdf", "").replace("-", " ").replace("_", " ").title(),
                    "content": text,
                    "url": url,
                    "html": "",
                }
            return {"error": "Could not extract text from PDF."}

        html = resp.text

        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()

        if _looks_like_challenge_page(title, html):
            return {
                "error": "This site is protected by Cloudflare or bot challenge. "
                         "Try a different URL — educational sites like Wikipedia, NCERT, "
                         "Khan Academy, and Byju's usually work."
            }

        text = extract_text(html)
        if text:
            text = _clean_text(text)
        if not text:
            return {"error": "No readable content found — the page may require JavaScript."}
        return {
            "title": title or url,
            "content": text,
            "url": url,
            "html": html[:50000],
        }
    except httpx.HTTPError:
        return None