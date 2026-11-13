"""
Web search tools for Raven CLI Agent using DuckDuckGo search.
"""

from typing import List, Dict, Any
from urllib.parse import urlparse
import re
import requests

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0"
)
_DEFAULT_MAX_EXTRACT_CHARS = 15000
_MIN_EXTRACT_CHARS = 1000
_MAX_EXTRACT_CHARS = 50000
_PER_BACKEND_SEARCH_TIMEOUT = 6
_SEARCH_BACKENDS = ("yahoo", "startpage", "duckduckgo", "brave")


def _configure_ddgs_engines(ddgs: Any, timeout: int, backends: tuple[str, ...]) -> None:
    """
    Pre-configure DDGS text engines with a deterministic desktop browser profile.

    Avoids upstream ddgs/primp failure modes caused by random impersonation:
    - Mobile OS profiles ('android'/'ios') cause Yahoo to return mobile HTML
      without 'relsrch' nodes, yielding 0 extracted results.
    - Standard Chrome/Firefox/Safari profiles trigger Startpage's Anubis PoW
      challenge, whereas 'opera' on 'macos' returns search results directly.
    """
    engines_cache = getattr(ddgs, "_engines_cache", None)
    if not isinstance(engines_cache, dict):
        return

    try:
        import primp
        from ddgs.engines import ENGINES

        text_engines = ENGINES.get("text", {})
        proxy = getattr(ddgs, "_proxy", None)
        verify = getattr(ddgs, "_verify", True)
        for name in backends:
            engine_cls = text_engines.get(name)
            if engine_cls is None:
                continue
            engine = engine_cls(proxy=proxy, timeout=timeout, verify=verify)
            engine.http_client.client = primp.Client(
                proxy=proxy,
                timeout=timeout,
                impersonate="opera",
                impersonate_os="macos",
                verify=verify if isinstance(verify, bool) else True,
                ca_cert_file=verify if isinstance(verify, str) else None,
            )
            engine.http_client.client.headers_update(engine.headers_update)
            engines_cache[engine_cls] = engine
    except Exception:
        pass


