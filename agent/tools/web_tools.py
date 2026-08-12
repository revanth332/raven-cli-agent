"""
Web search tools for Raven CLI Agent using DuckDuckGo search.
"""

from typing import List, Dict, Any

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


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
        with DDGS() as ddgs:
            raw_results = ddgs.text(query.strip(), max_results=max_results)
            if raw_results:
                for item in raw_results:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", item.get("link", "")),
                        "snippet": item.get("body", item.get("snippet", ""))
                    })

        if not results:
            return [{"message": f"No web search results found for query: '{query}'"}]

        return results
    except Exception as e:
        return [{"error": f"Failed to execute web search: {str(e)}"}]
