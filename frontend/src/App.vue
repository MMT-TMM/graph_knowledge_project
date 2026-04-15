<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const STORAGE_KEY = 'kg_workspaces_v1'

const tabOptions = [
  { key: 'graph', label: '图谱' },
  { key: 'upload', label: '上传' },
  { key: 'qa', label: '问答' },
  { key: 'api', label: 'API' },
]

const activeTab = ref('graph')
const workspaceNameInput = ref('')
const workspaces = ref([])
const selectedWorkspaceId = ref('')

const serverGraphs = ref([])

const textInput = ref('')
const imageFiles = ref([])
const pdfFiles = ref([])
const imagePreviewUrls = ref([])
const pdfPreviewUrls = ref([])

const modelName = ref('gpt-4.1-mini')
const apiKey = ref('')
const baseUrl = ref('')
const extractPrompt = ref('')
const qaPrompt = ref('')

const qaQuestion = ref('')

const loading = ref(false)
const qaLoading = ref(false)
const errorMessage = ref('')

const result = ref(null)

const chartEl = ref(null)
let chartInstance = null

const entityColors = {
  ArchitecturalComponent: '#4E79A7',
  Material: '#59A14F',
  Defect: '#E15759',
  Event: '#F28E2B',
  Dynasty: '#B07AA1',
  Literal: '#9C755F',
}

const selectedWorkspace = computed(() => workspaces.value.find((w) => w.id === selectedWorkspaceId.value) || null)

const qaMessages = computed(() => {
  const ws = selectedWorkspace.value
  return ws?.qa_messages ?? []
})

const hasAnyInput = computed(() => {
  return Boolean(textInput.value.trim()) || imageFiles.value.length > 0 || pdfFiles.value.length > 0
})

const canAsk = computed(() => {
  return Boolean(selectedWorkspace.value?.graph_id) && Boolean(qaQuestion.value.trim()) && !qaLoading.value
})

function persistWorkspaces() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(workspaces.value))
}

watch(workspaces, persistWorkspaces, { deep: true })

function hydrateWorkspaces() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      workspaces.value = parsed
    }
  } catch {
    workspaces.value = []
  }
}

