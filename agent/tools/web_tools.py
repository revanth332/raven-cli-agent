"""
Web search tools for Raven CLI Agent using DuckDuckGo search.
"""

from typing import List, Dict, Any
import requests

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


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
        cleaned_query = query.strip()
        backends = ("yahoo", "startpage", "duckduckgo", "brave")
        timeout = 15
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
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("href", item.get("link", "")),
                            "snippet": item.get("body", item.get("snippet", ""))
                        })
                    if results:
                        break

        if not results:
            if last_error is not None and "No results found" not in str(last_error):
                raise last_error
            return [{"message": f"No web search results found for query: '{query}'"}]

        return results
    except Exception as e:
        return [{"error": f"Failed to execute web search: {str(e)}"}]

def extract_content_from_web_links(web_link:str):
    """
    Use this tool to get the content from a web link in a clean markdown format.

    Args:
        web_link: The url from which the content needs to be extarcted.
    Returns:
        Extracted conent from the provied web link
    """
    if not web_link:
        return "No web link provided"
    response = requests.get(f"https://r.jina.ai/{web_link}",verify=False)
    return response.text