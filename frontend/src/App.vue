<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const textInput = ref('')
const modelName = ref('gpt-4.1-mini')
const apiKey = ref('')
const baseUrl = ref('')

const imageFile = ref(null)
const pdfFile = ref(null)
const imagePreviewUrl = ref('')
const pdfPreviewUrl = ref('')

const loading = ref(false)
const errorMessage = ref('')
const result = ref(null)
const hasAnyInput = computed(() => Boolean(textInput.value.trim()) || imageFile.value !== null || pdfFile.value !== null)

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

function onImageChange(event) {
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
    imagePreviewUrl.value = ''
  }

  imageFile.value = event.target.files?.[0] ?? null
  if (imageFile.value) {
    imagePreviewUrl.value = URL.createObjectURL(imageFile.value)
  }
}

function onPdfChange(event) {
  if (pdfPreviewUrl.value) {
    URL.revokeObjectURL(pdfPreviewUrl.value)
    pdfPreviewUrl.value = ''
  }

  pdfFile.value = event.target.files?.[0] ?? null
  if (pdfFile.value) {
    pdfPreviewUrl.value = URL.createObjectURL(pdfFile.value)
  }
}

function clearImage() {
  imageFile.value = null
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
  imagePreviewUrl.value = ''
}

function clearPdf() {
  pdfFile.value = null
  if (pdfPreviewUrl.value) {
    URL.revokeObjectURL(pdfPreviewUrl.value)
  }
  pdfPreviewUrl.value = ''
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
      links.push({
        source,
        target: literalId,
        value: rel.type,
      })
    } else {
      links.push({
        source,
        target,
        value: rel.type,
      })
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
    tooltip: {
      trigger: 'item',
      confine: true,
    },
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
        label: {
          color: '#1b2f59',
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
        },
      },
    ],
  })
}

async function submitForm() {
  errorMessage.value = ''
  result.value = null

  if (!textInput.value.trim() && !imageFile.value && !pdfFile.value) {
    errorMessage.value = '请至少输入文本或上传图片/PDF。'
    return
  }

  const formData = new FormData()
  formData.append('text', textInput.value)
  formData.append('model_name', modelName.value)
  if (apiKey.value.trim()) formData.append('api_key', apiKey.value.trim())
  if (baseUrl.value.trim()) formData.append('base_url', baseUrl.value.trim())
  if (imageFile.value) formData.append('image_file', imageFile.value)
  if (pdfFile.value) formData.append('pdf_file', pdfFile.value)

  loading.value = true
  try {
    const { data } = await axios.post('/api/extract', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })

    result.value = data
    await nextTick()
    renderGraph(data)
  } catch (error) {
    const msg = error?.response?.data?.detail || error?.message || '请求失败'
    errorMessage.value = String(msg)
  } finally {
    loading.value = false
  }
}

function downloadGraph() {
  if (!chartInstance) return
  const dataUrl = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#f9fcff',
  })

  const a = document.createElement('a')
  a.href = dataUrl
  a.download = `knowledge_graph_${Date.now()}.png`
  a.click()
}

