import streamlit as st
import os
from extractor import extract_claims
from verifier import verify_claim

st.set_page_config(
    page_title="AI Fact Checker",
    page_icon="🔍",
    layout="centered",
)

st.markdown("""
<style>
.verdict-verified  { background:#d4edda; color:#155724; padding:4px 12px; border-radius:12px; font-weight:700; font-size:0.85rem; display:inline-block; }
.verdict-inaccurate{ background:#fff3cd; color:#856404; padding:4px 12px; border-radius:12px; font-weight:700; font-size:0.85rem; display:inline-block; }
.verdict-false     { background:#f8d7da; color:#721c24; padding:4px 12px; border-radius:12px; font-weight:700; font-size:0.85rem; display:inline-block; }
.corrected         { background:#e8f4f8; border-left:4px solid #17a2b8; padding:8px 12px; border-radius:4px; margin-top:8px; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 AI Fact Checker")
st.markdown("Upload any PDF and this tool will **extract verifiable claims**, **search the live web** to cross-reference them, and **flag inaccuracies** automatically.")
st.divider()

def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")

OPENAI_KEY = get_secret("OPENAI_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

if not OPENAI_KEY or not TAVILY_KEY:
    missing = []
    if not OPENAI_KEY:
        missing.append("OPENAI_API_KEY")
    if not TAVILY_KEY:
        missing.append("TAVILY_API_KEY")
    st.error(f"⚠️ API keys missing: {', '.join(missing)}. Add them to Replit Secrets.")
    st.stop()

uploaded = st.file_uploader("📄 Upload a PDF document", type=["pdf"])

if uploaded:
    pdf_bytes = uploaded.read()
    st.success(f"Loaded: **{uploaded.name}** ({len(pdf_bytes)//1024} KB)")

    if st.button("🚀 Run Fact Check", use_container_width=True, type="primary"):

        with st.spinner("📖 Extracting claims from PDF..."):
            claims, error = extract_claims(pdf_bytes, OPENAI_KEY)

        if error:
            st.error(f"Extraction failed: {error}")
            st.stop()

        if not claims:
            st.warning("No verifiable claims found in this document.")
            st.stop()

        st.info(f"Found **{len(claims)} claims**. Verifying against live web data...")

        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, claim in enumerate(claims):
            status.markdown(f"🔎 Checking claim {i+1}/{len(claims)}: *{claim[:80]}...*")
            result = verify_claim(claim, OPENAI_KEY, TAVILY_KEY)
            results.append(result)
            progress.progress((i + 1) / len(claims))

        status.empty()
        progress.empty()
        st.divider()

        st.subheader("📋 Fact-Check Report")
        verdicts = {"Verified": 0, "Inaccurate": 0, "False": 0}

        for r in results:
            v = r["verdict"]
            verdicts[v] = verdicts.get(v, 0) + 1
            icon = {"Verified": "✅", "Inaccurate": "⚠️", "False": "❌"}.get(v, "❓")
            css_class = {
                "Verified": "verdict-verified",
                "Inaccurate": "verdict-inaccurate",
                "False": "verdict-false"
            }.get(v, "verdict-false")

            with st.expander(f"{icon} {r['claim'][:100]}{'...' if len(r['claim'])>100 else ''}"):
                st.markdown(f'<span class="{css_class}">{icon} {v}</span>', unsafe_allow_html=True)
                st.markdown(f"**Evidence:** {r['evidence']}")
                if r.get("url"):
                    st.markdown(f"🔗 [Source]({r['url']})")
                if r.get("corrected_fact"):
                    st.markdown(
                        f'<div class="corrected">💡 <strong>Correct fact:</strong> {r["corrected_fact"]}</div>',
                        unsafe_allow_html=True
                    )

        st.divider()
        st.subheader("📊 Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Verified", verdicts["Verified"])
        c2.metric("⚠️ Inaccurate", verdicts["Inaccurate"])
        c3.metric("❌ False", verdicts["False"])

        total = len(results)
        accuracy_pct = round((verdicts["Verified"] / total) * 100) if total else 0
        st.markdown(f"**Overall accuracy score: {accuracy_pct}%** ({verdicts['Verified']}/{total} claims verified)")
