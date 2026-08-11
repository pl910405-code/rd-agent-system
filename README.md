# 绘兰材料 · 研发提效AI Agent系统

5-Agent 配方迭代闭环系统，帮助材料研发人员提效。

## 功能

- **目标性能解析** - 输入目标性能指标，自动分解为配方调整方向
- **研发知识检索** - RAG 语义搜索 + 联网搜索（专利/文献/原料）
- **候选配方生成** - 基于历史数据和知识库推荐配方方案
- **实验设计(DOE)** - 生成正交实验矩阵，人工审批后执行
- **实验复盘** - 输入实验结果，AI 评估并给出下一轮建议

## 技术栈

- **后端**: FastAPI + uvicorn
- **RAG**: TF-IDF + BM25 双引擎语义检索
- **联网搜索**: Bing 多引擎搜索
- **LLM**: 支持 OpenAI 兼容 API（DeepSeek/通义千问/智谱等）
- **前端**: 原生 HTML/CSS/JS 单页应用
- **部署**: Dockerfile + render.yaml

## 本地运行

```bash
cd backend
pip install -r requirements.txt
python server.py
# 打开 http://localhost:8000
```

## 云部署

1. 推送到 GitHub
2. 在 [Render](https://render.com) 创建 Web Service，选择此仓库
3. Render 自动构建并部署，获得公网地址

## 数据安全

- 所有文档存储在本地/服务器，不上传到第三方
- LLM API Key 存储在服务端，前端不可见
- 所有 Agent 决策点支持人工审批