function downloadJson() {
  if (!result.value) return
  const blob = new Blob([JSON.stringify(result.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `knowledge_graph_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (imagePreviewUrl.value) URL.revokeObjectURL(imagePreviewUrl.value)
  if (pdfPreviewUrl.value) URL.revokeObjectURL(pdfPreviewUrl.value)
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<template>
  <main class="page">
    <section class="hero animate fade-up">
      <div class="hero-badge">Heritage Graph Studio</div>
      <h1>文化遗产知识图谱生成工作台</h1>
      <p>左侧配置抽取参数，右侧实时预览素材和知识图谱。</p>
      <div class="hero-meta">
        <span>多模态输入</span>
        <span>LangGraph 编排</span>
        <span>可下载图谱与 JSON</span>
      </div>
    </section>

    <section class="workspace">
      <aside class="left-panel panel animate fade-up delay-1">
        <h2>输入与模型配置</h2>

        <label class="field">
          文本输入
          <textarea v-model="textInput" rows="10" placeholder="输入待抽取文本" />
        </label>

        <div class="two-col">
          <label class="field">
            模型名称
            <input v-model="modelName" type="text" placeholder="例如 qwen-max 或 gpt-4.1-mini" />
          </label>
          <label class="field">
            Base URL
            <input v-model="baseUrl" type="text" placeholder="例如 https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </label>
        </div>

        <label class="field">
          API Key
          <input v-model="apiKey" type="password" placeholder="可选，不填则使用规则抽取" />
        </label>

        <div class="upload-grid">
          <label class="field">
            上传图片
            <input type="file" accept="image/*" @change="onImageChange" />
          </label>
          <label class="field">
            上传PDF
            <input type="file" accept="application/pdf" @change="onPdfChange" />
          </label>
        </div>

        <div class="actions">
          <button :disabled="loading || !hasAnyInput" class="primary-btn" @click="submitForm">
            {{ loading ? '抽取中...' : '开始抽取' }}
          </button>
          <button :disabled="loading" class="ghost-btn" @click="clearImage">清空图片</button>
          <button :disabled="loading" class="ghost-btn" @click="clearPdf">清空PDF</button>
        </div>

        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </aside>

      <section class="right-panel animate fade-up delay-2">
        <div class="panel">
          <h2>上传预览</h2>
          <div class="preview-grid">
            <article class="preview-card">
              <header>
                <span>图片预览</span>
                <small>{{ imageFile ? imageFile.name : '未上传图片' }}</small>
              </header>
              <div class="preview-body">
                <img v-if="imagePreviewUrl" :src="imagePreviewUrl" alt="图片预览" />
                <div v-else class="empty">上传图片后将在这里预览</div>
              </div>
            </article>

            <article class="preview-card">
              <header>
                <span>PDF预览</span>
                <small>{{ pdfFile ? pdfFile.name : '未上传PDF' }}</small>
              </header>
              <div class="preview-body">
                <iframe v-if="pdfPreviewUrl" :src="pdfPreviewUrl" title="pdf-preview"></iframe>
                <div v-else class="empty">上传 PDF 后将在这里预览</div>
              </div>
            </article>
          </div>
        </div>

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
            <div v-if="!loading && !result" class="graph-empty">
              提交后将在这里展示知识图谱
            </div>
          </div>

          <div v-if="result" class="meta">
            <p><strong>模型：</strong>{{ result.model_used }}</p>
            <p><strong>输出文件：</strong>{{ result.json_output }}</p>
            <p><strong>实体数：</strong>{{ result.entities.length }}，<strong>三元组数：</strong>{{ result.triples.length }}</p>
          </div>

          <div v-if="result?.warnings?.length" class="warning-box">
            <h3>处理警告</h3>
            <ul>
              <li v-for="(w, idx) in result.warnings" :key="idx">{{ w }}</li>
            </ul>
          </div>

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
  width: min(1380px, 95vw);
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
  grid-template-columns: minmax(360px, 430px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.panel {
  border: 1px solid rgba(149, 172, 220, 0.28);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.75);
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
  padding: 18px;
  position: sticky;
  top: 18px;
}

.left-panel h2,
.right-panel h2 {
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

textarea {
  resize: vertical;
  min-height: 170px;
}

.two-col,
.upload-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
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
  filter: saturate(1.04);
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

.primary-btn::after {
  content: "";
  position: absolute;
  top: 0;
  left: -120%;
  width: 80%;
  height: 100%;
  background: linear-gradient(100deg, transparent 10%, rgba(255, 255, 255, 0.4) 50%, transparent 90%);
  transform: skewX(-24deg);
}

.primary-btn:hover:not(:disabled)::after {
  animation: shine 0.95s ease;
}

.ghost-btn {
  color: #2a4b84;
  background: rgba(232, 241, 255, 0.68);
  border-color: rgba(124, 155, 219, 0.4);
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

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.preview-card {
  border: 1px solid rgba(127, 153, 205, 0.35);
  border-radius: 14px;
  background: #f8fbff;
  overflow: hidden;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.preview-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(45, 74, 125, 0.13);
}

.preview-card header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(127, 153, 205, 0.3);
  color: #304b7d;
}

.preview-card header span {
  font-weight: 700;
}

.preview-card header small {
  color: #5f7397;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-body {
  height: 265px;
  background: #f4f8ff;
}

.preview-body img,
.preview-body iframe {
  width: 100%;
  height: 100%;
  border: 0;
  object-fit: contain;
}

.empty {
  height: 100%;
  display: grid;
  place-items: center;
  color: #6c7ea2;
  font-size: 13px;
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
  margin-top: 10px;
  border-radius: 14px;
  border: 1px solid rgba(117, 153, 216, 0.35);
  background: #f9fcff;
}

.graph-wrap {
  position: relative;
  margin-top: 10px;
}

.graph-wrap .graph {
  margin-top: 0;
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

.warning-box h3 {
  margin: 0 0 6px;
  font-size: 14px;
}

.warning-box ul {
  margin: 0;
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

@keyframes shine {
  from {
    left: -120%;
  }
  to {
    left: 130%;
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

@media (max-width: 1080px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .left-panel {
    position: static;
  }

  .preview-grid,
  .two-col,
  .upload-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .page {
    width: min(100%, 96vw);
  }

  .preview-body {
    height: 220px;
  }

  .graph {
    height: 430px;
  }
}
</style>
