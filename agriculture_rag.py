"""
agriculture_rag.py - Retrieval-Augmented Generation module for verified agriculture knowledge.
Extracts text from PDF/TXT/MD, chunks documents while preserving metadata,
builds an in-memory TF-IDF and n-gram vector index with cosine similarity,
and retrieves verified passages with source titles, URLs, and page numbers.
"""

import os
import re
from typing import List, Dict, Any, Optional

try:
    import pypdf
except ImportError:
    pypdf = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agriculture_knowledge")


class AgricultureRAG:
    def __init__(self, knowledge_dir: str = KNOWLEDGE_DIR):
        self.knowledge_dir = knowledge_dir
        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.load_and_index()

    def parse_metadata_from_text(self, text: str, filename: str) -> Dict[str, Any]:
        """Extract metadata header from text if present, otherwise default to filename."""
        metadata = {
            "source": "Verified Agricultural Document",
            "title": filename,
            "url": None,
            "year": None
        }
        for line in text[:1500].splitlines():
            line_clean = line.strip()
            if line_clean.lower().startswith("source:"):
                metadata["source"] = line_clean.split(":", 1)[1].strip()
            elif line_clean.lower().startswith("document title:"):
                metadata["title"] = line_clean.split(":", 1)[1].strip()
            elif line_clean.lower().startswith("reference url:") or line_clean.lower().startswith("url:"):
                metadata["url"] = line_clean.split(":", 1)[1].strip()
            elif line_clean.lower().startswith("publication year:") or line_clean.lower().startswith("year:"):
                metadata["year"] = line_clean.split(":", 1)[1].strip()
        return metadata

    def extract_from_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Extract text chunks and metadata from a file (.txt, .md, .pdf)."""
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        extracted_chunks = []

        if ext in [".txt", ".md"]:
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                
                # Skip the administrative README file from search chunks
                if "README_KNOWLEDGE_BASE" in filename:
                    return []

                metadata = self.parse_metadata_from_text(content, filename)
                
                # Split by sections or paragraphs
                sections = re.split(r'\n(?=## |\n\n)', content)
                for idx, sec in enumerate(sections):
                    cleaned = sec.strip()
                    if len(cleaned) < 40:
                        continue
                    extracted_chunks.append({
                        "id": f"{filename}#sec{idx+1}",
                        "source": metadata["source"],
                        "title": metadata["title"],
                        "url": metadata["url"],
                        "page": None,
                        "file": filename,
                        "content": cleaned
                    })
            except Exception as e:
                print(f"[RAG] Error reading {filename}: {e}")

        elif ext == ".pdf":
            if pypdf is None:
                print(f"[RAG] pypdf not available to parse {filename}")
                return []
            try:
                reader = pypdf.PdfReader(filepath)
                meta_info = reader.metadata or {}
                title = meta_info.get("/Title") or filename
                
                for page_num, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    page_text = page_text.strip()
                    if len(page_text) < 40:
                        continue
                    
                    # Split long pages into ~500 character chunks
                    paragraphs = re.split(r'\n{2,}', page_text)
                    for p_idx, para in enumerate(paragraphs):
                        para_clean = para.strip()
                        if len(para_clean) < 30:
                            continue
                        extracted_chunks.append({
                            "id": f"{filename}#p{page_num+1}_{p_idx+1}",
                            "source": "Official Agricultural Publication (PDF)",
                            "title": title,
                            "url": None,
                            "page": page_num + 1,
                            "file": filename,
                            "content": para_clean
                        })
            except Exception as e:
                print(f"[RAG] Error reading PDF {filename}: {e}")

        return extracted_chunks

    def load_and_index(self):
        """Scan knowledge_dir, chunk all documents, and compute TF-IDF matrix."""
        self.chunks = []
        if not os.path.exists(self.knowledge_dir):
            os.makedirs(self.knowledge_dir, exist_ok=True)

        for fname in os.listdir(self.knowledge_dir):
            full_path = os.path.join(self.knowledge_dir, fname)
            if os.path.isfile(full_path):
                file_chunks = self.extract_from_file(full_path)
                self.chunks.extend(file_chunks)

        if not self.chunks:
            self.vectorizer = None
            self.tfidf_matrix = None
            print("[RAG] No agricultural documents found to index.")
            return

        corpus = [c["content"] for c in self.chunks]
        # Use sublinear TF, token pattern suitable for Latin + Unicode Indic scripts, english stop words
        self.vectorizer = TfidfVectorizer(
            token_pattern=r"(?u)\b\w{3,}\b",
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        print(f"[RAG] Successfully indexed {len(self.chunks)} chunks from {self.knowledge_dir}")

    def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.10) -> List[Dict[str, Any]]:
        """Retrieve most relevant chunks for a user query."""
        if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        query_clean = query.strip()
        if not query_clean:
            return []

        try:
            query_vec = self.vectorizer.transform([query_clean])
            sim_scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]
            
            top_indices = np.argsort(sim_scores)[::-1]
            results = []
            
            # Extract query tokens (length >= 3)
            query_tokens = set(re.findall(r"(?u)\b\w{3,}\b", query_clean.lower()))
            
            for idx in top_indices[:top_k]:
                score = float(sim_scores[idx])
                if score >= min_score:
                    chunk = dict(self.chunks[idx])
                    chunk_tokens = set(re.findall(r"(?u)\b\w{3,}\b", chunk["content"].lower()))
                    # Ensure at least 1 meaningful substantive word overlap
                    overlap = query_tokens.intersection(chunk_tokens)
                    if overlap:
                        chunk["score"] = round(score, 3)
                        results.append(chunk)

            return results
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")
            return []

    def get_indexed_sources_summary(self) -> List[Dict[str, Any]]:
        """Returns metadata for all indexed documents."""
        sources = {}
        for c in self.chunks:
            key = c["file"]
            if key not in sources:
                sources[key] = {
                    "file": c["file"],
                    "title": c["title"],
                    "source": c["source"],
                    "url": c["url"],
                    "chunks_count": 0
                }
            sources[key]["chunks_count"] += 1
        return list(sources.values())


# Singleton instance
rag_system = AgricultureRAG()