def web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Performs a real-time web search using DuckDuckGo and returns top search results.

    Args:
        query (str): The search query string.
        max_results (int): Maximum number of results to return (1 to 10). Defaults to 5.

    Returns:
        List[Dict[str, Any]]: A list of search result dictionaries containing 'title', 'url', and 'snippet'.
    """
    if not query or not str(query).strip():
        return [{"error": "Search query cannot be empty."}]

    try:
        max_results = max(1, min(10, int(max_results)))
    except (ValueError, TypeError):
        max_results = 5

    if DDGS is None:
        return [{"error": "ddgs Python library is not installed. Please run 'pip install ddgs'."}]

    try:
        results = []
        seen_urls = set()
        cleaned_query = str(query).strip()
        backends = _SEARCH_BACKENDS
        timeout = _PER_BACKEND_SEARCH_TIMEOUT
        last_error = None

        with DDGS(timeout=timeout) as ddgs:
            _configure_ddgs_engines(ddgs, timeout=timeout, backends=backends)
            for backend in backends:
                try:
                    raw_results = ddgs.text(
                        cleaned_query,
                        max_results=max_results,
                        backend=backend,
                    )
                except Exception as backend_err:
                    last_error = backend_err
                    continue

                if raw_results:
                    for item in raw_results:
                        if not isinstance(item, dict):
                            continue
                        title = str(item.get("title", "") or "").strip()
                        url = str(item.get("href", item.get("link", "")) or "").strip()
                        snippet = str(item.get("body", item.get("snippet", "")) or "").strip()
                        if not url or (not title and not snippet):
                            continue
                        norm_url = url.rstrip("/")
                        if norm_url in seen_urls:
                            continue
                        seen_urls.add(norm_url)
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                        })
                        if len(results) >= max_results:
                            break
                    if results:
                        break

        if not results:
            if last_error is not None and "No results found" not in str(last_error):
                raise last_error
            return [{"message": f"No web search results found for query: '{query}'"}]

        return results
    except Exception as e:
        return [{"error": f"Failed to execute web search: {str(e)}"}]


def _truncate_extracted_content(content: str, max_chars: int) -> str:
    """Truncates extracted webpage content to protect the LLM context window."""
    if len(content) <= max_chars:
        return content
    omitted = len(content) - max_chars
    return (
        f"{content[:max_chars]}"
        f"\n\n... [Content truncated at {max_chars:,} characters "
        f"({omitted:,} characters omitted to protect context window)]"
    )


def _html_to_clean_text(raw_html: str) -> str:
    """Converts raw HTML into clean readable text using lxml or regex fallback."""
    if not raw_html or not raw_html.strip():
        return ""

    try:
        from lxml import html as lxml_html
        from lxml.etree import Comment

        doc = lxml_html.fromstring(raw_html)
        for bad in doc.xpath(
            "//script | //style | //noscript | //svg | //iframe | //nav | //footer | //header"
        ):
            parent = bad.getparent()
            if parent is not None:
                parent.remove(bad)
        for comment in doc.xpath("//comment()"):
            parent = comment.getparent()
            if parent is not None:
                parent.remove(comment)

        title_nodes = doc.xpath("//title/text()")
        title_str = title_nodes[0].strip() if title_nodes else ""
        text_content = doc.text_content()
        lines = [line.strip() for line in text_content.splitlines()]
        compact_lines = []
        blank_streak = 0
        for line in lines:
            if not line:
                blank_streak += 1
                if blank_streak <= 1:
                    compact_lines.append("")
            else:
                blank_streak = 0
                compact_lines.append(line)
        body = "\n".join(compact_lines).strip()
        if title_str and not body.startswith(title_str):
            return f"# {title_str}\n\n{body}".strip()
        return body
    except Exception:
        cleaned = re.sub(r"(?is)<(script|style|noscript|svg).*?>.*?</\1>", " ", raw_html)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def _extract_direct_html_text(url: str, timeout: int = 10) -> str:
    """Stage 2 fallback: fetches target URL directly and extracts readable text locally."""
    raw_html = ""
    status_code = None

    try:
        import primp

        client = primp.Client(
            timeout=timeout,
            impersonate="opera",
            impersonate_os="macos",
            verify=True,
        )
        resp = client.get(url)
        status_code = getattr(resp, "status_code", 200)
        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code}")
        raw_html = getattr(resp, "text", "") or ""
    except ImportError:
        resp = requests.get(
            url,
            headers={"User-Agent": _DEFAULT_USER_AGENT},
            timeout=timeout,
            verify=True,
        )
        resp.raise_for_status()
        raw_html = resp.text

    extracted = _html_to_clean_text(raw_html)
    if not extracted:
        raise RuntimeError("Direct HTML extraction yielded empty text.")
    return extracted


def extract_content_from_web_links(
    web_link: str,
    max_chars: int = _DEFAULT_MAX_EXTRACT_CHARS,
) -> str:
    """
    Extracts clean markdown/readable content from a web link with timeout,
    TLS verification, direct HTML fallback, and context-window truncation.

    Args:
        web_link (str): The HTTP/HTTPS URL from which content should be extracted.
        max_chars (int): Maximum characters to return (1000 to 50000). Defaults to 15000.

    Returns:
        str: Extracted content from the provided web link, or an Error message string.
    """
    if not web_link or not str(web_link).strip():
        return "Error: No web link provided."

    cleaned_url = str(web_link).strip()
    parsed = urlparse(cleaned_url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return (
            f"Error: Invalid URL '{cleaned_url}'. "
            "Only valid http:// and https:// URLs are supported."
        )

    try:
        max_chars = max(_MIN_EXTRACT_CHARS, min(_MAX_EXTRACT_CHARS, int(max_chars)))
    except (ValueError, TypeError):
        max_chars = _DEFAULT_MAX_EXTRACT_CHARS

    jina_error = None
    try:
        response = requests.get(
            f"https://r.jina.ai/{cleaned_url}",
            headers={
                "Accept": "text/plain",
                "User-Agent": _DEFAULT_USER_AGENT,
            },
            timeout=15,
            verify=True,
        )
        response.raise_for_status()
        text = (response.text or "").strip()
        lower_head = text[:300].lower()
        if (
            text
            and not lower_head.startswith('{"data":null')
            and "rate limit exceeded" not in lower_head
            and "securitycompromiseerror" not in lower_head
        ):
            return _truncate_extracted_content(text, max_chars)
        jina_error = "Jina Reader returned empty or rate-limited payload"
    except Exception as exc:
        jina_error = str(exc)

    # Stage 2 fallback: direct fetch + local HTML-to-text extraction
    try:
        direct_text = _extract_direct_html_text(cleaned_url, timeout=10)
        return _truncate_extracted_content(direct_text, max_chars)
    except Exception as fallback_exc:
        return (
            f"Error: Failed to extract content from '{cleaned_url}'. "
            f"Reader error: {jina_error}. Direct fallback error: {fallback_exc}"
        )