from pubmed_rag.chunk import chunk_article, n_tokens, pack_paragraphs


def test_abstract_only_article():
    art = {"title": "Dexmedetomidine for pediatric sedation",
           "abstract": "Background: sedation matters.\n\nConclusion: it works."}
    chunks = chunk_article(art)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.section == "abstract"
    assert c.chunk_index == 0
    assert "Dexmedetomidine" in c.content       # title is included
    assert "it works" in c.content


def test_title_only_article():
    chunks = chunk_article({"title": "A short note", "abstract": "", "full_text": ""})
    assert len(chunks) == 1
    assert chunks[0].content == "A short note"


def test_body_produces_multiple_ordered_chunks_with_overlap():
    para = ("This sentence is a filler paragraph about anesthesia. " * 20).strip()
    body = "\n\n".join([para] * 12)  # well over one chunk
    art = {"title": "T", "abstract": "A.", "full_text": body}
    chunks = chunk_article(art, target=200, overlap=40)
    body_chunks = [c for c in chunks if c.section == "body"]
    assert len(body_chunks) >= 2
    # indexes are contiguous and start after the abstract chunk
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # each body chunk respects the target (allow overlap slack)
    assert all(c.token_count <= 200 + 40 for c in body_chunks)
    # consecutive body chunks share overlapping text (continuity)
    assert body_chunks[0].content.split("\n\n")[-1] in body_chunks[1].content


def test_long_single_paragraph_is_hard_split():
    huge = "word " * 2000  # one paragraph, no breaks, ~2000 tokens
    chunks = pack_paragraphs(huge, target=200, overlap=20)
    assert len(chunks) > 1
    assert all(n_tokens(c) <= 220 for c in chunks)
