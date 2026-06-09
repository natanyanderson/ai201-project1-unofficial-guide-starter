"""
app.py — Milestone 5: Generation + interface for the Mercy CS RAG system.

Pipeline this file owns (last two stages of the architecture diagram):
    Retrieval (embed.retrieve) --> Generation (Groq) --> Gradio UI

Design notes tied to planning.md "Anticipated Challenges":
  - Challenge #1 (corpus skewed to professor opinions; can't answer facts it
    doesn't store, e.g. average GPA): the system prompt forbids outside
    knowledge and forces the exact refusal string when the context is silent.
  - Challenge #2 (single-review hallucination / fake "most students say..."):
    the prompt explicitly bans implying a consensus and bans inventing reviews,
    names, or numbers.
  - Source attribution is NOT trusted to the LLM. URLs are collected from the
    retrieved chunks' metadata and appended programmatically, so the model can
    neither fabricate nor omit them.

Run:
    pip install groq gradio
    export GROQ_API_KEY=...        # required
    python app.py                  # runs the 3 test queries, then launches the UI
"""

import os

from groq import Groq

# retrieve(query, k=4) -> list of chunks, each with: text, metadata, source_url, distance
from embed import retrieve


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
MODEL = "llama-3.3-70b-versatile"
TOP_K = 4

# The single canonical refusal string. We instruct the model to emit it verbatim
# and we also detect it to decide whether to attach sources.
NO_INFO = "I don't have enough information in my sources to answer that."

# Optional hard cutoff. ChromaDB returns a distance per chunk; if the *closest*
# chunk is farther than this, we refuse before even calling the LLM. Left as None
# because the right value depends on your embedding/distance metric — inspect the
# distances printed by the test harness, then set a float here if you want the
# extra guard. The prompt alone already handles the GPA-style negative case.
DISTANCE_THRESHOLD = None

SYSTEM_PROMPT = f"""You are a question-answering assistant for Computer Science \
students at Mercy University. You answer questions about CS courses, electives, \
degree requirements, and professors.

Answer using ONLY the information contained in the context chunks provided in the \
user message. Obey these rules strictly:

1. Use only facts stated in the context. Do NOT use outside or general knowledge.
2. Never invent or guess details — no made-up professor names, course codes, \
prerequisites, numbers, statistics, or reviews.
3. If the context does not clearly contain the answer, reply with EXACTLY this \
sentence and nothing else: "{NO_INFO}"
4. If the context contains only ONE student review about a professor, answer from \
that single review only. Do NOT imply a consensus and do NOT use phrases like \
"most students," "students generally," or "reviews say" as if there were many.
5. When reviews disagree, say so plainly (e.g. "reviews are mixed").
6. Do NOT include URLs or source links in your answer — sources are added \
automatically afterward.
7. Be concise and factual."""


# --------------------------------------------------------------------------- #
# Groq client
# --------------------------------------------------------------------------- #
def _make_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Run: export GROQ_API_KEY=your_key_here"
        )
    return Groq(api_key=key)


# Created lazily so importing this module doesn't fail when no key is present.
_client = None


def _client_or_init():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _field(chunk, name, default=None):
    """Read a field from a chunk whether it's a dict or an object."""
    if isinstance(chunk, dict):
        return chunk.get(name, default)
    return getattr(chunk, name, default)


def _meta_label(chunk):
    """Build a short human-readable tag from a chunk's metadata for the context."""
    meta = _field(chunk, "metadata", {}) or {}
    parts = []
    for key in ("source_type", "type"):
        if meta.get(key):
            parts.append(str(meta[key]))
            break
    for key in ("professor", "course_code", "course", "semester"):
        if meta.get(key):
            parts.append(f"{key}={meta[key]}")
    return " | ".join(parts) if parts else "source"


def build_context(chunks):
    """Format retrieved chunks into a numbered context block for the prompt."""
    blocks = []
    for i, chunk in enumerate(chunks, 1):
        text = (_field(chunk, "text", "") or "").strip()
        blocks.append(f"[Chunk {i} | {_meta_label(chunk)}]\n{text}")
    return "\n\n".join(blocks)


