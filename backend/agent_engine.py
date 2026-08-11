"""
Agent推理引擎 - 5个Agent协同工作
Target Performance Agent / Knowledge Agent / Formula Agent / Design Agent / Review Agent
每个Agent优先使用RAG知识库 + 联网搜索获取真实数据，有LLM时用LLM推理，无LLM时用规则引擎
"""
import json
import re
from typing import Dict, List, Optional
from config import config
from rag_engine import rag_engine
from web_search import search_engine


class LLMClient:
    """LLM客户端，支持OpenAI兼容API"""

    def __init__(self):
        self._client = None

    def get_client(self):
        if not config.is_llm_enabled():
            return None
        if self._client is None:
            try:
                from openai import OpenAI
                llm_cfg = config.get_llm_config()
                self._client = OpenAI(
                    api_key=llm_cfg.get("api_key", ""),
                    base_url=llm_cfg.get("base_url", "https://api.openai.com/v1")
                )
            except Exception as e:
                print(f"LLM初始化失败: {e}")
                return None
        return self._client

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> Optional[str]:
        """调用LLM生成回答"""
        client = self.get_client()
        if not client:
            return None
        try:
            llm_cfg = config.get_llm_config()
            response = client.chat.completions.create(
                model=llm_cfg.get("model", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=llm_cfg.get("max_tokens", 2000)
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return None


llm_client = LLMClient()


# ================================================================
# Agent 1: 目标性能解析 Agent
# ================================================================
class TargetPerformanceAgent:
    """解析目标性能，拆解子目标，识别影响因素和冲突"""

    def analyze(self, target_input: Dict) -> Dict:
        performance = target_input.get("performance", {})
        constraints = target_input.get("constraints", {})

        # 1. 从RAG知识库检索相关历史数据
        rag_context = ""
        if rag_engine.documents:
            search_query = self._build_search_query(performance)
            rag_result = rag_engine.search_with_context(search_query, top_k=3)
            rag_context = rag_result.get("context", "")

        # 2. 尝试用LLM分析
        if config.is_llm_enabled():
            llm_result = self._llm_analyze(performance, constraints, rag_context)
            if llm_result:
                return llm_result

        # 3. 规则引擎分析（无LLM时）
        return self._rule_analyze(performance, constraints, rag_context)

    def _build_search_query(self, performance):
        parts = []
        for key, val in performance.items():
            if val:
                parts.append(f"{key} {val}")
        return " ".join(parts)

    def _llm_analyze(self, performance, constraints, rag_context):
        system_prompt = """你是一位材料研发专家，擅长分析功能性涂层和UV胶粘剂的研发目标。
请根据用户输入的目标性能，进行以下分析：
1. 将目标拆解为子目标
2. 识别每个子目标的关键影响因素
3. 识别目标之间可能存在的性能冲突
4. 分析约束条件
5. 提出需要澄清的问题

请以JSON格式返回结果，包含字段：subGoals(数组), conflicts(数组), constraintAnalysis(数组), questions(数组), summary(字符串)"""

        user_prompt = f"""目标性能：
{json.dumps(performance, ensure_ascii=False, indent=2)}

约束条件：
{json.dumps(constraints, ensure_ascii=False, indent=2)}

{'相关知识库内容：' + rag_context if rag_context else '知识库暂无数据'}

请分析以上研发目标。"""

        result = llm_client.chat(system_prompt, user_prompt, temperature=0.3)
        if result:
            return {"llm_response": result, "rag_context": rag_context, "source": "LLM"}
        return None

    def _rule_analyze(self, performance, constraints, rag_context):
        """规则引擎分析"""
        goal_map = {
            "transmittance": {"name": "高透光率", "factors": ["树脂透明性", "填料分散性", "组分相容性", "固化收缩"]},
            "haze": {"name": "低雾度", "factors": ["填料粒径", "相容性", "混合均匀度", "固化条件"]},
            "yellowing": {"name": "低黄变", "factors": ["光引发剂类型", "树脂结构", "抗氧化剂", "固化能量"]},
            "adhesion": {"name": "高粘接强度", "factors": ["官能度", "极性单体", "交联密度", "基材润湿"]},
            "viscosity": {"name": "粘度范围控制", "factors": ["树脂分子量", "稀释单体比例", "填料含量", "温度"]},
            "humidityAging": {"name": "耐湿热老化", "factors": ["树脂耐水解性", "交联密度", "偶联剂", "界面稳定性"]},
            "cost": {"name": "成本控制", "factors": ["高价树脂比例", "助剂成本", "国产替代"]},
        }

        sub_goals = []
        for key, val in performance.items():
            if val and key in goal_map:
                sub_goals.append({
                    "key": key,
                    "name": goal_map[key]["name"],
                    "value": val,
                    "factors": goal_map[key]["factors"]
                })

        # 冲突识别
        conflict_pairs = [
            {"goals": ["transmittance", "haze"], "desc": "增强填料或高官能组分可能影响雾度", "severity": "中"},
            {"goals": ["yellowing", "adhesion"], "desc": "固化速度和低黄变可能冲突", "severity": "中"},
            {"goals": ["adhesion", "viscosity"], "desc": "高交联密度提升粘接但可能导致粘度上升", "severity": "高"},
            {"goals": ["humidityAging", "cost"], "desc": "耐湿热提升需高官能树脂，可能增加成本", "severity": "中"},
            {"goals": ["viscosity", "adhesion"], "desc": "降粘可能牺牲强度或耐候性", "severity": "高"},
        ]
        conflicts = []
        for pair in conflict_pairs:
            if performance.get(pair["goals"][0]) and performance.get(pair["goals"][1]):
                conflicts.append(pair)

        # 约束分析
        constraint_analysis = []
        if constraints.get("bannedSubstances"):
            constraint_analysis.append({"type": "禁用物质", "severity": "高", "desc": "客户禁用物质清单将作为硬约束"})
        if constraints.get("costLimit"):
            constraint_analysis.append({"type": "成本约束", "severity": "中", "desc": f"成本上限: {constraints['costLimit']}"})
        if constraints.get("inventoryOnly"):
            constraint_analysis.append({"type": "原料约束", "severity": "中", "desc": "仅使用现有库存原料"})

        # 澄清问题
        questions = []
        if not performance.get("humidityAging"):
            questions.append("是否有耐湿热老化要求（如85℃/85%RH测试条件）？")
        if not constraints.get("deadline"):
            questions.append("客户交付时间节点是什么？")
        if not constraints.get("bannedSubstances"):
            questions.append("客户是否有禁用物质清单需要遵守？")

        summary = f"目标性能已拆解为{len(sub_goals)}个子目标"
        if conflicts:
            summary += f"，识别到{len(conflicts)}组性能冲突"
        if rag_context:
            summary += "，已从知识库检索到相关历史数据"

        return {
            "subGoals": sub_goals,
            "conflicts": conflicts,
            "constraintAnalysis": constraint_analysis,
            "questions": questions,
            "summary": summary,
            "rag_context": rag_context[:500] if rag_context else "",
            "rag_has_data": bool(rag_context),
            "source": "规则引擎"
        }


# ================================================================
# Agent 2: 研发知识检索 Agent
# ================================================================
class KnowledgeAgent:
    """从RAG知识库和联网搜索中检索相关信息"""

    def search(self, query: Dict) -> Dict:
        product_type = query.get("productType", "")
        performance = query.get("performance", {})
        keywords = query.get("keywords", [])
        search_query = " ".join([product_type] + [f"{k} {v}" for k, v in performance.items()] + keywords)

        # 1. RAG知识库检索
        rag_results = []
        if rag_engine.documents:
            rag_results = rag_engine.search(search_query, top_k=5)

        # 2. 联网搜索
        web_query = f"{product_type} {' '.join(keywords)}" if keywords else product_type
        if not web_query:
            web_query = search_query
        web_results = search_engine.search_all(web_query, product_type, max_results=3)

        # 3. 生成经验卡片
        experience_cards = self._generate_experience_cards(rag_results, web_results)

        return {
            "rag_results": rag_results,
            "web_results": web_results,
            "experience_cards": experience_cards,
            "total_rag": len(rag_results),
            "total_web": web_results.get("total", 0),
            "search_query": search_query
        }

    def _generate_experience_cards(self, rag_results, web_results):
        cards = []
        # 从RAG结果生成
        for r in rag_results[:3]:
            cards.append({
                "title": f"知识库: {r.get('source', '未知')}",
                "content": r.get("text", "")[:300],
                "score": r.get("score", 0),
                "source": "RAG知识库",
                "type": "internal"
            })
        # 从联网搜索生成
        for pat in web_results.get("patents", [])[:2]:
            if "error" not in pat:
                cards.append({
                    "title": f"专利: {pat.get('title', '')}",
                    "content": pat.get("snippet", "")[:300],
                    "url": pat.get("url", ""),
                    "source": "联网搜索-专利",
                    "type": "patent"
                })
        for lit in web_results.get("literature", [])[:2]:
            if "error" not in lit:
                cards.append({
                    "title": f"文献: {lit.get('title', '')}",
                    "content": lit.get("snippet", "")[:300],
                    "url": lit.get("url", ""),
                    "source": "联网搜索-文献",
                    "type": "literature"
                })
        return cards


# ================================================================
# Agent 3: 候选配方生成 Agent
# ================================================================
class FormulaAgent:
    """基于RAG和联网搜索生成候选配方方向"""

    def generate_candidates(self, target_analysis: Dict, knowledge_results: Dict) -> List[Dict]:
        # 收集上下文
        rag_context = ""
        if knowledge_results.get("rag_results"):
            rag_context = "\n".join([r["text"][:500] for r in knowledge_results["rag_results"][:3]])

        web_context = ""
        if knowledge_results.get("web_results"):
            wr = knowledge_results["web_results"]
            for pat in wr.get("patents", [])[:2]:
                if "error" not in pat:
                    web_context += f"\n专利: {pat.get('title', '')} - {pat.get('snippet', '')[:200]}"

        # 尝试用LLM生成
        if config.is_llm_enabled():
            llm_result = self._llm_generate(target_analysis, rag_context, web_context)
            if llm_result:
                return llm_result

        # 规则引擎生成
        return self._rule_generate(target_analysis, rag_context, web_context)

    def _llm_generate(self, target_analysis, rag_context, web_context):
        system_prompt = """你是一位资深材料配方研发专家，擅长UV固化胶粘剂、光学膜涂层等功能性材料的配方设计。
请根据目标性能分析和相关知识数据，生成3个候选配方方向：
1. 方案A - 稳妥型：基于历史最优配方小幅调整
2. 方案B - 性能突破型：针对短板性能进行突破
3. 方案C - 成本优化型：在满足基本性能前提下控制成本

每个方案需包含：配方组成(原料名称和比例)、调整说明、预期性能、风险提示、参考来源。
请以JSON数组格式返回，每个方案包含字段：id, type, objective, formula(数组), adjustments(数组), expectedOutcome(对象), risks(数组), references(数组)"""

        user_prompt = f"""目标性能分析：
{json.dumps(target_analysis, ensure_ascii=False, indent=2)[:2000]}

RAG知识库相关内容：
{rag_context[:1000] if rag_context else '知识库暂无数据'}

联网搜索结果：
{web_context[:1000] if web_context else '暂无联网搜索结果'}

请基于以上信息生成3个候选配方方向。注意：所有建议必须引用来源，不能编造数据。"""

        result = llm_client.chat(system_prompt, user_prompt, temperature=0.5)
        if result:
            return [{"llm_response": result, "source": "LLM"}]
        return None

    def _rule_generate(self, target_analysis, rag_context, web_context):
        """规则引擎生成候选配方"""
        candidates = []

        # 方案A: 稳妥型
        candidates.append({
            "id": "CAND-A",
            "type": "稳妥型",
            "objective": "基于历史经验小幅调整，快速验证",
            "formula": [
                {"name": "脂肪族聚氨酯丙烯酸酯树脂A", "ratio": "40-45%"},
                {"name": "IBOA(丙烯酸异冰片酯)", "ratio": "20-25%"},
                {"name": "TPGDA(三丙二醇二丙烯酸酯)", "ratio": "10-15%"},
                {"name": "光引发剂PI-819", "ratio": "1.5-2.5%"},
                {"name": "硅烷偶联剂KH-570", "ratio": "0.5-0.8%"},
                {"name": "抗氧化剂BHT", "ratio": "0.3%"},
            ],
            "adjustments": [
                {"item": "光引发剂", "change": "优先选用PI-819(低黄变型)", "reason": "降低黄变指数"},
                {"item": "偶联剂", "change": "0.5%→0.8%", "reason": "提升耐湿热保持率"},
            ],
            "expectedOutcome": {
                "transmittance": "≥92%",
                "yellowing": "ΔYI≤2.0",
                "adhesion": "≥8MPa",
                "viscosity": "900-1100cps",
                "note": "基于规则推理和历史经验，具体性能需实验验证"
            },
            "risks": ["实际性能需实验验证", "配方比例为建议范围，需DOE优化"],
            "references": ["规则引擎推理", "RAG知识库" if rag_context else "无知识库数据", "联网搜索" if web_context else "无联网数据"],
            "source": "规则引擎"
        })

        # 方案B: 性能突破型
        candidates.append({
            "id": "CAND-B",
            "type": "性能突破型",
            "objective": "引入高官能度树脂提升耐湿热和粘接强度",
            "formula": [
                {"name": "脂肪族聚氨酯丙烯酸酯树脂A", "ratio": "30-35%"},
                {"name": "高官能度树脂B(官能度≥3)", "ratio": "10-15%"},
                {"name": "IBOA", "ratio": "25-28%"},
                {"name": "光引发剂TPO-L(低黄变)", "ratio": "2-3%"},
                {"name": "硅烷偶联剂KH-602", "ratio": "0.8-1.0%"},
                {"name": "UV吸收剂UV-328", "ratio": "0.3-0.5%"},
                {"name": "BHT", "ratio": "0.3%"},
            ],
            "adjustments": [
                {"item": "引入高官能树脂", "change": "添加10-15%高官能度树脂", "reason": "提升交联密度和耐湿热"},
                {"item": "光引发剂升级", "change": "PI-819→TPO-L", "reason": "进一步降低黄变"},
                {"item": "新增UV吸收剂", "change": "添加0.3-0.5% UV-328", "reason": "提升长期耐候性"},
            ],
            "expectedOutcome": {
                "transmittance": "≥91.5%(可能略降)",
                "yellowing": "ΔYI≤1.5",
                "adhesion": "≥10MPa",
                "viscosity": "1000-1300cps",
                "humidityAging": "≥85%",
                "note": "性能上限更高，但粘度可能超标"
            },
            "risks": ["粘度可能超出目标范围", "透光率可能略降", "成本上升约15-20%"],
            "references": ["规则引擎推理", "RAG知识库" if rag_context else "无知识库数据", "联网专利" if web_context else "无联网数据"],
            "source": "规则引擎"
        })

        # 方案C: 成本优化型
        candidates.append({
            "id": "CAND-C",
            "type": "成本优化型",
            "objective": "使用国产替代原料控制成本",
            "formula": [
                {"name": "环氧丙烯酸酯树脂C(国产)", "ratio": "30-35%"},
                {"name": "树脂A(国产)", "ratio": "12-15%"},
                {"name": "TPGDA(国产)", "ratio": "18-22%"},
                {"name": "IBOA", "ratio": "15-18%"},
                {"name": "光引发剂PI-1173(国产)", "ratio": "2.5-3.5%"},
                {"name": "偶联剂KH-570", "ratio": "0.5-0.6%"},
                {"name": "BHT", "ratio": "0.3%"},
            ],
            "adjustments": [
                {"item": "主树脂替换", "change": "进口树脂→国产环氧丙烯酸酯", "reason": "降低成本约40%"},
                {"item": "光引发剂", "change": "PI-819→PI-1173(国产)", "reason": "降低引发剂成本约50%"},
                {"item": "单体减量", "change": "IBOA 25%→15-18%", "reason": "减少高价进口单体"},
            ],
            "expectedOutcome": {
                "transmittance": "≥92%",
                "yellowing": "ΔYI≈2.5-3.0(可能偏高)",
                "adhesion": "≥8MPa",
                "viscosity": "800-1000cps",
                "humidityAging": "≥75%(可能不足)",
                "cost": "预计降本20-30%",
                "note": "成本优势明显，但黄变和耐湿热可能不达标"
            },
            "risks": ["黄变可能超标(PI-1173黄变倾向中等)", "耐湿热保持率可能不足80%", "长期稳定性需验证"],
            "references": ["规则引擎推理", "国产替代策略"],
            "source": "规则引擎"
        })

        return candidates


# ================================================================
# Agent 4: 实验设计 Agent
# ================================================================
class ExperimentDesignAgent:
    """生成DOE实验矩阵、实验步骤和记录模板"""

    def generate_doe(self, candidate: Dict, variables: List = None) -> Dict:
        # 尝试用LLM生成
        if config.is_llm_enabled():
            llm_result = self._llm_generate(candidate)
            if llm_result:
                return llm_result

        # 规则引擎生成
        return self._rule_generate(candidate)

    def _llm_generate(self, candidate):
        system_prompt = """你是一位材料实验设计专家，擅长DOE实验设计。
请根据候选配方生成一个DOE实验矩阵，包含5-8组实验。
每组实验需包含：编号、名称、树脂体系、功能单体比例、光引发剂、偶联剂、固化能量、目标验证。
同时提供测试指标、实验步骤、安全注意事项。
以JSON格式返回。"""

        user_prompt = f"""候选配方信息：
{json.dumps(candidate, ensure_ascii=False, indent=2)[:2000]}

请生成DOE实验矩阵。"""

        result = llm_client.chat(system_prompt, user_prompt, temperature=0.5)
        if result:
            return {"llm_response": result, "source": "LLM"}
        return None

    def _rule_generate(self, candidate):
        matrix = [
            {"id": "E01", "name": "对照组", "resin": "基准树脂A", "monomerRatio": "中比例(25%)",
             "photoinitiator": "PI-1173", "couplingAgent": "0.5%", "uvEnergy": "标准(800mJ/cm²)",
             "objective": "对照组，验证基准配方性能"},
            {"id": "E02", "name": "单体影响验证", "resin": "基准树脂A", "monomerRatio": "高比例(30%)",
             "photoinitiator": "PI-1173", "couplingAgent": "0.5%", "uvEnergy": "标准(800mJ/cm²)",
             "objective": "验证功能单体对粘接强度的影响"},
            {"id": "E03", "name": "黄变改善验证", "resin": "基准树脂A", "monomerRatio": "中比例(25%)",
             "photoinitiator": "PI-819", "couplingAgent": "0.5%", "uvEnergy": "标准(800mJ/cm²)",
             "objective": "验证PI-819对黄变的改善效果"},
            {"id": "E04", "name": "综合优化", "resin": "树脂A+B(9:1)", "monomerRatio": "中比例(25%)",
             "photoinitiator": "PI-819", "couplingAgent": "0.8%", "uvEnergy": "标准(800mJ/cm²)",
             "objective": "验证耐湿热和粘接综合效果"},
            {"id": "E05", "name": "固化窗口验证", "resin": "树脂A+B(9:1)", "monomerRatio": "高比例(30%)",
             "photoinitiator": "PI-819", "couplingAgent": "0.8%", "uvEnergy": "高能量(1200mJ/cm²)",
             "objective": "验证固化窗口与粘度风险"},
        ]

        return {
            "factors": [
                {"name": "树脂体系", "levels": ["基准树脂A", "树脂A+B(9:1)", "树脂A+B(8:2)"]},
                {"name": "功能单体比例", "levels": ["低(18%)", "中(25%)", "高(30%)"]},
                {"name": "光引发剂类型", "levels": ["PI-1173", "PI-819", "TPO-L"]},
                {"name": "偶联剂比例", "levels": ["0.5%", "0.8%", "1.0%"]},
            ],
            "matrix": matrix,
            "totalGroups": len(matrix),
            "testItems": [
                {"name": "透光率", "method": "UV-Vis分光光度计", "standard": "GB/T 2410"},
                {"name": "雾度", "method": "雾度计", "standard": "GB/T 2410"},
                {"name": "黄变指数", "method": "色差仪", "standard": "ASTM E313"},
                {"name": "粘接强度", "method": "万能拉力机", "standard": "GB/T 7124"},
                {"name": "粘度", "method": "旋转粘度计", "standard": "GB/T 2794"},
                {"name": "耐湿热老化", "method": "85℃/85%RH 500h", "standard": "GB/T 1740"},
            ],
            "experimentSteps": [
                "1. 按配方比例称量各组分原料，精度±0.1g",
                "2. 在避光条件下混合树脂和单体，搅拌10分钟至均匀",
                "3. 加入光引发剂和助剂，继续搅拌5分钟",
                "4. 真空脱泡5分钟，排除气泡",
                "5. 将胶液涂布于基材上，控制厚度",
                "6. 使用UV固化设备按设定能量固化",
                "7. 固化后样品在室温放置24h后进行测试",
                "8. 按测试标准进行各项性能测试",
                "9. 记录所有数据和观察现象",
            ],
            "safetyNotes": [
                "操作时佩戴防护眼镜和手套",
                "UV固化设备需屏蔽紫外光泄漏",
                "确保通风良好，控制VOCs排放",
                "PI-819为粉末状，需注意粉尘防护",
            ],
            "approvalRequired": True,
            "source": "规则引擎"
        }


# ================================================================
# Agent 5: 实验复盘 Agent
# ================================================================
class ExperimentReviewAgent:
    """评估实验结果，分析变量影响，推荐下一轮方向"""

    def review(self, experiment_results: List[Dict], target_performance: Dict) -> Dict:
        # 尝试用LLM分析
        if config.is_llm_enabled():
            llm_result = self._llm_review(experiment_results, target_performance)
            if llm_result:
                return llm_result

        # 规则引擎分析
        return self._rule_review(experiment_results, target_performance)

    def _llm_review(self, results, target):
        system_prompt = """你是一位材料研发数据分析专家。
请分析实验结果，评估目标达成情况，识别关键变量影响，推荐下一轮配方调整方向。
以JSON格式返回，包含：evaluation(数组), bestCandidate(对象), variableAnalysis(数组), nextRoundSuggestions(数组), summary(字符串)"""

        user_prompt = f"""实验结果：
{json.dumps(results, ensure_ascii=False, indent=2)[:3000]}

目标性能：
{json.dumps(target, ensure_ascii=False, indent=2)}

请分析实验结果并给出下一轮建议。"""

        result = llm_client.chat(system_prompt, user_prompt, temperature=0.3)
        if result:
            return {"llm_response": result, "source": "LLM"}
        return None

    def _rule_review(self, results, target):
        if not results:
            return {"error": "无实验结果数据"}

        # 评估每条实验
        evaluations = []
        for exp in results:
            exp_results = exp.get("results", {})
            goals = []
            met_count = 0

            checks = [
                ("transmittance", "透光率", exp_results.get("transmittance"), target.get("transmittance"), ">="),
                ("haze", "雾度", exp_results.get("haze"), target.get("haze"), "<="),
                ("yellowing", "黄变指数", exp_results.get("yellowing"), target.get("yellowing"), "<="),
                ("adhesion", "粘接强度", exp_results.get("adhesion"), target.get("adhesion"), ">="),
                ("humidityAging", "耐湿热保持率", exp_results.get("humidityAging"), target.get("humidityAging"), ">="),
            ]

            for key, name, actual, target_val, op in checks:
                if actual is not None and target_val:
                    target_num = float(re.search(r'[\d.]+', str(target_val)).group()) if re.search(r'[\d.]+', str(target_val)) else 0
                    met = (actual >= target_num) if op == ">=" else (actual <= target_num)
                    if met:
                        met_count += 1
                    goals.append({"name": name, "target": str(target_val), "actual": str(actual), "met": met})

            total = len(goals)
            evaluations.append({
                "experimentId": exp.get("id", ""),
                "goals": goals,
                "metCount": met_count,
                "totalCount": total,
                "passRate": f"{met_count}/{total}" if total > 0 else "0/0",
                "overallStatus": "全部达标" if met_count == total and total > 0 else ("大部分达标" if met_count >= total * 0.7 else "部分达标"),
                "notes": exp.get("notes", "")
            })

        # 找最优
        best = max(evaluations, key=lambda e: e["metCount"]) if evaluations else None

        # 下一轮建议
        suggestions = []
        if best and best["metCount"] < best["totalCount"]:
            unmet = [g for g in best["goals"] if not g["met"]]
            for g in unmet:
                if "黄变" in g["name"]:
                    suggestions.append({"id": f"N{len(suggestions)+1:02d}", "adjustment": "将光引发剂更换为TPO-L或复配方案", "purpose": "降低黄变指数", "priority": "高"})
                elif "耐湿热" in g["name"]:
                    suggestions.append({"id": f"N{len(suggestions)+1:02d}", "adjustment": "增加高官能度树脂比例或偶联剂用量", "purpose": "提升耐湿热保持率", "priority": "高"})
                elif "粘度" in g["name"]:
                    suggestions.append({"id": f"N{len(suggestions)+1:02d}", "adjustment": "降低高粘组分比例，增加稀释单体", "purpose": "控制粘度在目标范围", "priority": "高"})
                elif "透光率" in g["name"]:
                    suggestions.append({"id": f"N{len(suggestions)+1:02d}", "adjustment": "优化树脂组合和分散工艺", "purpose": "提升透光率", "priority": "中"})

        if not suggestions:
            suggestions.append({"id": "N01", "adjustment": "以最优方案为中心微调", "purpose": "综合优化寻找最佳平衡点", "priority": "中"})

        summary = f"共评估{len(evaluations)}组实验"
        if best:
            summary += f"，最优方案达标率{best['passRate']}"
        if suggestions:
            summary += f"，生成{len(suggestions)}条下一轮调整建议"

        return {
            "evaluation": evaluations,
            "bestCandidate": {"experimentId": best["experimentId"], "reason": best["notes"]} if best else None,
            "nextRoundSuggestions": suggestions,
            "summary": summary,
            "source": "规则引擎"
        }


# ================================================================
# Agent编排器
# ================================================================
class AgentOrchestrator:
    """Agent编排器，协调5个Agent的工作流"""

    def __init__(self):
        self.target_agent = TargetPerformanceAgent()
        self.knowledge_agent = KnowledgeAgent()
        self.formula_agent = FormulaAgent()
        self.design_agent = ExperimentDesignAgent()
        self.review_agent = ExperimentReviewAgent()

    def run_full_iteration(self, target_input: Dict) -> Dict:
        """运行完整的配方迭代闭环"""
        # Step 1: 目标性能解析
        target_analysis = self.target_agent.analyze(target_input)

        # Step 2: 知识检索
        knowledge_query = {
            "productType": target_input.get("productType", ""),
            "performance": target_input.get("performance", {}),
            "keywords": target_input.get("keywords", [])
        }
        knowledge_results = self.knowledge_agent.search(knowledge_query)

        # Step 3: 候选配方生成
        candidates = self.formula_agent.generate_candidates(target_analysis, knowledge_results)

        # Step 4: DOE生成（使用第一个候选方案）
        doe_result = self.design_agent.generate_doe(candidates[0] if candidates else {})

        return {
            "step1_target_analysis": target_analysis,
            "step2_knowledge": knowledge_results,
            "step3_candidates": candidates,
            "step4_doe": doe_result,
            "llm_enabled": config.is_llm_enabled()
        }


# 全局Agent编排器
orchestrator = AgentOrchestrator()
