/**
 * 前端交互逻辑 v2.0 - 联网版
 * 所有Agent调用真实后端API（FastAPI）
 */

const API_BASE = ""; // 同源，无需指定base URL

// ========== 工具函数 ==========
async function api(url, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(API_BASE + url, opts);
  if (!res.ok) throw new Error(`API错误: ${res.status}`);
  return res.json();
}

function showLoading(elId, msg = "加载中...") {
  const el = document.getElementById(elId);
  if (el) el.innerHTML = `<div style="text-align:center;padding:20px;color:var(--gray-400);">⏳ ${msg}</div>`;
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ========== 全局状态 ==========
let iterState = {
  targetInput: null, targetAnalysis: null, knowledgeResults: null,
  candidates: null, doeResult: null, reviewResult: null
};

// ========== 页面切换 ==========
function switchPage(pageId, tabEl) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + pageId).classList.add('active');
  tabEl.classList.add('active');
  if (pageId === 'dashboard') initDashboard();
  if (pageId === 'knowledge') loadRAGStats();
  if (pageId === 'settings') loadLLMConfig();
}

// ========== 总览看板 ==========
async function initDashboard() {
  renderFlowDiagram();
  renderAgentCards();
  renderPermissionLists();
  renderDataSources();
  await checkHealth();
}

function renderFlowDiagram() {
  const steps = [
    {icon:'🎯',label:'目标性能输入',type:'human'},
    {icon:'🤖',label:'目标拆解',type:'agent'},
    {icon:'🔍',label:'历史检索+联网',type:'agent'},
    {icon:'🧪',label:'候选配方',type:'agent'},
    {icon:'📋',label:'DOE矩阵',type:'agent'},
    {icon:'✅',label:'人工审批',type:'human'},
    {icon:'👨‍🔬',label:'人工实验',type:'human'},
    {icon:'📝',label:'结果录入',type:'human'},
    {icon:'📈',label:'Agent评估',type:'agent'},
    {icon:'💡',label:'下一轮建议',type:'agent'},
    {icon:'👤',label:'负责人决策',type:'human'},
  ];
  let html = '';
  steps.forEach((s, i) => {
    html += `<div class="flow-step ${s.type}"><div class="circle">${s.icon}</div><div class="label">${s.label}</div><div class="type">${s.type==='agent'?'AI Agent':'人工'}</div></div>`;
    if (i < steps.length-1) html += '<div class="flow-arrow">→</div>';
  });
  document.getElementById('flow-diagram').innerHTML = html;
}

function renderAgentCards() {
  const agents = [
    {icon:'🎯',name:'目标性能解析 Agent',desc:'拆解目标性能、识别影响因素和冲突，结合RAG知识库分析'},
    {icon:'🔍',name:'研发知识检索 Agent',desc:'RAG知识库语义检索 + 联网搜索专利/文献/原料'},
    {icon:'🧪',name:'候选配方生成 Agent',desc:'基于RAG和联网搜索上下文，生成候选配方方向'},
    {icon:'📋',name:'实验设计 Agent',desc:'生成DOE实验矩阵、步骤、记录模板和风险提示'},
    {icon:'📈',name:'实验复盘 Agent',desc:'评估目标达成、分析变量影响、推荐下一轮方向'},
  ];
  document.getElementById('agent-cards').innerHTML = agents.map(a => `
    <div class="card" style="margin:0;border:1px solid var(--gray-200);">
      <div style="font-size:28px;margin-bottom:8px;">${a.icon}</div>
      <div style="font-weight:700;font-size:14px;margin-bottom:6px;">${a.name}</div>
      <div style="font-size:12px;color:var(--gray-600);line-height:1.5;">${a.desc}</div>
      <div style="margin-top:8px;"><span class="tag tag-green">不触碰设备</span></div>
    </div>`).join('');
}

function renderPermissionLists() {
  const canDo = ['检索资料（RAG知识库+联网搜索）','整理实验记录，结构化录入','生成候选配方方向和变量范围','生成实验方案草稿和DOE矩阵','推荐候选变量和关键因素','提示安全、环保、原料兼容性风险','分析实验结果，对比变量影响','生成报告和下一轮建议'];
  const cannotDo = ['自动操作实验设备','自动下发实验任务到设备','自动更改正式配方','宣称候选配方一定达标','自动批准送样','自动采购危险化学品','自动对客户承诺性能','自动判定量产导入'];
  document.getElementById('can-do-list').innerHTML = canDo.map(d=>`<div style="padding:6px 0;border-bottom:1px solid var(--gray-100);font-size:13px;">✅ ${d}</div>`).join('');
  document.getElementById('cannot-do-list').innerHTML = cannotDo.map(d=>`<div style="padding:6px 0;border-bottom:1px solid var(--gray-100);font-size:13px;color:var(--gray-600);">🚫 ${d}</div>`).join('');
}

function renderDataSources() {
  const sources = [
    {icon:'📂',name:'RAG知识库',desc:'上传的实验记录、配方、测试报告',status:'local'},
    {icon:'📜',name:'专利搜索',desc:'Google Patents + 联网搜索',status:'online'},
    {icon:'📚',name:'学术文献',desc:'论文、期刊、研究报告',status:'online'},
    {icon:'🧪',name:'原料资料',desc:'TDS/SDS、供应商信息',status:'online'},
  ];
  document.getElementById('data-sources').innerHTML = sources.map(s => `
    <div class="metric-card" style="text-align:left;">
      <div style="font-size:24px;margin-bottom:4px;">${s.icon}</div>
      <div style="font-weight:700;font-size:13px;">${s.name}</div>
      <div style="font-size:11px;color:var(--gray-500);margin-bottom:6px;">${s.desc}</div>
      <span class="tag ${s.status==='online'?'tag-green':'tag-blue'}">${s.status==='online'?'联网':'本地'}</span>
    </div>`).join('');
}

