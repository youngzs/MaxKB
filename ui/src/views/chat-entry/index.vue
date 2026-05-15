<template>
  <div class="chat-entry" v-loading="loading">
    <!-- 顶部工具栏：标题 + 知识库切换 + 新对话 -->
    <div class="chat-entry__toolbar flex-between">
      <div class="flex align-center">
        <AppIcon iconName="app-user-chat" class="chat-entry__logo mr-8" />
        <div>
          <h4 class="m-0">{{ $t('views.chatEntry.title') }}</h4>
          <el-text type="info" size="small">{{ $t('views.chatEntry.subTitle') }}</el-text>
        </div>
      </div>

      <div class="flex align-center chat-entry__controls">
        <span class="mr-8 lighter chat-entry__kb-label">
          {{ $t('views.chatEntry.kb.label') }}
        </span>
        <el-select
          v-model="selectedKnowledgeIds"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          :max-collapse-tags="2"
          :placeholder="$t('views.chatEntry.kb.placeholder')"
          :disabled="!backingApp || knowledgeList.length === 0"
          class="chat-entry__kb-select"
          @change="onKnowledgeChange"
        >
          <el-option
            v-for="kb in knowledgeList"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          >
            <div class="flex align-center">
              <KnowledgeIcon :type="kb.type" :size="18" class="mr-8" />
              <span class="ellipsis">{{ kb.name }}</span>
            </div>
          </el-option>
        </el-select>
        <el-button
          class="ml-12"
          :disabled="!backingApp"
          @click="newChat"
        >
          <AppIcon iconName="app-create-chat" class="mr-4" />
          {{ $t('views.chatEntry.newChat') }}
        </el-button>
      </div>
    </div>

    <!-- 知识库提示 -->
    <div class="chat-entry__tip">
      <el-text v-if="knowledgeList.length === 0" type="warning" size="small">
        {{ $t('views.chatEntry.kb.noKnowledge') }}
      </el-text>
      <el-text v-else-if="selectedKnowledgeIds.length === 0" type="info" size="small">
        {{ $t('views.chatEntry.kb.emptyHint') }}
      </el-text>
      <el-text v-else type="info" size="small">
        {{ $t('views.chatEntry.kb.activeHint', { n: selectedKnowledgeIds.length }) }}
      </el-text>
    </div>

    <!-- 对话区 -->
    <div class="chat-entry__body">
      <!-- 缺少可用模型，无法自动创建对话应用 -->
      <el-empty
        v-if="!loading && !backingApp"
        :description="$t('views.chatEntry.noApp.desc')"
        class="chat-entry__empty"
      >
        <template #image>
          <AppIcon iconName="app-user-chat" style="font-size: 60px; color: var(--el-color-info)" />
        </template>
        <el-button type="primary" @click="goModelManage">
          {{ $t('views.chatEntry.noApp.goModel') }}
        </el-button>
      </el-empty>

      <div v-else class="chat-entry__chat dialog-bg">
        <AiChat
          v-if="backingApp"
          :key="chatSessionKey"
          :applicationDetails="backingApp"
          :appId="backingApp.id"
          :knowledgeIdList="selectedKnowledgeIds"
          type="debug-ai-chat"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AiChat from '@/components/ai-chat/index.vue'
import ApplicationApi from '@/api/application/application'
import KnowledgeApi from '@/api/knowledge/knowledge'
import ModelApi from '@/api/model/model'
import useStore from '@/stores'
import { t } from '@/locales'

const router = useRouter()
const { user } = useStore()

/**
 * 本页专用的对话应用名称——固定复用同一个，仅作为模型/Prompt 的承载体。
 * 知识库由会话级参数 knowledgeIdList 显式传入（后端会话级隔离），
 * 因此该应用自身的 knowledge_id_list 绑定始终为空、不会被修改。
 */
const DEDICATED_APP_NAME = '知识库问答助手'
/** 用户本地记忆上次选择的知识库（按工作空间分桶） */
const KB_SELECTION_STORAGE_KEY = computed(
  () => `chat-entry:kb:${user.getWorkspaceId() || 'default'}`,
)

const loading = ref(false)
const knowledgeList = ref<any[]>([])
const selectedKnowledgeIds = ref<string[]>([])
// 完整的应用详情对象，直接作为 AiChat 的 applicationDetails 传入
const backingApp = ref<any>(null)
// 改变 key 会重新挂载 AiChat —— 用于「新对话」和「切换知识库后重开会话」
const chatSessionKey = ref(0)

const defaultPrompt = t('views.application.form.prompt.defaultPrompt', {
  data: '{data}',
  question: '{question}',
})

/**
 * 应用详情 → AiChat 需要的表单结构。
 * 与 ApplicationSetting.getDetail 的字段重映射保持一致。
 */
function normalizeAppDetail(data: any) {
  return {
    ...data,
    model_id: data.model,
    stt_model_id: data.stt_model,
    tts_model_id: data.tts_model,
    tts_type: data.tts_type,
    long_term_model_id: data.long_term_model,
  }
}

/** 读取本地记忆的知识库选择，过滤掉已不存在的 id */
function loadStoredSelection(): string[] {
  try {
    const raw = localStorage.getItem(KB_SELECTION_STORAGE_KEY.value)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : []
  } catch (e) {
    return []
  }
}

