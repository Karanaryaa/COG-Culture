import json
import fitz
from openai import OpenAI

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()

EXTRACTION_SYSTEM = """You are a precise fact-extraction expert.
From the document text, extract every specific verifiable claim:
- Statistics and percentages (e.g. "global AI market grew 38% in 2023")
- Dates and timelines (e.g. "ChatGPT launched in November 2022")
- Financial figures (e.g. "OpenAI raised $10 billion from Microsoft")
- Named technical facts (e.g. "GPT-4 has 1.8 trillion parameters")
- Any concrete numerical assertion

Rules:
- Skip vague or subjective statements like "AI is transforming industries"
- Each claim must be a standalone searchable sentence
- Return ONLY a raw JSON array of strings, no markdown, no explanation
- Maximum 15 claims

Example output:
["OpenAI was founded in 2015.", "ChatGPT reached 100 million users in 2 months."]
"""

def extract_claims(pdf_bytes: bytes, api_key: str):
    try:
        text = extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        return [], f"Could not read PDF: {e}"

    if not text:
        return [], "No extractable text found. Try a text-based PDF."

    truncated = text[:6000]

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user", "content": truncated},
            ],
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        return [], f"OpenAI API error during extraction: {e}"

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        claims = json.loads(clean)
        if not isinstance(claims, list):
            return [], "OpenAI returned unexpected format."
        return [str(c) for c in claims if c], None
    except json.JSONDecodeError:
        return [], f"Could not parse OpenAI response as JSON. Raw: {raw}"