def format_sources(chunks):
    """Deduplicated source URLs from the retrieved chunks, in retrieval order."""
    seen = set()
    urls = []
    for chunk in chunks:
        url = _field(chunk, "source_url") or (
            (_field(chunk, "metadata", {}) or {}).get("source_url")
        )
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    if not urls:
        return "(no source URLs attached to the retrieved chunks)"
    return "\n".join(f"- {u}" for u in urls)


def is_no_info(answer):
    """True if the model declined to answer (so we shouldn't attach sources)."""
    return "don't have enough information" in answer.lower()


def call_groq(context, query):
    """Send context + question to Groq and return the answer text."""
    client = _client_or_init()
    user_message = f"Context:\n{context}\n\nQuestion: {query}"
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,  # deterministic, grounded answers — minimizes drift/hallucination
    )
    return completion.choices[0].message.content.strip()


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #
def answer_question(query, k=TOP_K):
    """
    Full generation step: retrieve -> ground with Groq -> attach sources.
    Returns (answer, sources) so the Gradio UI can show them separately.
    """
    query = (query or "").strip()
    if not query:
        return "Please enter a question.", ""

    chunks = retrieve(query, k=k)

    # Nothing retrieved at all -> refuse.
    if not chunks:
        return NO_INFO, "(no relevant sources found)"

    # Optional hard distance cutoff (off by default; see DISTANCE_THRESHOLD).
    if DISTANCE_THRESHOLD is not None:
        distances = [
            d for d in (_field(c, "distance") for c in chunks) if d is not None
        ]
        if distances and min(distances) > DISTANCE_THRESHOLD:
            return NO_INFO, "(no relevant sources found)"

    context = build_context(chunks)
    answer = call_groq(context, query)

    # If the model refused, don't attach sources — they'd falsely imply an answer.
    if is_no_info(answer):
        return answer, "(no relevant sources found)"

    return answer, format_sources(chunks)


# --------------------------------------------------------------------------- #
# Gradio interface
# --------------------------------------------------------------------------- #
def build_demo():
    import gradio as gr

    with gr.Blocks(title="Mercy CS Course & Professor Q&A") as demo:
        gr.Markdown(
            "# Mercy CS Course & Professor Q&A\n"
            "Ask about CS courses, electives, degree requirements, or professors at "
            "Mercy University. Answers come only from the indexed sources."
        )
        question = gr.Textbox(
            label="Your question",
            placeholder="e.g. How is Samer Almazahreh as a professor?",
            lines=2,
        )
        ask_btn = gr.Button("Ask", variant="primary")
        answer_out = gr.Textbox(label="Answer", lines=6)
        sources_out = gr.Textbox(label="Sources", lines=4)

        # No HTML <form>; wire the button and the Enter key to the handler.
        ask_btn.click(answer_question, inputs=question, outputs=[answer_out, sources_out])
        question.submit(answer_question, inputs=question, outputs=[answer_out, sources_out])

    return demo


# --------------------------------------------------------------------------- #
# Entry point: run the 3 required test queries, then launch the UI
# --------------------------------------------------------------------------- #
TEST_QUERIES = [
    "How is Samer Almazahreh as a professor at Mercy College?",
    "What is the corequisite or prerequisite for the Artificial Intelligence class at Mercy College?",
    "What is the average GPA for a Mercy Computer Science student?",  # negative test (challenge #1)
]


def run_tests():
    print("=" * 70)
    print("TEST RUN — 3 queries")
    print("=" * 70)
    for q in TEST_QUERIES:
        answer, sources = answer_question(q)
        print(f"\nQ: {q}\n")
        print(f"A: {answer}\n")
        print("Sources:")
        print(sources)
        print("-" * 70)


if __name__ == "__main__":
    run_tests()

    # Launch the UI after the tests print. Set SKIP_UI=1 to run tests only.
    if os.environ.get("SKIP_UI") != "1":
        build_demo().launch()