/** 持久化当前知识库选择到 localStorage */
function persistSelection(ids: string[]) {
  try {
    localStorage.setItem(KB_SELECTION_STORAGE_KEY.value, JSON.stringify(ids))
  } catch (e) {
    /* 容量不足等异常忽略，不影响主流程 */
  }
}

/** 加载当前工作空间下的全部知识库（folder_id = workspaceId 时后端不按目录过滤，返回全部） */
async function loadKnowledgeList() {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  try {
    const res: any = await KnowledgeApi.getKnowledgeList({ folder_id: workspaceId })
    knowledgeList.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    knowledgeList.value = []
  }
}

/** 构造新建专用应用所需的 SIMPLE 表单 */
function buildSimpleAppForm(modelId: string) {
  return {
    name: DEDICATED_APP_NAME,
    desc: t('views.chatEntry.dedicatedAppDesc'),
    model_id: modelId,
    dialogue_number: 5,
    prologue: t('views.chatEntry.prologue'),
    knowledge_id_list: [] as string[],
    knowledge_setting: {
      top_n: 5,
      similarity: 0.5,
      max_paragraph_char_number: 5000,
      search_mode: 'blend',
      no_references_setting: {
        status: 'ai_questioning',
        value: '{question}',
      },
    },
    model_setting: {
      prompt: defaultPrompt,
      system: '',
      no_references_prompt: '{question}',
    },
    model_params_setting: {},
    problem_optimization: false,
    stt_model_id: undefined,
    tts_model_id: undefined,
    stt_model_enable: false,
    tts_model_enable: false,
    tts_type: 'BROWSER',
    type: 'SIMPLE',
    folder_id: user.getWorkspaceId(),
  }
}

/** 找到或创建本页专用的对话应用（不再读写它的 knowledge_id_list） */
async function ensureBackingApp() {
  // 1. 复用已存在的专用应用
  const listRes: any = await ApplicationApi.getAllApplication({})
  const all: any[] = Array.isArray(listRes?.data) ? listRes.data : []
  const existed = all.find((a) => a.name === DEDICATED_APP_NAME && a.type === 'SIMPLE')
  if (existed) {
    const detail: any = await ApplicationApi.getApplicationDetail(existed.id)
    backingApp.value = normalizeAppDetail(detail.data)
    return
  }

  // 2. 不存在则新建——需要一个可用的 LLM 模型
  let modelId = ''
  try {
    const modelRes: any = await ModelApi.getSelectModelList({ model_type: 'LLM' })
    modelId = modelRes?.data?.[0]?.id || ''
  } catch (e) {
    modelId = ''
  }
  if (!modelId) {
    // 没有可用模型，无法自动创建——页面会展示空态引导去配置模型
    backingApp.value = null
    return
  }
  const createRes: any = await ApplicationApi.postApplication(buildSimpleAppForm(modelId) as any)
  const detail: any = await ApplicationApi.getApplicationDetail(createRes.data.id)
  backingApp.value = normalizeAppDetail(detail.data)
}

/**
 * 切换 / 关联知识库——会话级隔离：仅记忆到 localStorage 并重开 AiChat 会话；
 * 不修改应用的 knowledge_id_list 绑定。AiChat 会通过 knowledgeIdList prop
 * 把当前选择传给后端 open 接口，后端只对本次会话生效。
 */
function onKnowledgeChange(ids: string[]) {
  persistSelection(ids)
  // 重新挂载 AiChat —— 触发新的 open 调用，后端按新的会话知识库列表初始化对话
  chatSessionKey.value += 1
}

function newChat() {
  chatSessionKey.value += 1
}

function goModelManage() {
  router.push({ name: 'model' })
}

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([loadKnowledgeList(), ensureBackingApp()])
    // 恢复本地记忆的选择，并剔除已删除的知识库
    const stored = loadStoredSelection()
    const available = new Set(knowledgeList.value.map((k) => k.id))
    selectedKnowledgeIds.value = stored.filter((id) => available.has(id))
  } finally {
    loading.value = false
  }
})
</script>

<style lang="scss" scoped>
.chat-entry {
  display: flex;
  flex-direction: column;
  height: var(--app-main-height);
  box-sizing: border-box;

  &__toolbar {
    padding: 12px 24px;
    background: var(--el-bg-color);
    border-bottom: 1px solid var(--el-border-color-light);
    align-items: center;

    h4 {
      font-size: 16px;
      font-weight: 600;
    }
  }

  &__logo {
    font-size: 28px;
    color: var(--el-color-primary);
  }

  &__controls {
    flex-shrink: 0;
  }

  &__kb-label {
    white-space: nowrap;
  }

  &__kb-select {
    width: 360px;
  }

  &__tip {
    padding: 6px 24px;
    background: var(--el-bg-color);
  }

  &__body {
    flex: 1;
    overflow: hidden;
    padding: 16px 24px 24px;
    box-sizing: border-box;
  }

  &__chat {
    height: 100%;
    border-radius: 8px;
    background: var(--dialog-bg-gradient-color, var(--el-bg-color));
    overflow: hidden;
    box-sizing: border-box;
  }

  &__empty {
    padding-top: 60px;
  }
}
</style>
