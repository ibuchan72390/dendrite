"""TF-IDF vectorizer, concept extraction, and cosine similarity — all from scratch with numpy."""

import math
import re
from collections import Counter
from typing import Optional

import numpy as np

# Extended English stopwords
STOPWORDS = frozenset(
    """
a about above after again against all also am an and any are aren't as at
be because been before being below between both but by
can't cannot could couldn't
did didn't do does doesn't doing don't down during
each even every few for from further
get got had hadn't has hasn't have haven't having he he'd he'll he's her here here's
hers herself him himself his how how's
i i'd i'll i'm i've if in into is isn't it it's its itself
just
let's
me more most mustn't my myself
no nor not
of off on once only or other ought our ours ourselves out over own
same shan't she she'd she'll she's should shouldn't so some such
than that that's the their theirs them themselves then there there's these they
they'd they'll they're they've this those through to too
under until up
very
was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's will with won't would wouldn't
you you'd you'll you're you've your yours yourself yourselves
""".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


class TFIDFVectorizer:
    """Minimal TF-IDF implementation using numpy.  Fits on a corpus, transforms documents."""

    def __init__(self):
        self.vocab: dict[str, int] = {}  # term -> column index
        self.idf: Optional[np.ndarray] = None
        self._fitted = False

    def fit(self, documents: list[str]) -> "TFIDFVectorizer":
        """Build vocabulary and compute IDF weights."""
        if not documents:
            self._fitted = True
            return self

        tokenized = [tokenize(doc) for doc in documents]
        # Build vocabulary from all unique terms
        all_terms: set[str] = set()
        for tokens in tokenized:
            all_terms.update(tokens)
        self.vocab = {term: idx for idx, term in enumerate(sorted(all_terms))}

        n_docs = len(documents)
        n_terms = len(self.vocab)
        df = np.zeros(n_terms, dtype=float)

        for tokens in tokenized:
            unique_tokens = set(tokens)
            for t in unique_tokens:
                if t in self.vocab:
                    df[self.vocab[t]] += 1.0

        # Smooth IDF: log((1+n)/(1+df)) + 1  (sklearn-style, prevents zero IDF)
        self.idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0
        self._fitted = True
        return self

    def transform(self, documents: list[str]) -> np.ndarray:
        """Return TF-IDF matrix of shape (n_docs, n_terms)."""
        if not self._fitted:
            raise RuntimeError("Vectorizer must be fitted before transform.")
        if not self.vocab:
            return np.zeros((len(documents), 0))

        n_terms = len(self.vocab)
        matrix = np.zeros((len(documents), n_terms), dtype=float)

        for i, doc in enumerate(documents):
            tokens = tokenize(doc)
            if not tokens:
                continue
            counts = Counter(tokens)
            for term, count in counts.items():
                if term in self.vocab:
                    j = self.vocab[term]
                    tf = count / len(tokens)  # relative frequency
                    matrix[i, j] = tf * self.idf[j]

        return matrix

    def fit_transform(self, documents: list[str]) -> np.ndarray:
        return self.fit(documents).transform(documents)


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Return cosine similarity in [-1, 1].  Returns 0 for zero vectors."""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def extract_concepts(text: str, top_n: int = 8) -> list[str]:
    """Return the top_n most significant terms by raw TF score."""
    tokens = tokenize(text)
    if not tokens:
        return []
    counts = Counter(tokens)
    # Sort by frequency, then alphabetically for stability
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [term for term, _ in ranked[:top_n]]


def find_related(
    query_text: str,
    corpus_texts: list[str],
    top_k: Optional[int] = None,
) -> list[tuple[int, float]]:
    """
    Return a list of (corpus_index, similarity_score) sorted descending.

    Falls back to simple token overlap when corpus is too small for IDF to be meaningful.
    """
    if not corpus_texts:
        return []

    all_texts = corpus_texts + [query_text]

    vectorizer = TFIDFVectorizer()
    matrix = vectorizer.fit_transform(all_texts)

    corpus_matrix = matrix[:-1]
    query_vec = matrix[-1]

    scores: list[tuple[int, float]] = []
    for i, doc_vec in enumerate(corpus_matrix):
        sim = cosine_similarity(query_vec, doc_vec)
        scores.append((i, sim))

    scores.sort(key=lambda x: -x[1])

    if top_k is not None:
        scores = scores[:top_k]

    return scores


def build_similarity_matrix(texts: list[str]) -> np.ndarray:
    """Return an N×N cosine similarity matrix for a list of texts."""
    if len(texts) < 2:
        return np.zeros((len(texts), len(texts)))

    vectorizer = TFIDFVectorizer()
    matrix = vectorizer.fit_transform(texts)

    n = len(texts)
    sim_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            sim_matrix[i, j] = cosine_similarity(matrix[i], matrix[j])

    return sim_matrix
