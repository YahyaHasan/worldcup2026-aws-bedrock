import json
import os
import boto3
import urllib3

ssm = boto3.client("ssm")
http = urllib3.PoolManager()

TAVILY_PARAM_NAME = "/worldcup2026/tavily-api-key"
TAVILY_ENDPOINT = "https://api.tavily.com/search"

# Cache the key across warm invocations so we don't hit SSM on every call.
_cached_key = None


def get_api_key():
    """Fetch the Tavily key from SSM Parameter Store, decrypted. Cached per container."""
    global _cached_key
    if _cached_key is None:
        response = ssm.get_parameter(Name=TAVILY_PARAM_NAME, WithDecryption=True)
        _cached_key = response["Parameter"]["Value"].strip()
    return _cached_key

def search_tavily(query, max_results=5):
    """Call the Tavily search API and return its raw results."""
    api_key = get_api_key()

    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": True,
    }

    response = http.request(
        "POST",
        TAVILY_ENDPOINT,
        body=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    if response.status != 200:
        return None

    return json.loads(response.data.decode("utf-8"))

def synthesize(tavily_response):
    """Turn raw Tavily results into a short summary + source list."""
    results = tavily_response.get("results", [])
    answer = tavily_response.get("answer")  # Tavily's own synthesized answer, if present

    sources = [
        {"title": r.get("title", ""), "url": r.get("url", "")}
        for r in results[:3]
    ]

    if answer:
        summary = answer
    elif results:
        # Fall back to stitching the top results' content snippets.
        snippets = [r.get("content", "") for r in results[:2]]
        summary = " ".join(snippets)[:500]
    else:
        summary = "No recent news found for this query."

    return {"summary": summary, "sources": sources}

def lambda_handler(event, context):
    """Entry point. Expects team_name, with optional topic_hint."""
    team_name = event.get("team_name")
    if not team_name:
        return {"error": "team_name is required"}

    topic_hint = event.get("topic_hint", "")
    query = f"{team_name} national football team {topic_hint} news 2026".strip()

    tavily_response = search_tavily(query)
    if tavily_response is None:
        return {"error": "News search failed — the search service returned an error."}

    return synthesize(tavily_response)
