"""Unit tests for TF-IDF vectorizer, concept extraction, and cosine similarity."""

import numpy as np
import pytest

from dendrite.analyzer import (
    TFIDFVectorizer,
    build_similarity_matrix,
    cosine_similarity,
    extract_concepts,
    find_related,
    tokenize,
)


class TestTokenize:
    def test_lowercases(self):
        assert tokenize("Hello World") == ["hello", "world"]

    def test_removes_stopwords(self):
        tokens = tokenize("the cat sat on the mat")
        assert "the" not in tokens
        assert "on" not in tokens

    def test_strips_punctuation(self):
        tokens = tokenize("neuron, axon! dendrite.")
        assert "neuron" in tokens
        assert "axon" in tokens
        assert "dendrite" in tokens

    def test_removes_short_tokens(self):
        tokens = tokenize("a is an at")
        assert tokens == []

    def test_empty_string(self):
        assert tokenize("") == []


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        assert cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_zero_vector(self):
        v1 = np.array([0.0, 0.0, 0.0])
        v2 = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v1, v2) == 0.0
        assert cosine_similarity(v2, v1) == 0.0

    def test_similar_vectors(self):
        v1 = np.array([1.0, 1.0, 0.0])
        v2 = np.array([1.0, 0.9, 0.1])
        sim = cosine_similarity(v1, v2)
        assert 0.9 < sim <= 1.0

    def test_opposite_vectors(self):
        v1 = np.array([1.0, 0.0])
        v2 = np.array([-1.0, 0.0])
        # cosine = -1, but our function returns a float; test it is negative or 0
        assert cosine_similarity(v1, v2) == pytest.approx(-1.0)


class TestTFIDFVectorizer:
    def test_fit_transform_shape(self):
        docs = ["the cat sat", "the dog ran fast", "birds fly high"]
        vec = TFIDFVectorizer()
        matrix = vec.fit_transform(docs)
        assert matrix.shape[0] == len(docs)
        assert matrix.shape[1] == len(vec.vocab)

    def test_tfidf_basic_idf_boost(self):
        """Rare terms should have higher IDF than common terms."""
        docs = [
            "energy energy energy cell",
            "energy energy mitochondria",
            "mitochondria powerhouse",
        ]
        vec = TFIDFVectorizer()
        vec.fit(docs)
        # "powerhouse" appears in 1 doc; "energy" in 2 docs → powerhouse has higher IDF
        idf_energy = vec.idf[vec.vocab["energy"]]
        idf_powerhouse = vec.idf[vec.vocab["powerhouse"]]
        assert idf_powerhouse > idf_energy

    def test_transform_without_fit_raises(self):
        vec = TFIDFVectorizer()
        with pytest.raises(RuntimeError):
            vec.transform(["hello"])

    def test_empty_documents(self):
        vec = TFIDFVectorizer()
        matrix = vec.fit_transform([])
        assert matrix.shape == (0, 0)

    def test_single_document(self):
        vec = TFIDFVectorizer()
        matrix = vec.fit_transform(["the mitochondria is the powerhouse"])
        assert matrix.shape[0] == 1

    def test_unseen_terms_ignored(self):
        """Terms in transform that weren't in fit vocab are silently ignored."""
        vec = TFIDFVectorizer()
        vec.fit(["cell energy atp"])
        matrix = vec.transform(["completely different words here xyzzy"])
        # All terms unknown; vector should be zero
        assert np.allclose(matrix[0], 0.0)


class TestExtractConcepts:
    def test_returns_list(self):
        result = extract_concepts("mitochondria powerhouse cell energy")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_stopwords_removed(self):
        result = extract_concepts("the quick brown fox jumps over the lazy dog")
        for concept in result:
            # Common stopwords should not appear
            assert concept not in ("the", "over", "and", "for")

    def test_top_n_respected(self):
        text = "cell energy atp mitochondria glucose brain neuron synapse axon"
        result = extract_concepts(text, top_n=3)
        assert len(result) <= 3

    def test_empty_text(self):
        assert extract_concepts("") == []

    def test_meaningful_terms_returned(self):
        text = "The mitochondria produces ATP energy for the cell"
        concepts = extract_concepts(text)
        # At least one biological term should appear
        assert any(c in concepts for c in ("mitochondria", "energy", "atp", "cell", "produces"))


class TestFindRelated:
    def test_returns_ranked_list(self):
        corpus = [
            "cell energy mitochondria atp",
            "brain neuron synapse signal",
            "energy production cellular respiration",
        ]
        results = find_related("energy cell", corpus)
        assert isinstance(results, list)
        assert len(results) == len(corpus)
        # All scores between -1 and 1
        for idx, score in results:
            assert -1.0 <= score <= 1.0

    def test_more_similar_ranks_higher(self):
        corpus = [
            "mitochondria produces energy atp",    # very related
            "dolphins swim ocean waves",             # unrelated
            "cell energy powerhouse metabolism",   # very related
        ]
        results = find_related("energy mitochondria cell", corpus)
        scores_by_idx = dict(results)
        # Indices 0 and 2 should score higher than index 1
        assert scores_by_idx[0] > scores_by_idx[1]
        assert scores_by_idx[2] > scores_by_idx[1]

    def test_top_k_limits_results(self):
        corpus = ["doc one", "doc two", "doc three", "doc four"]
        results = find_related("query text", corpus, top_k=2)
        assert len(results) == 2

    def test_empty_corpus(self):
        results = find_related("anything", [])
        assert results == []

    def test_identical_document_scores_highest(self):
        query = "mitochondria powerhouse cell energy"
        corpus = [query, "something completely unrelated about fish"]
        results = find_related(query, corpus)
        assert results[0][0] == 0  # identical doc is index 0 and should rank first
        assert results[0][1] == pytest.approx(1.0, abs=0.01)


class TestBuildSimilarityMatrix:
    def test_diagonal_is_one(self):
        texts = ["cell energy", "brain neuron", "atp mitochondria"]
        matrix = build_similarity_matrix(texts)
        for i in range(len(texts)):
            assert matrix[i, i] == pytest.approx(1.0, abs=0.01)

    def test_symmetric(self):
        texts = ["cell energy atp", "brain neuron synapse", "energy metabolism"]
        matrix = build_similarity_matrix(texts)
        for i in range(len(texts)):
            for j in range(len(texts)):
                assert matrix[i, j] == pytest.approx(matrix[j, i], abs=1e-10)

    def test_single_text(self):
        matrix = build_similarity_matrix(["only one"])
        assert matrix.shape == (1, 1)

    def test_dissimilar_texts_low_score(self):
        texts = ["mitochondria cell energy atp", "ocean dolphins waves surfing"]
        matrix = build_similarity_matrix(texts)
        assert matrix[0, 1] < 0.3