function createWorkspace(name) {
  const finalName = (name || '').trim() || `图谱_${Date.now()}`
  const ws = {
    id: `ws_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    name: finalName,
    graph_id: '',
    graph_path: '',
    entity_count: 0,
    triple_count: 0,
    updated_at: new Date().toISOString(),
    qa_messages: [],
  }
  workspaces.value.unshift(ws)
  selectedWorkspaceId.value = ws.id
  return ws
}

function createWorkspaceByInput() {
  const ws = createWorkspace(workspaceNameInput.value)
  workspaceNameInput.value = ''
  activeTab.value = 'upload'
  return ws
}

function selectWorkspace(id) {
  selectedWorkspaceId.value = id
}

function removeWorkspace(id) {
  workspaces.value = workspaces.value.filter((w) => w.id !== id)
  if (selectedWorkspaceId.value === id) {
    selectedWorkspaceId.value = workspaces.value[0]?.id || ''
  }
}

function updateWorkspace(id, patch) {
  const index = workspaces.value.findIndex((w) => w.id === id)
  if (index === -1) return
  workspaces.value[index] = {
    ...workspaces.value[index],
    ...patch,
    updated_at: new Date().toISOString(),
  }
}

function ensureWorkspaceSelected() {
  if (selectedWorkspace.value) return selectedWorkspace.value
  if (workspaces.value.length > 0) {
    selectedWorkspaceId.value = workspaces.value[0].id
    return workspaces.value[0]
  }
  return createWorkspace('默认图谱')
}

function appendQaMessage(role, content) {
  const ws = ensureWorkspaceSelected()
  const messages = Array.isArray(ws.qa_messages) ? [...ws.qa_messages] : []
  messages.push({
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    role,
    content,
    created_at: new Date().toISOString(),
  })
  updateWorkspace(ws.id, { qa_messages: messages })
}

async function loadServerGraphs() {
  try {
    const { data } = await axios.get('/api/graphs')
    serverGraphs.value = Array.isArray(data) ? data : []
  } catch {
    serverGraphs.value = []
  }
}

function importServerGraph(graph) {
  const ws = createWorkspace(graph.name)
  updateWorkspace(ws.id, {
    graph_id: graph.id,
    graph_path: graph.json_output,
  })
  loadGraphDetail(graph.id)
}

function revokeObjectUrls(urls) {
  for (const url of urls) {
    URL.revokeObjectURL(url)
  }
}

function onImagesChange(event) {
  revokeObjectUrls(imagePreviewUrls.value)
  const files = Array.from(event.target.files || [])
  imageFiles.value = files
  imagePreviewUrls.value = files.map((file) => URL.createObjectURL(file))
}

function onPdfsChange(event) {
  revokeObjectUrls(pdfPreviewUrls.value)
  const files = Array.from(event.target.files || [])
  pdfFiles.value = files
  pdfPreviewUrls.value = files.map((file) => URL.createObjectURL(file))
}

function clearImages() {
  imageFiles.value = []
  revokeObjectUrls(imagePreviewUrls.value)
  imagePreviewUrls.value = []
}

function clearPdfs() {
  pdfFiles.value = []
  revokeObjectUrls(pdfPreviewUrls.value)
  pdfPreviewUrls.value = []
}

function clearUploads() {
  textInput.value = ''
  clearImages()
  clearPdfs()
}

function buildGraphData(payload) {
  const entityMap = new Map()
  const nodes = []

  for (const entity of payload.entities ?? []) {
    entityMap.set(entity.name, entity.type)
    nodes.push({
      id: entity.name,
      name: entity.name,
      value: entity.type,
      category: entity.type,
      symbolSize: 56,
      itemStyle: { color: entityColors[entity.type] ?? '#6f6f6f' },
      label: {
        show: true,
        formatter: `{b}\n(${entity.type})`,
        fontSize: 12,
      },
    })
  }

  const links = []
  const literalAdded = new Set()

  for (const rel of payload.relations ?? []) {
    const source = rel.source
    const target = rel.target

    if (!entityMap.has(target)) {
      const literalId = `literal::${target}`
      if (!literalAdded.has(literalId)) {
        literalAdded.add(literalId)
        nodes.push({
          id: literalId,
          name: target,
          value: 'Literal',
          category: 'Literal',
          symbolSize: 44,
          itemStyle: { color: entityColors.Literal },
          label: {
            show: true,
            formatter: `{b}\n(Literal)`,
            fontSize: 11,
          },
        })
      }
      links.push({ source, target: literalId, value: rel.type })
    } else {
      links.push({ source, target, value: rel.type })
    }
  }

  return { nodes, links }
}

function renderGraph(payload) {
  if (!chartEl.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }

  const { nodes, links } = buildGraphData(payload)

  chartInstance.setOption({
    backgroundColor: '#f9fcff',
    tooltip: { trigger: 'item', confine: true },
    animationDuration: 800,
    animationEasing: 'cubicOut',
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links,
        roam: true,
        draggable: true,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 10],
        force: {
          repulsion: 1200,
          edgeLength: [120, 220],
          gravity: 0.08,
        },
        lineStyle: {
          width: 2,
          color: '#8c7f6f',
          curveness: 0.08,
        },
        edgeLabel: {
          show: true,
          formatter: (params) => params.data.value,
          color: '#3f557f',
          fontSize: 12,
        },
        label: { color: '#1b2f59' },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
        },
      },
    ],
  })
}

async function loadGraphDetail(graphId) {
  if (!graphId) return
  errorMessage.value = ''
  try {
    const { data } = await axios.get(`/api/graphs/${encodeURIComponent(graphId)}`)
    result.value = data.data
    await nextTick()
    renderGraph(result.value)
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '加载图谱失败'
  }
}

async function submitExtract() {
  errorMessage.value = ''
  if (!hasAnyInput.value) {
    errorMessage.value = '请先上传文本、图片或PDF。'
    return
  }

  const ws = ensureWorkspaceSelected()

  const formData = new FormData()
  formData.append('text', textInput.value)
  formData.append('graph_name', ws.name)
  formData.append('model_name', modelName.value)
  if (apiKey.value.trim()) formData.append('api_key', apiKey.value.trim())
  if (baseUrl.value.trim()) formData.append('base_url', baseUrl.value.trim())
  if (extractPrompt.value.trim()) formData.append('custom_prompt', extractPrompt.value.trim())

  for (const file of imageFiles.value) {
    formData.append('image_files', file)
  }

  for (const file of pdfFiles.value) {
    formData.append('pdf_files', file)
  }

  loading.value = true
  try {
    const { data } = await axios.post('/api/extract', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })

    result.value = data
    updateWorkspace(ws.id, {
      graph_id: data.graph_id,
      graph_path: data.json_output,
      entity_count: data.entities?.length ?? 0,
      triple_count: data.triples?.length ?? 0,
    })

    await loadServerGraphs()
    await nextTick()
    renderGraph(data)
    activeTab.value = 'graph'
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '抽取失败'
  } finally {
    loading.value = false
  }
}

async function askQuestion() {
  errorMessage.value = ''
  const question = qaQuestion.value.trim()
  if (!question) return

  const ws = selectedWorkspace.value
  if (!ws?.graph_id) {
    errorMessage.value = '请先在图谱列表中选择一个已构建图谱，再进行问答。'
    return
  }

  appendQaMessage('user', question)
  qaQuestion.value = ''
  qaLoading.value = true

  try {
    const { data } = await axios.post('/api/qa', {
      graph_id: ws.graph_id,
      question,
      model_name: modelName.value,
      api_key: apiKey.value.trim() || null,
      base_url: baseUrl.value.trim() || null,
      qa_prompt: qaPrompt.value.trim() || null,
    })

    appendQaMessage('assistant', data.answer)
  } catch (error) {
    appendQaMessage('assistant', '问答失败，请检查图谱或模型配置。')
    errorMessage.value = error?.response?.data?.detail || error?.message || '问答失败'
  } finally {
    qaLoading.value = false
  }
}

function downloadGraph() {
  if (!chartInstance) return
  const dataUrl = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#f9fcff',
  })

  const wsName = selectedWorkspace.value?.name || 'knowledge_graph'
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = `${wsName}_${Date.now()}.png`
  a.click()
}

function downloadJson() {
  if (!result.value) return
  const blob = new Blob([JSON.stringify(result.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const wsName = selectedWorkspace.value?.name || 'knowledge_graph'
  const a = document.createElement('a')
  a.href = url
  a.download = `${wsName}_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(async () => {
  hydrateWorkspaces()
  if (!workspaces.value.length) {
    createWorkspace('默认图谱')
  } else {
    selectedWorkspaceId.value = workspaces.value[0].id
  }

  await loadServerGraphs()

  if (selectedWorkspace.value?.graph_id) {
    await loadGraphDetail(selectedWorkspace.value.graph_id)
  }

  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  revokeObjectUrls(imagePreviewUrls.value)
  revokeObjectUrls(pdfPreviewUrls.value)
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<template>
  <main class="page">
    <section class="hero animate fade-up">
      <div class="hero-badge">Heritage Graph Studio</div>
      <h1>文化遗产知识图谱生成与问答工作台</h1>
      <p>图谱管理、文件上传、图谱问答、API配置统一在左侧完成。</p>
      <div class="hero-meta">
        <span>多模态输入</span>
        <span>图谱列表管理</span>
        <span>基于图谱问答</span>
      </div>
    </section>

    <section class="workspace">
      <aside class="left-panel panel animate fade-up delay-1">
        <nav class="tab-nav">
          <button
            v-for="tab in tabOptions"
            :key="tab.key"
            class="tab-btn"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </nav>

        <section v-if="activeTab === 'graph'" class="tab-body">
          <h2>图谱列表</h2>
          <div class="new-row">
            <input v-model="workspaceNameInput" type="text" placeholder="输入新图谱名称" />
            <button class="primary-btn" @click="createWorkspaceByInput">新建</button>
          </div>

          <div class="workspace-list">
            <article
              v-for="ws in workspaces"
              :key="ws.id"
              class="workspace-item"
              :class="{ selected: ws.id === selectedWorkspaceId }"
              @click="selectWorkspace(ws.id)"
            >
              <header>
                <strong>{{ ws.name }}</strong>
                <button class="mini ghost-btn" @click.stop="removeWorkspace(ws.id)">删除</button>
              </header>
              <p>实体：{{ ws.entity_count || 0 }} / 三元组：{{ ws.triple_count || 0 }}</p>
              <div class="workspace-actions">
                <button class="mini ghost-btn" :disabled="!ws.graph_id" @click.stop="loadGraphDetail(ws.graph_id)">加载图谱</button>
                <span class="tag" :class="{ done: !!ws.graph_id }">{{ ws.graph_id ? '已构建' : '未构建' }}</span>
              </div>
            </article>
          </div>

          <details>
            <summary>服务器图谱（可导入）</summary>
            <div class="server-graph-list">
              <article v-for="g in serverGraphs" :key="g.id" class="server-item">
                <div>
                  <strong>{{ g.name }}</strong>
                  <p>{{ g.id }}</p>
                </div>
                <button class="mini ghost-btn" @click="importServerGraph(g)">导入</button>
              </article>
            </div>
          </details>
        </section>

        <section v-if="activeTab === 'upload'" class="tab-body">
          <h2>上传输入</h2>

          <label class="field">
            文本输入
            <textarea v-model="textInput" rows="7" placeholder="输入待抽取文本" />
          </label>

          <label class="field">
            上传图片（支持多张）
            <input type="file" accept="image/*" multiple @change="onImagesChange" />
          </label>

          <label class="field">
            上传PDF（支持多个）
            <input type="file" accept="application/pdf" multiple @change="onPdfsChange" />
          </label>

          <div class="actions">
            <button :disabled="loading || !hasAnyInput" class="primary-btn" @click="submitExtract">
              {{ loading ? '抽取中...' : '开始抽取' }}
            </button>
            <button :disabled="loading" class="ghost-btn" @click="clearUploads">清空输入</button>
          </div>

          <div v-if="imagePreviewUrls.length || pdfPreviewUrls.length" class="inline-preview">
            <div v-if="imagePreviewUrls.length" class="preview-group">
              <h3>图片预览（{{ imageFiles.length }}）</h3>
              <div class="preview-grid">
                <article v-for="(url, idx) in imagePreviewUrls" :key="`img-${idx}`" class="preview-card">
                  <header><span>{{ imageFiles[idx]?.name }}</span></header>
                  <div class="preview-body"><img :src="url" alt="image-preview" /></div>
                </article>
              </div>
            </div>

            <div v-if="pdfPreviewUrls.length" class="preview-group">
              <h3>PDF预览（{{ pdfFiles.length }}）</h3>
              <div class="preview-grid">
                <article v-for="(url, idx) in pdfPreviewUrls" :key="`pdf-${idx}`" class="preview-card">
                  <header><span>{{ pdfFiles[idx]?.name }}</span></header>
                  <div class="preview-body"><iframe :src="url" title="pdf-preview"></iframe></div>
                </article>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeTab === 'qa'" class="tab-body">
          <h2>图谱问答</h2>
          <p class="hint">
            当前图谱：{{ selectedWorkspace?.name || '未选择' }}
            <span v-if="selectedWorkspace?.graph_id">（{{ selectedWorkspace.graph_id }}）</span>
          </p>

          <div class="chat-box">
            <article v-for="msg in qaMessages" :key="msg.id" class="chat-item" :class="msg.role">
              <strong>{{ msg.role === 'user' ? '你' : '助手' }}</strong>
              <p>{{ msg.content }}</p>
            </article>

            <div v-if="!qaMessages.length" class="chat-empty">
              先构建图谱，再在这里提问。
            </div>
          </div>

          <div class="qa-input-row">
            <textarea
              v-model="qaQuestion"
              rows="3"
              placeholder="例如：柱子在图谱中有哪些病害？"
              @keydown.enter.exact.prevent="askQuestion"
            />
            <button class="primary-btn" :disabled="!canAsk" @click="askQuestion">
              {{ qaLoading ? '回答中...' : '发送' }}
            </button>
          </div>
        </section>

        <section v-if="activeTab === 'api'" class="tab-body">
          <h2>API配置</h2>

          <label class="field">
            模型名称
            <input v-model="modelName" type="text" placeholder="例如 qwen-max / gpt-4.1-mini" />
          </label>

          <label class="field">
            API Key
            <input v-model="apiKey" type="password" placeholder="不填则使用规则模式" />
          </label>

          <label class="field">
            Base URL
            <input v-model="baseUrl" type="text" placeholder="例如 https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </label>

          <label class="field">
            自定义抽取提示词
            <textarea v-model="extractPrompt" rows="5" placeholder="可选：覆盖默认知识图谱抽取提示词" />
          </label>

          <label class="field">
            问答补充提示词
            <textarea v-model="qaPrompt" rows="4" placeholder="可选：例如“回答要简洁并列出依据”" />
          </label>
        </section>

        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </aside>

      <section class="right-panel animate fade-up delay-2">
        <div class="panel result-panel">
          <div class="result-head">
            <h2>知识图谱预览</h2>
            <div class="actions">
              <button class="primary-btn" :disabled="!result" @click="downloadGraph">下载图谱图片</button>
              <button class="ghost-btn" :disabled="!result" @click="downloadJson">下载JSON</button>
            </div>
          </div>

          <div class="graph-wrap">
            <div ref="chartEl" class="graph"></div>
            <div v-if="loading" class="graph-loading">
              <div class="loader-ring"></div>
              <p>正在抽取并构建知识图谱...</p>
            </div>
            <div v-if="!loading && !result" class="graph-empty">提交后将在这里展示知识图谱</div>
          </div>

          <div v-if="result" class="meta">
            <p><strong>当前图谱：</strong>{{ selectedWorkspace?.name || '-' }}</p>
            <p><strong>输出文件：</strong>{{ result.json_output || selectedWorkspace?.graph_path }}</p>
            <p><strong>实体数：</strong>{{ result.entities?.length || 0 }}，<strong>三元组数：</strong>{{ result.triples?.length || 0 }}</p>
          </div>

          <details v-if="result?.warnings?.length" class="warning-box">
            <summary>处理警告（{{ result.warnings.length }}）</summary>
            <ul>
              <li v-for="(w, idx) in result.warnings" :key="idx">{{ w }}</li>
            </ul>
          </details>

          <details v-if="result">
            <summary>查看JSON结果</summary>
            <pre>{{ JSON.stringify(result, null, 2) }}</pre>
          </details>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.page {
  width: min(1420px, 95vw);
  margin: 24px auto 34px;
  display: grid;
  gap: 16px;
}

.hero {
  position: relative;
  overflow: hidden;
  padding: 26px 26px 24px;
  border: 1px solid rgba(115, 150, 232, 0.24);
  background:
    radial-gradient(circle at 85% 0%, rgba(108, 169, 255, 0.35) 0%, transparent 42%),
    radial-gradient(circle at 5% 20%, rgba(73, 205, 199, 0.25) 0%, transparent 44%),
    linear-gradient(120deg, #f8fbff 0%, #f2f7ff 55%, #eef6ff 100%);
  border-radius: 22px;
  box-shadow: 0 18px 40px rgba(38, 70, 120, 0.14);
}

.hero-badge {
  width: fit-content;
  border-radius: 999px;
  background: rgba(59, 105, 194, 0.1);
  border: 1px solid rgba(59, 105, 194, 0.2);
  color: #3059a3;
  font-size: 12px;
  font-weight: 700;
  padding: 6px 10px;
}

.hero h1 {
  margin: 12px 0 8px;
  font-size: clamp(24px, 3vw, 36px);
  line-height: 1.2;
  color: #112245;
}

.hero p {
  margin: 0;
  color: #3d527a;
}

.hero-meta {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.hero-meta span {
  border: 1px solid rgba(90, 127, 201, 0.3);
  background: rgba(255, 255, 255, 0.56);
  color: #325590;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(390px, 470px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.panel {
  border: 1px solid rgba(149, 172, 220, 0.28);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
  backdrop-filter: blur(6px);
  box-shadow: 0 12px 30px rgba(35, 61, 109, 0.08);
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.panel:hover {
  transform: translateY(-2px);
  border-color: rgba(112, 149, 223, 0.46);
  box-shadow: 0 16px 34px rgba(35, 61, 109, 0.11);
}

.left-panel {
  padding: 16px;
  position: sticky;
  top: 16px;
}

.tab-nav {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.tab-btn {
  background: rgba(232, 241, 255, 0.72);
  border: 1px solid rgba(124, 155, 219, 0.4);
  color: #2a4b84;
  font-weight: 700;
  border-radius: 10px;
  padding: 8px 6px;
  cursor: pointer;
}

.tab-btn.active {
  color: white;
  border-color: transparent;
  background: linear-gradient(135deg, #4d8af7, #46b6e9);
}

.tab-body h2 {
  margin: 0 0 12px;
  font-size: 18px;
  color: #1b2f59;
}

.field {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  color: #283f70;
  font-weight: 650;
}

textarea,
input {
  width: 100%;
  border: 1px solid rgba(123, 151, 209, 0.4);
  background: rgba(255, 255, 255, 0.9);
  color: #0f2346;
  border-radius: 12px;
  padding: 11px 12px;
  font-size: 14px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

textarea:focus,
input:focus {
  outline: none;
  border-color: #5f89d8;
  box-shadow: 0 0 0 4px rgba(95, 137, 216, 0.14);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

button {
  position: relative;
  overflow: hidden;
  border-radius: 11px;
  cursor: pointer;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 700;
  border: 1px solid transparent;
  transition: transform 0.2s ease, filter 0.2s ease;
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.primary-btn {
  color: #fff;
  background: linear-gradient(135deg, #4d8af7, #46b6e9);
  box-shadow: 0 8px 18px rgba(61, 127, 225, 0.25);
}

.ghost-btn {
  color: #2a4b84;
  background: rgba(232, 241, 255, 0.68);
  border-color: rgba(124, 155, 219, 0.4);
}

.mini {
  padding: 5px 8px;
  font-size: 12px;
}

.new-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  margin-bottom: 12px;
}

.workspace-list {
  display: grid;
  gap: 8px;
  max-height: 290px;
  overflow: auto;
  padding-right: 4px;
}

.workspace-item {
  border: 1px solid rgba(124, 155, 219, 0.35);
  border-radius: 12px;
  padding: 8px;
  cursor: pointer;
  background: rgba(248, 251, 255, 0.88);
}

.workspace-item.selected {
  border-color: rgba(76, 139, 246, 0.8);
  box-shadow: 0 0 0 3px rgba(76, 139, 246, 0.14);
}

.workspace-item header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.workspace-item p {
  margin: 8px 0 6px;
  color: #3f557d;
  font-size: 13px;
}

.workspace-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2fb;
  color: #546689;
}

.tag.done {
  background: #e6f8ef;
  color: #2a915e;
}

.server-graph-list {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.server-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid rgba(124, 155, 219, 0.3);
  border-radius: 10px;
  padding: 8px;
}

.server-item p {
  margin: 3px 0 0;
  font-size: 12px;
  color: #617697;
}

.hint {
  margin: 0 0 8px;
  color: #496189;
}

.chat-box {
  border: 1px solid rgba(124, 155, 219, 0.32);
  border-radius: 12px;
  background: #f8fbff;
  min-height: 260px;
  max-height: 360px;
  overflow: auto;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.chat-item {
  max-width: 90%;
  border-radius: 10px;
  padding: 8px 10px;
}

.chat-item strong {
  font-size: 12px;
}

.chat-item p {
  margin: 4px 0 0;
  white-space: pre-wrap;
}

.chat-item.user {
  justify-self: end;
  background: #dbecff;
  color: #18376c;
}

.chat-item.assistant {
  justify-self: start;
  background: #edf2f9;
  color: #2b446e;
}

.chat-empty {
  display: grid;
  place-items: center;
  color: #6a7c9b;
}

.qa-input-row {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

.error {
  margin: 10px 0 0;
  color: #b42318;
}

.right-panel {
  display: grid;
  gap: 16px;
}

.right-panel > .panel {
  padding: 16px;
}

.preview-group {
  margin-bottom: 12px;
}

.inline-preview {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}

.inline-preview .preview-grid {
  grid-template-columns: 1fr;
}

.preview-group h3 {
  margin: 0 0 8px;
  color: #2a4476;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.preview-card {
  border: 1px solid rgba(127, 153, 205, 0.35);
  border-radius: 14px;
  background: #f8fbff;
  overflow: hidden;
}

.preview-card header {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(127, 153, 205, 0.3);
  color: #304b7d;
  font-size: 12px;
}

.preview-card header span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-body {
  height: 230px;
  background: #f4f8ff;
}

.preview-body img,
.preview-body iframe {
  width: 100%;
  height: 100%;
  border: 0;
  object-fit: contain;
}

.result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.result-head h2 {
  margin: 0;
}

.graph {
  height: min(58vh, 560px);
  border-radius: 14px;
  border: 1px solid rgba(117, 153, 216, 0.35);
  background: #f9fcff;
}

.graph-wrap {
  position: relative;
  margin-top: 10px;
}

.graph-loading,
.graph-empty {
  position: absolute;
  inset: 0;
  border-radius: 14px;
  display: grid;
  place-items: center;
  text-align: center;
}

.graph-loading {
  gap: 10px;
  background: rgba(248, 252, 255, 0.88);
  backdrop-filter: blur(3px);
  color: #2e4f84;
  font-weight: 600;
}

.loader-ring {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 3px solid rgba(88, 136, 220, 0.22);
  border-top-color: #4f89f8;
  animation: spin 0.75s linear infinite;
}

.graph-empty {
  color: #5e749c;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(249, 252, 255, 0.2), rgba(249, 252, 255, 0.58));
}

.meta {
  margin-top: 10px;
  color: #27416f;
}

.warning-box {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff6e5;
  border: 1px solid #efd2a0;
}

.warning-box ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

details {
  margin-top: 12px;
}

pre {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(128, 155, 209, 0.35);
  background: #f8fbff;
}

.animate {
  opacity: 0;
  animation-fill-mode: forwards;
}

.fade-up {
  animation-name: fadeUp;
  animation-duration: 0.65s;
  animation-timing-function: cubic-bezier(0.2, 0.7, 0.2, 1);
}

.delay-1 {
  animation-delay: 0.08s;
}

.delay-2 {
  animation-delay: 0.16s;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .left-panel {
    position: static;
  }

  .preview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .tab-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .new-row {
    grid-template-columns: 1fr;
  }

  .graph {
    height: 420px;
  }
}
</style>
