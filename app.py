"""Streamlit UI for the PubMed RAG for Anesthesiology system.

Run:  uv run streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from pubmed_rag.config import config
from pubmed_rag.rag import answer, save_feedback
from pubmed_rag.retrieval import keyword_search

st.set_page_config(page_title="PubMed RAG for Anesthesiology", page_icon="💊", layout="centered")

st.title("💊 PubMed RAG for Anesthesiology")
st.caption(
    "Ask a clinical question and get an answer grounded in PubMed literature, with citations. "
    "Retrieval runs over a knowledge base of anesthesiology papers (abstracts + PMC full text)."
)

# --- sidebar controls -------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    strategy = st.selectbox(
        "Retrieval strategy", ["hybrid_rerank", "hybrid", "vector", "keyword"],
        help="hybrid_rerank = hybrid + cross-encoder rerank + dedupe (best). "
             "hybrid = keyword + vector (RRF). vector/hybrid need embeddings.",
    )
    top_k = st.slider("Sources (top-k)", 3, 15, 8)
    rewrite = st.toggle("Rewrite query for retrieval", value=True)
    st.divider()
    st.caption(f"Chat model: `{config.chat_model}`  \nEmbed model: `{config.embed_model}`")
    if not config.openai_api_key:
        st.warning("No OPENAI_API_KEY set — generation and vector search are disabled. "
                   "Keyword search still works.")

# --- session state ----------------------------------------------------------
st.session_state.setdefault("result", None)
st.session_state.setdefault("feedback_sent", False)

# --- query form -------------------------------------------------------------
with st.form("ask"):
    question = st.text_input(
        "Your question",
        placeholder="e.g. What is the most effective prophylaxis for postoperative nausea and vomiting?",
    )
    submitted = st.form_submit_button("Ask", type="primary")

if submitted and question.strip():
    st.session_state.feedback_sent = False
    if not config.openai_api_key:
        # graceful fallback: show keyword hits only
        st.info("Generation disabled (no API key). Showing keyword search results instead.")
        hits = keyword_search(question, k=top_k)
        st.session_state.result = ("fallback", question, hits)
    else:
        with st.spinner("Searching literature and composing a grounded answer…"):
            try:
                st.session_state.result = ("full", question,
                                           answer(question, strategy=strategy, k=top_k, rewrite=rewrite))
            except Exception as e:  # embeddings missing, API error, etc.
                st.error(f"Could not generate an answer: {e}")
                st.session_state.result = None

# --- render result ----------------------------------------------------------
res = st.session_state.result
if res and res[0] == "full":
    _, question, r = res
    st.markdown("### Answer")
    st.markdown(r.text)
    st.caption(
        f"strategy: `{r.strategy}` · rewritten: _{r.rewritten}_ · "
        f"{r.latency_ms} ms · ${r.usage.cost_usd:.4f}"
    )

    st.markdown("### Sources")
    for i, h in enumerate(r.hits, 1):
        with st.expander(f"[{i}] {h.title}  ·  {h.journal} {h.pub_year or ''}"):
            st.markdown(f"**PMID:** [{h.pmid}]({h.source_url})  ·  section: `{h.section}`")
            st.write(h.content)

    if r.query_log_id and not st.session_state.feedback_sent:
        st.markdown("#### Was this helpful?")
        c1, c2, _ = st.columns([1, 1, 6])
        if c1.button("👍 Yes"):
            save_feedback(r.query_log_id, 1)
            st.session_state.feedback_sent = True
            st.toast("Thanks for the feedback!")
        if c2.button("👎 No"):
            save_feedback(r.query_log_id, -1)
            st.session_state.feedback_sent = True
            st.toast("Thanks — we'll use this to improve.")
    elif st.session_state.feedback_sent:
        st.success("Feedback recorded.")

elif res and res[0] == "fallback":
    _, question, hits = res
    st.markdown("### Keyword search results")
    if not hits:
        st.write("No matching passages found.")
    for i, h in enumerate(hits, 1):
        with st.expander(f"[{i}] {h.title}  ·  {h.journal} {h.pub_year or ''}"):
            st.markdown(f"**PMID:** [{h.pmid}]({h.source_url})  ·  section: `{h.section}`")
            st.write(h.content)

st.divider()
st.caption("⚕️ This tool summarizes published literature and is not medical advice.")