async function checkHealth() {
  try {
    const data = await api('/api/health');
    document.getElementById('stat-rag-docs').textContent = data.rag_documents || 0;
    document.getElementById('stat-rag-chunks').textContent = data.rag_chunks || 0;
    document.getElementById('stat-llm').textContent = data.llm_enabled ? '已启用' : '未启用';
    document.getElementById('stat-llm').style.color = data.llm_enabled ? 'var(--success)' : 'var(--gray-400)';
    document.getElementById('status-badge').textContent = data.llm_enabled ? `LLM: ${data.llm_model}` : '规则引擎模式';
    document.getElementById('status-badge').style.background = data.llm_enabled ? 'rgba(34,197,94,0.2)' : 'rgba(217,119,6,0.2)';
  } catch (e) {
    document.getElementById('status-badge').textContent = '后端未连接';
    document.getElementById('status-badge').style.background = 'rgba(220,38,38,0.2)';
  }
}

// ========== 配方迭代闭环 ==========
function updateStepIndicator(step) {
  const steps = ['目标输入','性能拆解','知识检索','候选配方','DOE矩阵','结果录入','评估建议'];
  let html = '';
  steps.forEach((s, i) => {
    const num = i+1;
    const isActive = num === step;
    const isDone = num < step;
    const bg = isActive ? 'var(--primary)' : (isDone ? 'var(--success)' : 'var(--gray-200)');
    const color = isActive || isDone ? 'white' : 'var(--gray-500)';
    html += `<div style="display:flex;align-items:center;gap:6px;">
      <div style="width:24px;height:24px;border-radius:50%;background:${bg};color:${color};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;">${isDone?'✓':num}</div>
      <span style="font-size:12px;color:${isActive?'var(--primary)':'var(--gray-500)'};font-weight:${isActive?'700':'400'};">${s}</span>
    </div>${i<steps.length-1?'<div style="color:var(--gray-300);">→</div>':''}`;
  });
  document.getElementById('step-indicator').innerHTML = html;
}

function showIterStep(step) {
  for (let i=1; i<=7; i++) { const el=document.getElementById('iter-step'+i); if(el) el.style.display='none'; }
  const t = document.getElementById('iter-step'+step);
  if (t) { t.style.display='block'; t.classList.add('fade-in'); }
  updateStepIndicator(step);
}

async function runTargetAnalysis() {
  const btn = document.getElementById('btn-step1');
  btn.disabled = true; btn.textContent = '⏳ Agent分析中...';
  showLoading('target-analysis-result', '正在解析目标性能（结合RAG知识库）...');
  showIterStep(2);

  iterState.targetInput = {
    productType: document.getElementById('target-product').value,
    performance: {
      transmittance: document.getElementById('t-transmittance').value,
      haze: document.getElementById('t-haze').value,
      yellowing: document.getElementById('t-yellowing').value,
      adhesion: document.getElementById('t-adhesion').value,
      viscosity: document.getElementById('t-viscosity').value,
      humidityAging: document.getElementById('t-humidity').value,
      cost: document.getElementById('t-cost').value,
    },
    constraints: { costLimit: document.getElementById('t-cost').value, bannedSubstances: ['客户禁用物质清单'], inventoryOnly: true },
    keywords: document.getElementById('t-keywords').value.split(',').map(s=>s.trim()).filter(s=>s)
  };

  try {
    const res = await api('/api/agent/target', 'POST', iterState.targetInput);
    renderTargetAnalysis(res.data);
  } catch (e) {
    document.getElementById('target-analysis-result').innerHTML = `<div class="alert alert-danger">分析失败: ${escapeHtml(e.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = '🤖 Agent解析目标性能 →';
}

function renderTargetAnalysis(data) {
  let html = '';
  
  if (data.llm_response) {
    html += `<div class="alert alert-info"><strong>LLM推理结果：</strong></div>`;
    html += `<div style="background:var(--gray-50);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;">${escapeHtml(data.llm_response)}</div>`;
    if (data.rag_context) {
      html += `<div style="margin-top:8px;font-size:12px;color:var(--gray-500);">📚 已参考RAG知识库内容</div>`;
    }
  } else {
    html += `<div class="alert alert-info">${escapeHtml(data.summary || '分析完成')}</div>`;
    if (data.rag_has_data) {
      html += `<div class="alert alert-success" style="margin-bottom:8px;">📚 已从RAG知识库检索到相关历史数据</div>`;
    }

    if (data.subGoals && data.subGoals.length > 0) {
      html += '<h4 style="margin:12px 0 8px;">目标性能拆解</h4>';
      html += '<table><thead><tr><th>目标</th><th>要求</th><th>影响因素</th></tr></thead><tbody>';
      data.subGoals.forEach(g => {
        html += `<tr><td><strong>${escapeHtml(g.name)}</strong></td><td>${escapeHtml(g.value||'-')}</td><td style="font-size:12px;">${(g.factors||[]).join('、')}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    if (data.conflicts && data.conflicts.length > 0) {
      html += '<h4 style="margin:12px 0 8px;">性能冲突识别</h4>';
      data.conflicts.forEach(c => {
        html += `<div class="alert alert-${c.severity==='高'?'danger':'warning'}" style="margin-bottom:4px;">⚠️ ${escapeHtml(c.desc)} <span class="tag tag-${c.severity==='高'?'red':'yellow'}">${c.severity}</span></div>`;
      });
    }

    if (data.constraintAnalysis && data.constraintAnalysis.length > 0) {
      html += '<h4 style="margin:12px 0 8px;">约束条件</h4>';
      data.constraintAnalysis.forEach(c => {
        html += `<div class="alert alert-${c.severity==='高'?'danger':'warning'}" style="margin-bottom:4px;"><strong>[${c.type}]</strong> ${escapeHtml(c.desc)}</div>`;
      });
    }

    if (data.questions && data.questions.length > 0) {
      html += '<h4 style="margin:12px 0 8px;">建议澄清问题</h4>';
      data.questions.forEach(q => html += `<div style="padding:4px 0;font-size:13px;color:var(--gray-600);">❓ ${escapeHtml(q)}</div>`);
    }
  }

  document.getElementById('target-analysis-result').innerHTML = html;
}

