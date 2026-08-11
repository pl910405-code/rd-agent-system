"""
联网搜索模块 - 专利/文献/原料/通用网络搜索
多引擎搜索：DuckDuckGo → Bing → 直接HTTP请求
"""
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except Exception:
    HAS_DDGS = False


class WebSearchEngine:
    """联网搜索引擎，支持多种搜索类型"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.timeout = 15

    def search_all(self, query: str, product_type: str = "", max_results: int = 5) -> Dict:
        """综合搜索"""
        results = {
            "query": query,
            "product_type": product_type,
            "patents": self.search_patents(query, product_type, max_results=5),
            "literature": self.search_literature(query, max_results=5),
            "materials": self.search_materials(query, product_type, max_results=5),
            "web": self.search_web(query, max_results=5),
        }
        results["total"] = sum(len(v) for v in [results["patents"], results["literature"], results["materials"], results["web"]] if isinstance(v, list))
        return results

    def search_web(self, query: str, max_results: int = 10) -> List[Dict]:
        """通用网络搜索（多引擎）"""
        results = []
        # 尝试DuckDuckGo
        if HAS_DDGS:
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results, region="cn-zh"):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("href", r.get("url", "")),
                            "snippet": r.get("body", r.get("snippet", "")),
                            "source": "DuckDuckGo"
                        })
            except Exception:
                pass

        # DuckDuckGo失败，用Bing
        if len(results) < max_results:
            bing_results = self._bing_search(query, max_results - len(results))
            results.extend(bing_results)

        # Bing也不行，用Google
        if len(results) < max_results:
            google_results = self._google_search(query, max_results - len(results))
            results.extend(google_results)

        return results[:max_results]

    def search_patents(self, query: str, product_type: str = "", max_results: int = 5) -> List[Dict]:
        """专利搜索"""
        patents = []
        search_term = f"{query} {product_type}".strip()

        # 方法1: DuckDuckGo搜patents.google.com
        if HAS_DDGS:
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(f"site:patents.google.com {search_term}", max_results=max_results):
                        patent_url = r.get("href", r.get("url", ""))
                        patents.append({
                            "title": r.get("title", ""),
                            "url": patent_url,
                            "patent_id": self._extract_patent_id(patent_url),
                            "snippet": r.get("body", r.get("snippet", "")),
                            "source": "Google Patents"
                        })
            except Exception:
                pass

        # 方法2: Bing搜专利
        if len(patents) < max_results:
            bing_results = self._bing_search(f"专利 {search_term} UV胶 光学膜", max_results - len(patents))
            for r in bing_results:
                r["patent_id"] = self._extract_patent_id(r.get("url", ""))
                r["source"] = "Bing-专利"
                patents.append(r)

        # 方法3: Google搜专利
        if len(patents) < max_results:
            google_results = self._google_search(f"patent {search_term} UV adhesive optical film", max_results - len(patents))
            for r in google_results:
                r["patent_id"] = self._extract_patent_id(r.get("url", ""))
                r["source"] = "Google-专利"
                patents.append(r)

        return patents[:max_results]

    def search_literature(self, query: str, max_results: int = 5) -> List[Dict]:
        """学术论文搜索"""
        papers = []
        queries = [f"{query} 研究 论文", f"{query} UV固化 胶粘剂 性能"]

        for q in queries:
            if len(papers) >= max_results:
                break
            # Bing搜索
            results = self._bing_search(q, max_results - len(papers))
            for r in results:
                title = r.get("title", "")
                url = r.get("url", "")
                if any(kw in title.lower() or kw in url.lower() for kw in
                       ["论文", "期刊", "研究", "journal", "paper", "cnki", "万方", "维普", "research", "study"]):
                    r["source"] = "Bing-学术"
                    papers.append(r)
            # Google搜索
            if len(papers) < max_results:
                results = self._google_search(q, max_results - len(papers))
                for r in results:
                    r["source"] = "Google-学术"
                    papers.append(r)

        return papers[:max_results]

    def search_materials(self, query: str, product_type: str = "", max_results: int = 5) -> List[Dict]:
        """原料/化学品资料搜索"""
        materials = []
        search_terms = [f"{query} TDS 技术数据表", f"{query} SDS 安全数据表"]
        if product_type:
            search_terms.append(f"{product_type} 原料 树脂 单体 光引发剂 规格")

        for term in search_terms:
            if len(materials) >= max_results:
                break
            results = self._bing_search(term, max_results - len(materials))
            for r in results:
                r["source"] = "Bing-原料"
                materials.append(r)
            if len(materials) < max_results:
                results = self._google_search(term, max_results - len(materials))
                for r in results:
                    r["source"] = "Google-原料"
                    materials.append(r)

        return materials[:max_results]

    def _bing_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Bing搜索"""
        results = []
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={max_results*2}&setlang=zh-CN"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            for item in soup.select(".b_algo"):
                if len(results) >= max_results:
                    break
                title_el = item.select_one("h2 a")
                snippet_el = item.select_one(".b_caption p")
                if title_el:
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": title_el.get("href", ""),
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        "source": "Bing"
                    })
        except Exception as e:
            print(f"Bing搜索失败: {e}")
        return results

    def _google_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Google搜索"""
        results = []
        try:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={max_results*2}&hl=zh-CN"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            for item in soup.select(".g"):
                if len(results) >= max_results:
                    break
                title_el = item.select_one("h3")
                link_el = item.select_one("a")
                snippet_el = item.select_one(".VwiC3b, .st, [style='-webkit-line-clamp:2']")
                if title_el and link_el:
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": link_el.get("href", ""),
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        "source": "Google"
                    })
        except Exception as e:
            print(f"Google搜索失败: {e}")
        return results

    def fetch_page_content(self, url: str, max_chars: int = 3000) -> str:
        """抓取网页内容"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)
            return text[:max_chars]
        except Exception as e:
            return f"抓取失败: {str(e)}"

    def _extract_patent_id(self, url: str) -> str:
        match = re.search(r'/patent/([A-Z]{2}\d+[A-Z]?)/', url)
        if match:
            return match.group(1)
        return ""


search_engine = WebSearchEngine()
