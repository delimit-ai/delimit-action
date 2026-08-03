#!/usr/bin/env python3
"""README link checker (LED-4159).

Origin: the Marketplace README's flagship attestation link 404'd unnoticed
(fixed in PR #44). This script catches the class: every http(s) URL in
README.md must resolve, or CI says so.

Design constraints:
- stdlib only (urllib) — no new dependencies.
- Extracts URLs from markdown links/images, HTML src/href attributes, and
  bare URLs — but ONLY outside fenced code blocks and inline code spans,
  because the README's YAML/JSON examples contain placeholder URLs
  (e.g. https://github.com/org/repo/pull/123) that are not real links.
- HEAD first, GET fallback (some hosts reject or mis-handle HEAD),
  15s timeout, browser-ish User-Agent, one retry per URL.
- 2xx/3xx = OK (urllib follows redirects; a followed redirect landing on
  2xx is OK; a raw 3xx we could not follow still counts as alive).
- Inline allowlist for known-flaky hosts:
      <!-- linkcheck-allow: example.com -->
  Allowlisted failures WARN but never fail the run.

Exit codes: 0 = all links OK (or only allowlisted warnings), 1 = at least
one non-allowlisted URL is 4xx/5xx/network-dead.
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

TIMEOUT_SECONDS = 15
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "delimit-readme-linkcheck/1.0 (+https://github.com/delimit-ai/delimit-action)"
)

ALLOWLIST_RE = re.compile(r"<!--\s*linkcheck-allow:\s*([^\s>]+)\s*-->")
FENCED_CODE_RE = re.compile(r"^(```|~~~).*?^\1\s*$", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MD_LINK_RE = re.compile(r"\]\(\s*<?(https?://[^)\s>]+)>?\s*(?:\"[^\"]*\")?\s*\)")
HTML_ATTR_RE = re.compile(r"(?:src|href)\s*=\s*[\"'](https?://[^\"']+)[\"']", re.IGNORECASE)
BARE_URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]`]+")

TRAILING_PUNCTUATION = ".,;:!?"


def parse_allowlist(text: str) -> set[str]:
    """Collect allowlisted hosts from <!-- linkcheck-allow: host --> comments."""
    return {m.group(1).lower().lstrip(".") for m in ALLOWLIST_RE.finditer(text)}


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans (their URLs are examples)."""
    text = FENCED_CODE_RE.sub("", text)
    return INLINE_CODE_RE.sub("", text)


def clean_url(url: str) -> str:
    return url.rstrip(TRAILING_PUNCTUATION)


def extract_urls(text: str) -> list[str]:
    """Extract every checkable http(s) URL, deduplicated, in first-seen order."""
    stripped = strip_code(text)
    seen: dict[str, None] = {}
    for regex in (MD_LINK_RE, HTML_ATTR_RE, BARE_URL_RE):
        for match in regex.finditer(stripped):
            url = clean_url(match.group(1) if regex is not BARE_URL_RE else match.group(0))
            if url and url not in seen:
                seen[url] = None
    return list(seen)


def _request(url: str, method: str) -> tuple[int, str]:
    """Issue one request; return (status_code, detail). Raises on network errors."""
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
            return resp.status, f"{method} {resp.status}"
    except urllib.error.HTTPError as exc:
        # HTTPError carries a real status code (urllib already followed 3xx).
        return exc.code, f"{method} {exc.code}"


def check_url(url: str) -> tuple[bool, str]:
    """HEAD-then-GET-fallback with one retry. Returns (ok, detail)."""
    last_detail = "no attempt"
    for attempt in (1, 2):
        for method in ("HEAD", "GET"):
            try:
                status, detail = _request(url, method)
            except Exception as exc:  # URLError, timeout, ssl, socket, ...
                last_detail = f"{method} error: {type(exc).__name__}: {exc}"
                continue
            last_detail = detail
            if 200 <= status < 400:
                return True, detail
            # 4xx/5xx on HEAD: some hosts reject HEAD — fall through to GET.
        # Both methods failed this attempt; back off briefly, then retry once
        # (avoids tripping rate limiters like GitHub's 429 on the retry).
        if attempt == 1:
            time.sleep(2)
    return False, last_detail


def main(argv: list[str]) -> int:
    readme = Path(argv[1]) if len(argv) > 1 else Path("README.md")
    if not readme.is_file():
        print(f"error: {readme} not found", file=sys.stderr)
        return 1

    text = readme.read_text(encoding="utf-8")
    allowlist = parse_allowlist(text)
    urls = extract_urls(text)

    if allowlist:
        print(f"Allowlisted hosts (failures warn, never fail): {', '.join(sorted(allowlist))}")
    print(f"Checking {len(urls)} unique URL(s) from {readme}\n")

    failures: list[str] = []
    warnings: list[str] = []
    rows: list[tuple[str, str, str]] = []

    for url in urls:
        ok, detail = check_url(url)
        host = (urlsplit(url).hostname or "").lower()
        allowlisted = any(host == h or host.endswith("." + h) for h in allowlist)
        if ok:
            verdict = "OK"
        elif allowlisted:
            verdict = "WARN (allowlisted)"
            warnings.append(url)
        else:
            verdict = "FAIL"
            failures.append(url)
        rows.append((verdict, detail, url))
        print(f"  [{verdict:>17}] {detail:<28} {url}")

    print("\n| Result | Detail | URL |")
    print("|--------|--------|-----|")
    for verdict, detail, url in rows:
        print(f"| {verdict} | {detail} | {url} |")

    print(f"\nSummary: {len(urls) - len(failures) - len(warnings)} ok, "
          f"{len(warnings)} allowlisted warning(s), {len(failures)} failure(s)")
    if warnings:
        print("Allowlisted (non-fatal) failures:")
        for url in warnings:
            print(f"  - {url}")
    if failures:
        print("Dead links (fix these or allowlist the host):", file=sys.stderr)
        for url in failures:
            print(f"  - {url}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