async function runKnowledgeSearch() {
  const btn = document.getElementById('btn-step2');
  btn.disabled = true; btn.textContent = '⏳ 检索中（RAG+联网）...';
  showLoading('knowledge-search-result', '正在检索RAG知识库和联网搜索...');
  showIterStep(3);

  try {
    const req = {
      productType: iterState.targetInput.productType,
      performance: iterState.targetInput.performance,
      keywords: iterState.targetInput.keywords
    };
    const res = await api('/api/agent/knowledge', 'POST', req);
    iterState.knowledgeResults = res.data;
    renderKnowledgeResults(res.data);
  } catch (e) {
    document.getElementById('knowledge-search-result').innerHTML = `<div class="alert alert-danger">检索失败: ${escapeHtml(e.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = '🔍 Agent检索历史实验+联网搜索 →';
}

function renderKnowledgeResults(data) {
  let html = `<div class="alert alert-success">RAG知识库: ${data.total_rag}条结果 | 联网搜索: ${data.total_web}条结果</div>`;

  // RAG结果
  if (data.rag_results && data.rag_results.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">📚 RAG知识库检索结果</h4>';
    html += '<table><thead><tr><th>来源</th><th>内容摘要</th><th>相似度</th></tr></thead><tbody>';
    data.rag_results.forEach(r => {
      const sc = r.score >= 0.5 ? 'score-high' : (r.score >= 0.2 ? 'score-mid' : 'score-low');
      html += `<tr><td style="font-size:12px;">${escapeHtml(r.source||'-')}</td><td style="font-size:12px;max-width:400px;">${escapeHtml((r.text||'').substring(0,200))}...</td><td><div class="score-ring ${sc}">${(r.score*100).toFixed(0)}</div></td></tr>`;
    });
    html += '</tbody></table>';
  } else {
    html += '<div class="alert alert-warning">RAG知识库暂无数据，请上传实验文档到知识库</div>';
  }

  // 联网搜索结果
  const wr = data.web_results || {};
  if (wr.patents && wr.patents.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">📜 联网搜索-专利</h4>';
    wr.patents.forEach(p => {
      if (p.error) { html += `<div class="alert alert-danger">${escapeHtml(p.error)}</div>`; return; }
      html += `<div class="card" style="margin:4px 0;border-left:3px solid var(--primary);padding:12px;">
        <div style="font-weight:700;font-size:13px;">${escapeHtml(p.title||'')}</div>
        ${p.patent_id ? `<span class="tag tag-blue">${escapeHtml(p.patent_id)}</span>` : ''}
        <div style="font-size:12px;color:var(--gray-600);margin-top:4px;">${escapeHtml(p.snippet||'')}</div>
        ${p.url ? `<a href="${escapeHtml(p.url)}" target="_blank" style="font-size:12px;color:var(--primary);">查看原文 →</a>` : ''}
      </div>`;
    });
  }
  if (wr.literature && wr.literature.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">📚 联网搜索-文献</h4>';
    wr.literature.forEach(l => {
      if (l.error) return;
      html += `<div class="card" style="margin:4px 0;border-left:3px solid var(--success);padding:12px;">
        <div style="font-weight:700;font-size:13px;">${escapeHtml(l.title||'')}</div>
        <div style="font-size:12px;color:var(--gray-600);margin-top:4px;">${escapeHtml(l.snippet||'')}</div>
        ${l.url ? `<a href="${escapeHtml(l.url)}" target="_blank" style="font-size:12px;color:var(--success);">查看原文 →</a>` : ''}
      </div>`;
    });
  }
  if (wr.materials && wr.materials.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">🧪 联网搜索-原料</h4>';
    wr.materials.forEach(m => {
      if (m.error) return;
      html += `<div class="card" style="margin:4px 0;border-left:3px solid var(--warning);padding:12px;">
        <div style="font-weight:700;font-size:13px;">${escapeHtml(m.title||'')}</div>
        <div style="font-size:12px;color:var(--gray-600);margin-top:4px;">${escapeHtml(m.snippet||'')}</div>
        ${m.url ? `<a href="${escapeHtml(m.url)}" target="_blank" style="font-size:12px;color:var(--warning);">查看原文 →</a>` : ''}
      </div>`;
    });
  }

  // 经验卡片
  if (data.experience_cards && data.experience_cards.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">💡 可复用经验卡片</h4>';
    html += '<div class="grid-2">';
    data.experience_cards.forEach(c => {
      const borderColor = c.type === 'patent' ? 'var(--primary)' : (c.type === 'literature' ? 'var(--success)' : 'var(--warning)');
      html += `<div class="card" style="margin:0;border-left:3px solid ${borderColor};">
        <div style="font-weight:700;font-size:13px;margin-bottom:4px;">${escapeHtml(c.title)}</div>
        <div style="font-size:12px;color:var(--gray-600);">${escapeHtml(c.content.substring(0,200))}</div>
        <div style="margin-top:4px;"><span class="tag tag-gray">${escapeHtml(c.source)}</span></div>
      </div>`;
    });
    html += '</div>';
  }

  document.getElementById('knowledge-search-result').innerHTML = html;
}

async function runFormulaGeneration() {
  const btn = document.getElementById('btn-step3');
  btn.disabled = true; btn.textContent = '⏳ 生成候选配方中...';
  showLoading('formula-candidates-result', '正在生成候选配方（结合RAG和联网搜索上下文）...');
  showIterStep(4);

  try {
    const res = await api('/api/agent/formula', 'POST', {
      target_analysis: iterState.targetAnalysis || iterState.targetInput,
      knowledge_results: iterState.knowledgeResults || {}
    });
    iterState.candidates = res.data;
    renderFormulaCandidates(res.data);
  } catch (e) {
    document.getElementById('formula-candidates-result').innerHTML = `<div class="alert alert-danger">生成失败: ${escapeHtml(e.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = '🧪 Agent生成候选配方 →';
}

function renderFormulaCandidates(candidates) {
  let html = '';
  candidates.forEach(c => {
    if (c.llm_response) {
      html += `<div class="candidate-card">
        <div class="header"><div class="title">LLM推理结果</div></div>
        <div style="background:var(--gray-50);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;">${escapeHtml(c.llm_response)}</div>
      </div>`;
      return;
    }
    const rateClass = c.successRate === '高' ? 'tag-green' : (c.successRate === '中' ? 'tag-yellow' : 'tag-red');
    html += `<div class="candidate-card">
      <div class="header"><div class="title">${escapeHtml(c.id||'')} · ${escapeHtml(c.type||'')}</div>
        <div><span class="tag ${rateClass}">${escapeHtml(c.estimatedCost||c.source||'')}</span></div></div>
      <div style="font-size:13px;color:var(--gray-600);margin-bottom:10px;">🎯 ${escapeHtml(c.objective||'')}</div>`;
    
    if (c.formula && c.formula.length > 0) {
      html += '<div style="margin-bottom:10px;"><strong style="font-size:13px;">配方组成：</strong><table style="margin-top:6px;"><thead><tr><th>原料</th><th>比例</th></tr></thead><tbody>';
      c.formula.forEach(f => html += `<tr><td>${escapeHtml(f.name||'')}</td><td>${escapeHtml(String(f.ratio||''))}</td></tr>`);
      html += '</tbody></table></div>';
    }
    if (c.adjustments && c.adjustments.length > 0) {
      html += '<div style="margin-bottom:10px;"><strong style="font-size:13px;">调整说明：</strong>';
      c.adjustments.forEach(a => html += `<div style="font-size:12px;padding:4px 0;color:var(--gray-600);">• ${escapeHtml(a.item||'')}: ${escapeHtml(a.change||'')} <span style="color:var(--gray-400);">(${escapeHtml(a.reason||'')})</span></div>`);
      html += '</div>';
    }
    if (c.expectedOutcome) {
      html += '<div style="margin-bottom:10px;"><strong style="font-size:13px;">预期性能：</strong><div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:6px;">';
      Object.entries(c.expectedOutcome).forEach(([k,v]) => html += `<div style="font-size:12px;padding:4px 8px;background:var(--gray-50);border-radius:4px;"><span style="color:var(--gray-400);">${escapeHtml(k)}:</span> ${escapeHtml(String(v))}</div>`);
      html += '</div></div>';
    }
    if (c.risks && c.risks.length > 0) {
      html += '<div style="margin-bottom:10px;"><strong style="font-size:13px;color:var(--danger);">风险提示：</strong>';
      c.risks.forEach(r => html += `<div style="font-size:12px;padding:2px 0;color:var(--danger);">⚠️ ${escapeHtml(r)}</div>`);
      html += '</div>';
    }
    if (c.references && c.references.length > 0) {
      html += `<div style="font-size:11px;color:var(--gray-400);">参考来源：${c.references.map(r=>escapeHtml(r)).join(', ')}</div>`;
    }
    html += '</div>';
  });
  document.getElementById('formula-candidates-result').innerHTML = html;
}

async function runDOEGeneration() {
  const btn = document.getElementById('btn-step4');
  btn.disabled = true; btn.textContent = '⏳ 生成DOE矩阵中...';
  showLoading('doe-result', '正在生成DOE实验矩阵...');
  showIterStep(5);

  try {
    const candidate = (iterState.candidates && iterState.candidates[0]) ? iterState.candidates[0] : {};
    const res = await api('/api/agent/doe', 'POST', { candidate, variables: [] });
    iterState.doeResult = res.data;
    renderDOEResult(res.data);
  } catch (e) {
    document.getElementById('doe-result').innerHTML = `<div class="alert alert-danger">生成失败: ${escapeHtml(e.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = '📋 Agent生成DOE实验矩阵 →';
}

function renderDOEResult(data) {
  let html = '';
  if (data.llm_response) {
    html += `<div style="background:var(--gray-50);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;">${escapeHtml(data.llm_response)}</div>`;
    document.getElementById('doe-result').innerHTML = html;
    return;
  }

  html += `<div class="alert alert-info">共生成${data.totalGroups||0}组实验</div>`;
  if (data.matrix && data.matrix.length > 0) {
    html += '<table><thead><tr><th>编号</th><th>名称</th><th>树脂体系</th><th>功能单体</th><th>光引发剂</th><th>偶联剂</th><th>固化能量</th><th>目标验证</th></tr></thead><tbody>';
    data.matrix.forEach(e => {
      html += `<tr><td><strong>${escapeHtml(e.id||'')}</strong></td><td>${escapeHtml(e.name||'')}</td><td>${escapeHtml(e.resin||'')}</td><td>${escapeHtml(e.monomerRatio||'')}</td><td>${escapeHtml(e.photoinitiator||'')}</td><td>${escapeHtml(e.couplingAgent||'')}</td><td>${escapeHtml(e.uvEnergy||'')}</td><td style="font-size:12px;">${escapeHtml(e.objective||'')}</td></tr>`;
    });
    html += '</tbody></table>';
  }
  if (data.testItems && data.testItems.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">测试指标</h4><table><thead><tr><th>项目</th><th>方法</th><th>标准</th></tr></thead><tbody>';
    data.testItems.forEach(t => html += `<tr><td>${escapeHtml(t.name||'')}</td><td>${escapeHtml(t.method||'')}</td><td>${escapeHtml(t.standard||'')}</td></tr>`);
    html += '</tbody></table>';
  }
  if (data.experimentSteps && data.experimentSteps.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">实验步骤</h4><div style="background:var(--gray-50);padding:12px;border-radius:8px;">';
    data.experimentSteps.forEach(s => html += `<div style="padding:4px 0;font-size:13px;">${escapeHtml(s)}</div>`);
    html += '</div>';
  }
  if (data.safetyNotes && data.safetyNotes.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">安全注意事项</h4><div class="alert alert-warning">';
    data.safetyNotes.forEach(n => html += `<div style="padding:2px 0;">⚠️ ${escapeHtml(n)}</div>`);
    html += '</div>';
  }
  document.getElementById('doe-result').innerHTML = html;
}

function showResultInput() { showIterStep(6); }

function loadSampleResults() {
  const sample = [
    {id:"E01",results:{transmittance:91.8,haze:1.2,yellowing:2.5,adhesion:8.1,viscosity:760,humidityAging:72},notes:"固化充分，轻微黄变"},
    {id:"E02",results:{transmittance:92.1,haze:1.0,yellowing:2.3,adhesion:9.4,viscosity:890,humidityAging:75},notes:"粘接改善"},
    {id:"E03",results:{transmittance:92.5,haze:0.8,yellowing:1.8,adhesion:8.9,viscosity:870,humidityAging:73},notes:"黄变改善，PI-819效果好"},
    {id:"E04",results:{transmittance:92.0,haze:0.9,yellowing:1.9,adhesion:10.1,viscosity:1040,humidityAging:82},notes:"综合最优"},
    {id:"E05",results:{transmittance:91.6,haze:1.3,yellowing:2.1,adhesion:10.5,viscosity:1300,humidityAging:84},notes:"粘度超标"},
  ];
  document.getElementById('result-input-json').value = JSON.stringify(sample, null, 2);
}

async function runExperimentReview() {
  const btn = document.getElementById('btn-step6');
  btn.disabled = true; btn.textContent = '⏳ 评估中...';
  showLoading('review-result', '正在评估实验结果...');
  showIterStep(7);

  let results;
  try { results = JSON.parse(document.getElementById('result-input-json').value); }
  catch(e) { document.getElementById('review-result').innerHTML = `<div class="alert alert-danger">JSON格式错误: ${escapeHtml(e.message)}</div>`; btn.disabled=false; btn.textContent='📈 Agent评估实验结果 →'; return; }

  try {
    const target = iterState.targetInput ? iterState.targetInput.performance : {};
    const res = await api('/api/agent/review', 'POST', { experiment_results: results, target_performance: target });
    iterState.reviewResult = res.data;
    renderReviewResult(res.data);
  } catch (e) {
    document.getElementById('review-result').innerHTML = `<div class="alert alert-danger">评估失败: ${escapeHtml(e.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = '📈 Agent评估实验结果 →';
}

function renderReviewResult(data) {
  let html = '';
  if (data.llm_response) {
    html += `<div style="background:var(--gray-50);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;">${escapeHtml(data.llm_response)}</div>`;
    document.getElementById('review-result').innerHTML = html;
    return;
  }
  html += `<div class="alert alert-success">${escapeHtml(data.summary||'评估完成')}</div>`;
  if (data.bestCandidate) {
    html += `<div class="alert alert-info"><strong>🏆 最优方案：${escapeHtml(data.bestCandidate.experimentId||'')}</strong><br>${escapeHtml(data.bestCandidate.reason||'')}</div>`;
  }
  if (data.evaluation && data.evaluation.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">目标达成评估</h4><div style="overflow-x:auto;"><table><thead><tr><th>实验编号</th>';
    const goals = data.evaluation[0].goals || [];
    goals.forEach(g => html += `<th>${escapeHtml(g.name)}</th>`);
    html += '<th>达标率</th><th>状态</th></tr></thead><tbody>';
    data.evaluation.forEach(ev => {
      html += `<tr><td><strong>${escapeHtml(ev.experimentId||'')}</strong></td>`;
      (ev.goals||[]).forEach(g => html += `<td><span class="tag ${g.met?'tag-green':'tag-red'}" style="font-size:11px;">${escapeHtml(g.actual||'')}${g.met?' ✓':' ✗'}</span></td>`);
      const sc = ev.overallStatus === '全部达标' ? 'tag-green' : (ev.overallStatus === '大部分达标' ? 'tag-yellow' : 'tag-red');
      html += `<td><strong>${escapeHtml(ev.passRate||'')}</strong></td><td><span class="tag ${sc}">${escapeHtml(ev.overallStatus||'')}</span></td></tr>`;
    });
    html += '</tbody></table></div>';
  }
  if (data.nextRoundSuggestions && data.nextRoundSuggestions.length > 0) {
    html += '<h4 style="margin:12px 0 8px;">下一轮配方调整建议</h4><div class="approval-banner"><span>👤</span><span>需研发负责人审批后执行</span></div>';
    html += '<table><thead><tr><th>编号</th><th>调整建议</th><th>目的</th><th>优先级</th></tr></thead><tbody>';
    data.nextRoundSuggestions.forEach(s => {
      html += `<tr><td><strong>${escapeHtml(s.id||'')}</strong></td><td style="font-size:13px;">${escapeHtml(s.adjustment||'')}</td><td style="font-size:13px;">${escapeHtml(s.purpose||'')}</td><td><span class="tag ${s.priority==='高'?'tag-red':'tag-yellow'}">${escapeHtml(s.priority||'')}</span></td></tr>`;
    });
    html += '</tbody></table>';
  }
  document.getElementById('review-result').innerHTML = html;
}

function resetIteration() {
  iterState = {targetInput:null,targetAnalysis:null,knowledgeResults:null,candidates:null,doeResult:null,reviewResult:null};
  showIterStep(1);
}

// ========== 知识检索页面 ==========
async function uploadFiles(files) {
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/api/rag/upload', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.status === 'success') {
        console.log('上传成功:', data.data);
      } else {
        alert(`上传失败: ${data.message}`);
      }
    } catch(e) { alert(`上传失败: ${e.message}`); }
  }
  loadRAGStats();
}

async function loadRAGStats() {
  try {
    const res = await api('/api/rag/stats');
    const stats = res.data;
    let html = `<div class="grid-3" style="margin-bottom:12px;">
      <div class="metric-card"><div class="value" style="color:var(--primary);">${stats.total_documents||0}</div><div class="label">文档数</div></div>
      <div class="metric-card"><div class="value" style="color:var(--success);">${stats.total_chunks||0}</div><div class="label">文本块</div></div>
      <div class="metric-card"><div class="value" style="color:var(--warning);">${(stats.total_chars||0).toLocaleString()}</div><div class="label">总字符数</div></div>
    </div>`;
    
    if (stats.documents && stats.documents.length > 0) {
      html += '<table><thead><tr><th>文件名</th><th>文本块数</th><th>字符数</th><th>操作</th></tr></thead><tbody>';
      stats.documents.forEach(d => {
        html += `<tr><td>${escapeHtml(d.filename)}</td><td>${d.chunks}</td><td>${d.chars}</td><td><button class="btn btn-outline btn-sm" onclick="deleteDoc('${escapeHtml(d.filename)}')">删除</button></td></tr>`;
      });
      html += '</tbody></table>';
    } else {
      html += '<div class="alert alert-warning">知识库为空，请上传文档</div>';
    }
    document.getElementById('rag-stats').innerHTML = html;
  } catch(e) {
    document.getElementById('rag-stats').innerHTML = `<div class="alert alert-danger">加载失败: ${escapeHtml(e.message)}</div>`;
  }
}

async function deleteDoc(filename) {
  if (!confirm(`确认删除 "${filename}"？`)) return;
  try {
    await api(`/api/rag/document/${encodeURIComponent(filename)}`, 'DELETE');
    loadRAGStats();
  } catch(e) { alert(`删除失败: ${e.message}`); }
}

async function runSearch() {
  const scope = document.getElementById('search-scope').value;
  const keywords = document.getElementById('search-keywords').value;
  const product = document.getElementById('search-product').value;
  const max = parseInt(document.getElementById('search-max').value);
  
  showLoading('search-results', '正在搜索...');
  
  try {
    if (scope === 'rag' || scope === 'all') {
      const ragRes = await api('/api/rag/search', 'POST', { query: keywords, top_k: max });
      if (scope === 'rag') { renderSearchResults({rag: ragRes.data, web: null}); return; }
      
      const webRes = await api('/api/search', 'POST', { query: keywords, product_type: product, search_type: scope === 'all' ? 'all' : scope, max_results: max });
      renderSearchResults({rag: ragRes.data, web: webRes.data});
    } else {
      const webRes = await api('/api/search', 'POST', { query: keywords, product_type: product, search_type: scope, max_results: max });
      renderSearchResults({rag: null, web: webRes.data});
    }
  } catch(e) {
    document.getElementById('search-results').innerHTML = `<div class="alert alert-danger">搜索失败: ${escapeHtml(e.message)}</div>`;
  }
}

function renderSearchResults(data) {
  let html = '';
  if (data.rag && data.rag.length > 0) {
    html += '<div class="card"><div class="card-title"><span class="icon">📚</span> RAG知识库结果</div>';
    html += '<table><thead><tr><th>来源</th><th>内容</th><th>相似度</th></tr></thead><tbody>';
    data.rag.forEach(r => {
      const sc = r.score >= 0.5 ? 'score-high' : (r.score >= 0.2 ? 'score-mid' : 'score-low');
      html += `<tr><td style="font-size:12px;">${escapeHtml(r.source||'-')}</td><td style="font-size:12px;max-width:500px;">${escapeHtml((r.text||'').substring(0,300))}</td><td><div class="score-ring ${sc}">${(r.score*100).toFixed(0)}</div></td></tr>`;
    });
    html += '</tbody></table></div>';
  } else if (data.rag) {
    html += '<div class="card"><div class="alert alert-warning">RAG知识库无匹配结果</div></div>';
  }
  
  if (data.web) {
    const wr = data.web;
    const sections = [
      {key:'patents', icon:'📜', name:'专利', color:'var(--primary)'},
      {key:'literature', icon:'📚', name:'文献', color:'var(--success)'},
      {key:'materials', icon:'🧪', name:'原料', color:'var(--warning)'},
      {key:'web', icon:'🌐', name:'通用', color:'var(--gray-600)'},
    ];
    sections.forEach(s => {
      const items = wr[s.key];
      if (items && items.length > 0) {
        html += `<div class="card"><div class="card-title"><span class="icon">${s.icon}</span> 联网搜索-${s.name}（${items.length}条）</div>`;
        items.forEach(item => {
          if (item.error) { html += `<div class="alert alert-danger">${escapeHtml(item.error)}</div>`; return; }
          html += `<div style="padding:10px 0;border-bottom:1px solid var(--gray-100);">
            <div style="font-weight:700;font-size:13px;">${escapeHtml(item.title||'')}</div>
            <div style="font-size:12px;color:var(--gray-600);margin-top:4px;">${escapeHtml(item.snippet||'')}</div>
            ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" style="font-size:12px;color:${s.color};">查看原文 →</a>` : ''}
          </div>`;
        });
        html += '</div>';
      }
    });
  }
  
  if (!html) html = '<div class="card"><div class="alert alert-warning">无搜索结果</div></div>';
  document.getElementById('search-results').innerHTML = html;
}

// ========== 实验设计页面 ==========
async function runDOEDesign() {
  showLoading('design-results', '正在生成DOE实验矩阵...');
  try {
    const candidate = { formula: [], objective: document.getElementById('design-desc').value };
    const res = await api('/api/agent/doe', 'POST', { candidate, variables: [] });
    renderDOEDesignResult(res.data);
  } catch(e) {
    document.getElementById('design-results').innerHTML = `<div class="alert alert-danger">生成失败: ${escapeHtml(e.message)}</div>`;
  }
}

function renderDOEDesignResult(data) {
  let html = '<div class="card">';
  if (data.llm_response) {
    html += `<div style="background:var(--gray-50);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;">${escapeHtml(data.llm_response)}</div>`;
  } else {
    html += `<div class="alert alert-info">共生成${data.totalGroups||0}组实验</div>`;
    if (data.matrix) {
      html += '<table><thead><tr><th>编号</th><th>名称</th><th>树脂</th><th>单体</th><th>引发剂</th><th>偶联剂</th><th>能量</th><th>目标</th></tr></thead><tbody>';
      data.matrix.forEach(e => html += `<tr><td><strong>${escapeHtml(e.id||'')}</strong></td><td>${escapeHtml(e.name||'')}</td><td>${escapeHtml(e.resin||'')}</td><td>${escapeHtml(e.monomerRatio||'')}</td><td>${escapeHtml(e.photoinitiator||'')}</td><td>${escapeHtml(e.couplingAgent||'')}</td><td>${escapeHtml(e.uvEnergy||'')}</td><td style="font-size:12px;">${escapeHtml(e.objective||'')}</td></tr>`);
      html += '</tbody></table>';
    }
    if (data.testItems) {
      html += '<h4 style="margin:12px 0 8px;">测试指标</h4><table><thead><tr><th>项目</th><th>方法</th><th>标准</th></tr></thead><tbody>';
      data.testItems.forEach(t => html += `<tr><td>${escapeHtml(t.name||'')}</td><td>${escapeHtml(t.method||'')}</td><td>${escapeHtml(t.standard||'')}</td></tr>`);
      html += '</tbody></table>';
    }
    if (data.experimentSteps) {
      html += '<h4 style="margin:12px 0 8px;">实验步骤</h4><div style="background:var(--gray-50);padding:12px;border-radius:8px;">';
      data.experimentSteps.forEach(s => html += `<div style="padding:4px 0;font-size:13px;">${escapeHtml(s)}</div>`);
      html += '</div>';
    }
    if (data.safetyNotes) {
      html += '<h4 style="margin:12px 0 8px;">安全注意事项</h4><div class="alert alert-warning">';
      data.safetyNotes.forEach(n => html += `<div style="padding:2px 0;">⚠️ ${escapeHtml(n)}</div>`);
      html += '</div>';
    }
  }
  html += '</div>';
  document.getElementById('design-results').innerHTML = html;
}

// ========== 实验复盘页面 ==========
function loadSampleReviewData() {
  document.getElementById('review-results').value = JSON.stringify([
    {id:"E01",results:{transmittance:91.8,haze:1.2,yellowing:2.5,adhesion:8.1,viscosity:760,humidityAging:72},notes:"固化充分，轻微黄变"},
    {id:"E02",results:{transmittance:92.1,haze:1.0,yellowing:2.3,adhesion:9.4,viscosity:890,humidityAging:75},notes:"粘接改善"},
    {id:"E03",results:{transmittance:92.5,haze:0.8,yellowing:1.8,adhesion:8.9,viscosity:870,humidityAging:73},notes:"黄变改善"},
    {id:"E04",results:{transmittance:92.0,haze:0.9,yellowing:1.9,adhesion:10.1,viscosity:1040,humidityAging:82},notes:"综合最优"},
    {id:"E05",results:{transmittance:91.6,haze:1.3,yellowing:2.1,adhesion:10.5,viscosity:1300,humidityAging:84},notes:"粘度超标"},
  ], null, 2);
}

async function runReview() {
  showLoading('review-page-results', '正在分析实验结果...');
  try {
    const target = JSON.parse(document.getElementById('review-target').value);
    const results = JSON.parse(document.getElementById('review-results').value);
    const res = await api('/api/agent/review', 'POST', { experiment_results: results, target_performance: target });
    renderReviewPageResult(res.data);
  } catch(e) {
    document.getElementById('review-page-results').innerHTML = `<div class="alert alert-danger">错误: ${escapeHtml(e.message)}</div>`;
  }
}

function renderReviewPageResult(data) {
  let html = '<div class="card">';
  if (data.llm_response) {
    html += `<div style="background:var(--gray-50);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;">${escapeHtml(data.llm_response)}</div>`;
  } else {
    html += `<div class="alert alert-success">${escapeHtml(data.summary||'')}</div>`;
    if (data.bestCandidate) html += `<div class="alert alert-info"><strong>🏆 ${escapeHtml(data.bestCandidate.experimentId||'')}</strong> ${escapeHtml(data.bestCandidate.reason||'')}</div>`;
    if (data.evaluation) {
      html += '<h4 style="margin:12px 0 8px;">目标达成评估</h4><div style="overflow-x:auto;"><table><thead><tr><th>编号</th>';
      if (data.evaluation[0] && data.evaluation[0].goals) data.evaluation[0].goals.forEach(g => html += `<th>${escapeHtml(g.name)}</th>`);
      html += '<th>达标率</th><th>状态</th></tr></thead><tbody>';
      data.evaluation.forEach(ev => {
        html += `<tr><td><strong>${escapeHtml(ev.experimentId||'')}</strong></td>`;
        (ev.goals||[]).forEach(g => html += `<td><span class="tag ${g.met?'tag-green':'tag-red'}" style="font-size:11px;">${escapeHtml(g.actual||'')}</span></td>`);
        html += `<td><strong>${escapeHtml(ev.passRate||'')}</strong></td><td><span class="tag ${ev.overallStatus==='全部达标'?'tag-green':ev.overallStatus==='大部分达标'?'tag-yellow':'tag-red'}">${escapeHtml(ev.overallStatus||'')}</span></td></tr>`;
      });
      html += '</tbody></table></div>';
    }
    if (data.nextRoundSuggestions) {
      html += '<h4 style="margin:12px 0 8px;">下一轮建议</h4><table><thead><tr><th>编号</th><th>建议</th><th>目的</th><th>优先级</th></tr></thead><tbody>';
      data.nextRoundSuggestions.forEach(s => html += `<tr><td><strong>${escapeHtml(s.id||'')}</strong></td><td style="font-size:13px;">${escapeHtml(s.adjustment||'')}</td><td style="font-size:13px;">${escapeHtml(s.purpose||'')}</td><td><span class="tag ${s.priority==='高'?'tag-red':'tag-yellow'}">${escapeHtml(s.priority||'')}</span></td></tr>`);
      html += '</tbody></table>';
    }
  }
  html += '</div>';
  document.getElementById('review-page-results').innerHTML = html;
}

// ========== LLM配置 ==========
async function saveLLMConfig() {
  const apiKey = document.getElementById('llm-api-key').value;
  const baseUrl = document.getElementById('llm-base-url').value;
  const model = document.getElementById('llm-model').value;
  const enabled = document.getElementById('llm-enabled').checked;
  
  try {
    const res = await api('/api/llm/config', 'POST', { api_key: apiKey, base_url: baseUrl, model, enabled });
    document.getElementById('llm-config-status').innerHTML = `<div class="alert alert-success">✅ LLM配置已保存，状态: ${res.llm_enabled ? '已启用' : '未启用'}</div>`;
    checkHealth();
  } catch(e) {
    document.getElementById('llm-config-status').innerHTML = `<div class="alert alert-danger">保存失败: ${escapeHtml(e.message)}</div>`;
  }
}

async function loadLLMConfig() {
  try {
    const res = await api('/api/llm/config');
    const cfg = res.data || res;
    document.getElementById('llm-base-url').value = cfg.base_url || 'https://api.openai.com/v1';
    document.getElementById('llm-model').value = cfg.model || 'gpt-4o-mini';
    document.getElementById('llm-enabled').checked = cfg.enabled || false;
    document.getElementById('llm-config-status').innerHTML = cfg.has_key 
      ? `<div class="alert alert-info">当前API Key: ${escapeHtml(cfg.api_key_preview||'')} | 模型: ${escapeHtml(cfg.model||'')} | 状态: ${cfg.enabled ? '已启用' : '未启用'}</div>`
      : `<div class="alert alert-warning">未配置API Key，当前使用规则引擎模式</div>`;
  } catch(e) {
    document.getElementById('llm-config-status').innerHTML = `<div class="alert alert-danger">加载失败: ${escapeHtml(e.message)}</div>`;
  }
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
  showIterStep(1);
});
