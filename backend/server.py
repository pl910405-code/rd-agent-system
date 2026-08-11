"""
FastAPI服务器 - 研发提效AI Agent系统
提供REST API：联网搜索、RAG知识库、Agent推理、文件上传、LLM配置
同时提供静态前端文件服务
"""
import os
import sys
import shutil
import uvicorn
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# 确保backend目录在path中
sys.path.insert(0, os.path.dirname(__file__))

from config import config
from rag_engine import rag_engine
from web_search import search_engine
from agent_engine import orchestrator, TargetPerformanceAgent, KnowledgeAgent, FormulaAgent, ExperimentDesignAgent, ExperimentReviewAgent
from doc_processor import doc_processor

# 路径
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="绘兰材料研发提效AI Agent", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
# 请求模型
# ================================================================
class SearchRequest(BaseModel):
    query: str
    product_type: str = ""
    search_type: str = "all"  # all / patents / literature / materials / web
    max_results: int = 5

class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = 5

class TargetAnalysisRequest(BaseModel):
    productType: str = "UV固化胶"
    performance: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    keywords: List[str] = []

class KnowledgeSearchRequest(BaseModel):
    productType: str = "UV固化胶"
    performance: Dict[str, Any] = {}
    keywords: List[str] = []

class FormulaRequest(BaseModel):
    target_analysis: Dict[str, Any] = {}
    knowledge_results: Dict[str, Any] = {}

class DOERequest(BaseModel):
    candidate: Dict[str, Any] = {}
    variables: List[Any] = []

class ReviewRequest(BaseModel):
    experiment_results: List[Dict[str, Any]] = []
    target_performance: Dict[str, Any] = {}

class LLMConfigRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    enabled: Optional[bool] = None

class FullIterationRequest(BaseModel):
    productType: str = "UV固化胶"
    performance: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    keywords: List[str] = []


# ================================================================
# API端点
# ================================================================

@app.get("/api/health")
async def health():
    return {
        "status": "running",
        "version": "2.0",
        "llm_enabled": config.is_llm_enabled(),
        "llm_model": config.get_llm_config().get("model", ""),
        "rag_documents": len(rag_engine.doc_metadata),
        "rag_chunks": len(rag_engine.documents)
    }

# --- 联网搜索 ---
@app.post("/api/search")
async def search(req: SearchRequest):
    """联网搜索：专利/文献/原料/通用"""
    try:
        if req.search_type == "all":
            results = search_engine.search_all(req.query, req.product_type, req.max_results)
        elif req.search_type == "patents":
            results = {"patents": search_engine.search_patents(req.query, req.product_type, req.max_results)}
        elif req.search_type == "literature":
            results = {"literature": search_engine.search_literature(req.query, req.max_results)}
        elif req.search_type == "materials":
            results = {"materials": search_engine.search_materials(req.query, req.product_type, req.max_results)}
        else:
            results = {"web": search_engine.search_web(req.query, req.max_results)}
        return {"status": "success", "data": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/search/fetch")
async def fetch_page(url: str = ""):
    """抓取网页内容"""
    if not url:
        raise HTTPException(status_code=400, detail="URL不能为空")
    content = search_engine.fetch_page_content(url)
    return {"url": url, "content": content}

# --- RAG知识库 ---
@app.post("/api/rag/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档到RAG知识库"""
    try:
        # 检查文件类型
        ext = Path(file.filename).suffix.lower()
        if ext not in doc_processor.SUPPORTED_TYPES:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}，支持: {doc_processor.SUPPORTED_TYPES}")

        # 保存文件
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 处理并索引
        result = rag_engine.add_document(str(file_path))
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/rag/search")
async def rag_search(req: RAGSearchRequest):
    """RAG知识库语义检索"""
    results = rag_engine.search(req.query, req.top_k)
    return {"status": "success", "data": results, "total": len(results)}

@app.get("/api/rag/documents")
async def get_documents():
    """获取知识库文档列表"""
    return {"status": "success", "data": rag_engine.get_documents()}

@app.get("/api/rag/stats")
async def rag_stats():
    """获取知识库统计"""
    return {"status": "success", "data": rag_engine.get_stats()}

@app.delete("/api/rag/document/{filename}")
async def delete_document(filename: str):
    """删除知识库文档"""
    result = rag_engine.remove_document(filename)
    return {"status": "success", "data": result}

# --- Agent API ---
@app.post("/api/agent/target")
async def agent_target_analysis(req: TargetAnalysisRequest):
    """目标性能解析Agent"""
    target_input = {
        "productType": req.productType,
        "performance": req.performance,
        "constraints": req.constraints,
        "keywords": req.keywords
    }
    result = orchestrator.target_agent.analyze(target_input)
    return {"status": "success", "data": result}

@app.post("/api/agent/knowledge")
async def agent_knowledge_search(req: KnowledgeSearchRequest):
    """研发知识检索Agent"""
    query = {
        "productType": req.productType,
        "performance": req.performance,
        "keywords": req.keywords
    }
    result = orchestrator.knowledge_agent.search(query)
    return {"status": "success", "data": result}

@app.post("/api/agent/formula")
async def agent_formula_generation(req: FormulaRequest):
    """候选配方生成Agent"""
    result = orchestrator.formula_agent.generate_candidates(req.target_analysis, req.knowledge_results)
    return {"status": "success", "data": result}

@app.post("/api/agent/doe")
async def agent_doe_generation(req: DOERequest):
    """实验设计Agent"""
    result = orchestrator.design_agent.generate_doe(req.candidate, req.variables)
    return {"status": "success", "data": result}

@app.post("/api/agent/review")
async def agent_experiment_review(req: ReviewRequest):
    """实验复盘Agent"""
    result = orchestrator.review_agent.review(req.experiment_results, req.target_performance)
    return {"status": "success", "data": result}

@app.post("/api/agent/full-iteration")
async def agent_full_iteration(req: FullIterationRequest):
    """完整配方迭代闭环"""
    target_input = {
        "productType": req.productType,
        "performance": req.performance,
        "constraints": req.constraints,
        "keywords": req.keywords
    }
    result = orchestrator.run_full_iteration(target_input)
    return {"status": "success", "data": result}

# --- LLM配置 ---
@app.post("/api/llm/config")
async def set_llm_config(req: LLMConfigRequest):
    """配置LLM API"""
    config.set_llm_config(
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
        enabled=req.enabled
    )
    return {"status": "success", "llm_enabled": config.is_llm_enabled()}

@app.get("/api/llm/config")
async def get_llm_config():
    """获取LLM配置状态"""
    llm_cfg = config.get_llm_config()
    return {
        "status": "success",
        "enabled": llm_cfg.get("enabled", False),
        "model": llm_cfg.get("model", ""),
        "base_url": llm_cfg.get("base_url", ""),
        "has_key": bool(llm_cfg.get("api_key", "")),
        "api_key_preview": llm_cfg.get("api_key", "")[:8] + "..." if llm_cfg.get("api_key") else ""
    }


# ================================================================
# 静态文件服务（前端）
# ================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


# ================================================================
# 启动
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  绘兰材料 · 研发提效AI Agent系统 v2.0")
    print("  联网搜索 + RAG知识库 + LLM推理")
    print("=" * 60)
    print(f"  LLM状态: {'已启用' if config.is_llm_enabled() else '未启用(使用规则引擎)'}")
    print(f"  知识库: {len(rag_engine.doc_metadata)}个文档, {len(rag_engine.documents)}个文本块")
    print(f"  服务地址: http://localhost:8000")
    print("=" * 60)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
