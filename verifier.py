import json
from openai import OpenAI
from tavily import TavilyClient

VERDICT_SYSTEM = """You are a strict evidence-based fact-checker.

Given a CLAIM and WEB SEARCH RESULTS, decide:
- Verified: web results clearly and directly support the claim
- Inaccurate: claim is outdated, off by significant margin, or partially wrong
- False: web results contradict the claim or provide no supporting evidence

Respond ONLY with a raw JSON object, no markdown, no extra text, with these exact keys:
"verdict": one of exactly "Verified", "Inaccurate", or "False"
"evidence": one concise sentence explaining your decision, max 40 words
"url": the single most relevant source URL, or empty string if none
"corrected_fact": if Inaccurate or False, the correct fact in one sentence; otherwise empty string

Example response:
{"verdict":"Inaccurate","evidence":"ChatGPT actually reached 100 million users in 2 months, not 1 month as claimed.","url":"https://example.com","corrected_fact":"ChatGPT reached 100 million users in approximately 2 months after launch."}
"""

def verify_claim(claim: str, openai_key: str, tavily_key: str) -> dict:
    fallback = {
        "claim": claim,
        "verdict": "False",
        "evidence": "Could not verify due to search or API error.",
        "url": "",
        "corrected_fact": "",
    }

    try:
        client = TavilyClient(api_key=tavily_key)
        results = client.search(
            query=claim,
            max_results=3,
            search_depth="basic",
            include_answer=False,
        )
        hits = results.get("results", [])
    except Exception as e:
        fallback["evidence"] = f"Web search failed: {e}"
        return fallback

    if not hits:
        fallback["evidence"] = "No web results found for this claim."
        return fallback

    snippets_text = ""
    for i, h in enumerate(hits[:3], 1):
        title = h.get("title", "")
        url = h.get("url", "")
        content = h.get("content", "")[:400]
        snippets_text += f"\n[{i}] {title}\nURL: {url}\nSnippet: {content}\n"

    try:
        oc = OpenAI(api_key=openai_key)
        response = oc.chat.completions.create(
            model="gpt-4o",
            max_tokens=400,
            messages=[
                {"role": "system", "content": VERDICT_SYSTEM},
                {"role": "user", "content": f"CLAIM: {claim}\n\nWEB SEARCH RESULTS:{snippets_text}"},
            ],
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        fallback["evidence"] = f"OpenAI verdict API error: {e}"
        return fallback

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        verdict = data.get("verdict", "False")
        if verdict not in ("Verified", "Inaccurate", "False"):
            verdict = "False"
        return {
            "claim": claim,
            "verdict": verdict,
            "evidence": data.get("evidence", ""),
            "url": data.get("url", ""),
            "corrected_fact": data.get("corrected_fact", ""),
        }
    except (json.JSONDecodeError, KeyError):
        fallback["evidence"] = f"Could not parse verdict. Raw: {raw[:120]}"
        return fallback
