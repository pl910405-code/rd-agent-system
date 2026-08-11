"""
RAG知识库引擎 - 基于TF-IDF + BM25的语义检索
支持文档上传、分块索引、相似度检索、引用来源追踪
"""
import os
import json
import pickle
import numpy as np
from typing import List, Dict, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from doc_processor import doc_processor

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
KB_DIR = os.path.join(DATA_DIR, "kb")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
INDEX_PATH = os.path.join(KB_DIR, "kb_index.pkl")


class RAGEngine:
    """RAG知识库引擎"""

    def __init__(self):
        self.documents = []  # 所有文档块 {id, text, source, filename, chunk_index, char_count}
        self.doc_metadata = []  # 文档元数据 {filename, file_path, file_type, total_chars, chunk_count, upload_time}
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            token_pattern=r'(?u)\b\w+\b|[^\s\d\w]',  # 支持中文分词
        )
        self.tfidf_matrix = None
        self._load_index()

    def add_document(self, file_path: str) -> Dict:
        """处理并索引一个文档"""
        result = doc_processor.process_file(file_path)
        if "error" in result:
            return result

        chunks = result.get("chunks", [])
        if not chunks:
            return {"error": "文档内容为空或解析失败"}

        # 添加到文档库
        for chunk in chunks:
            self.documents.append({
                "id": chunk["id"],
                "text": chunk["text"],
                "source": result["filename"],
                "filename": result["filename"],
                "chunk_index": chunk["chunk_index"],
                "char_count": chunk["char_count"]
            })

        # 更新元数据
        import datetime
        self.doc_metadata.append({
            "filename": result["filename"],
            "file_path": file_path,
            "file_type": result["file_type"],
            "total_chars": result["total_chars"],
            "chunk_count": len(chunks),
            "upload_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        # 重建索引
        self._rebuild_index()
        self._save_index()

        return {
            "filename": result["filename"],
            "total_chars": result["total_chars"],
            "chunk_count": len(chunks),
            "total_documents": len(self.doc_metadata),
            "total_chunks": len(self.documents),
            "status": "success"
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """语义检索：返回最相关的文档块"""
        if not self.documents or self.tfidf_matrix is None:
            return []

        # 向量化查询
        query_vec = self.vectorizer.transform([query])
        
        # 计算余弦相似度
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # BM25风格的增强评分
        bm25_scores = self._bm25_score(query)
        
        # 综合评分 = 0.5 * TF-IDF余弦相似度 + 0.5 * BM25
        combined_scores = 0.5 * similarities + 0.5 * bm25_scores
        
        # 获取Top K结果
        top_indices = np.argsort(combined_scores)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if combined_scores[idx] > 0:
                doc = self.documents[idx]
                results.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "source": doc["source"],
                    "filename": doc["filename"],
                    "chunk_index": doc["chunk_index"],
                    "score": float(combined_scores[idx]),
                    "tfidf_score": float(similarities[idx]),
                    "bm25_score": float(bm25_scores[idx])
                })
        
        return results

    def search_with_context(self, query: str, top_k: int = 5) -> Dict:
        """检索并返回格式化上下文"""
        results = self.search(query, top_k)
        
        context_parts = []
        for i, r in enumerate(results):
            context_parts.append(f"[来源{i+1}: {r['source']} (相似度: {r['score']:.2f})]\n{r['text']}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        return {
            "query": query,
            "context": context,
            "sources": [{"source": r["source"], "score": r["score"], "text_preview": r["text"][:200]} for r in results],
            "total_results": len(results)
        }

    def get_documents(self) -> List[Dict]:
        """获取所有已索引文档列表"""
        return self.doc_metadata

    def remove_document(self, filename: str) -> Dict:
        """删除指定文档"""
        self.documents = [d for d in self.documents if d["filename"] != filename]
        self.doc_metadata = [d for d in self.doc_metadata if d["filename"] != filename]
        self._rebuild_index()
        self._save_index()
        return {"removed": filename, "remaining_docs": len(self.doc_metadata)}

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        return {
            "total_documents": len(self.doc_metadata),
            "total_chunks": len(self.documents),
            "total_chars": sum(d["char_count"] for d in self.documents),
            "documents": [{"filename": d["filename"], "chunks": d["chunk_count"], "chars": d["total_chars"]} for d in self.doc_metadata]
        }

    def _bm25_score(self, query: str) -> np.ndarray:
        """简易BM25评分"""
        if self.tfidf_matrix is None or len(self.documents) == 0:
            return np.zeros(len(self.documents))
        
        query_terms = set(query.lower().split())
        if not query_terms:
            return np.zeros(len(self.documents))
        
        # 文档频率
        df = np.array([sum(1 for term in query_terms if term in doc["text"].lower()) for doc in self.documents])
        
        # 文档长度
        doc_lengths = np.array([len(doc["text"]) for doc in self.documents])
        avg_length = doc_lengths.mean() if doc_lengths.mean() > 0 else 1
        
        # BM25参数
        k1 = 1.5
        b = 0.75
        N = len(self.documents)
        
        # IDF
        idf = np.log((N - df + 0.5) / (df + 0.5) + 1)
        idf = np.where(df > 0, idf, 0)
        
        # TF (词频近似)
        tf = np.array([sum(doc["text"].lower().count(term) for term in query_terms) for doc in self.documents])
        tf = tf / (doc_lengths / avg_length + 1)
        
        # BM25分数
        scores = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_lengths / avg_length))
        
        return scores

    def _rebuild_index(self):
        """重建TF-IDF索引"""
        if not self.documents:
            self.tfidf_matrix = None
            return
        texts = [doc["text"] for doc in self.documents]
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)

    def _save_index(self):
        """保存索引到磁盘"""
        os.makedirs(KB_DIR, exist_ok=True)
        try:
            data = {
                "documents": self.documents,
                "doc_metadata": self.doc_metadata,
                "vectorizer_vocab": self.vectorizer.vocabulary_,
                "vectorizer_idf": self.vectorizer.idf_,
                "tfidf_matrix": self.tfidf_matrix
            }
            with open(INDEX_PATH, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"保存索引失败: {e}")

    def _load_index(self):
        """从磁盘加载索引"""
        if os.path.exists(INDEX_PATH):
            try:
                with open(INDEX_PATH, "rb") as f:
                    data = pickle.load(f)
                self.documents = data.get("documents", [])
                self.doc_metadata = data.get("doc_metadata", [])
                vocab = data.get("vectorizer_vocab", {})
                idf = data.get("vectorizer_idf", None)
                if vocab and idf is not None:
                    self.vectorizer = TfidfVectorizer(
                        max_features=10000, ngram_range=(1, 2),
                        min_df=1, max_df=0.95, token_pattern=r'(?u)\b\w+\b|[^\s\d\w]',
                        vocabulary=vocab
                    )
                    self.vectorizer.idf_ = idf
                    self.tfidf_matrix = data.get("tfidf_matrix", None)
                print(f"已加载知识库: {len(self.doc_metadata)}个文档, {len(self.documents)}个文本块")
            except Exception as e:
                print(f"加载索引失败: {e}, 将使用空知识库")
                self.documents = []
                self.doc_metadata = []
                self.tfidf_matrix = None
        else:
            print("知识库为空，等待上传文档")


# 全局RAG引擎实例
rag_engine = RAGEngine()
