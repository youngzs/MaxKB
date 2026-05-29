<template>
  <div class="chat-entry" v-loading="loading">
    <!-- 顶部工具栏：标题 + 知识库切换 -->
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

      <div v-else-if="backingApp" class="chat-entry__main flex">
        <!-- 历史对话侧栏 -->
        <div class="chat-entry__history">
          <div class="chat-entry__history-head">
            <el-button
              type="primary"
              plain
              class="w-full"
              @click="newChat"
            >
              <AppIcon iconName="app-create-chat" class="mr-4" />
              {{ $t('views.chatEntry.newChat') }}
            </el-button>
          </div>
          <div class="chat-entry__history-label">{{ $t('chat.history') }}</div>
          <el-scrollbar class="chat-entry__history-list" v-loading="chatLogLoading">
            <template v-if="displayChatList.length">
              <div
                v-for="item in displayChatList"
                :key="item.id"
                class="chat-entry__history-item"
                :class="{ 'is-active': item.id === currentChatId }"
                @click="selectChat(item)"
              >
                <div class="chat-entry__history-item-title ellipsis" :title="item.abstract">
                  {{ item.abstract || $t('chat.createChat') }}
                </div>
                <div v-if="item.update_time" class="chat-entry__history-item-time">
                  {{ datetimeFormat(item.update_time) }}
                </div>
              </div>
            </template>
            <div v-else-if="!chatLogLoading" class="chat-entry__history-empty">
              <el-text type="info" size="small">{{ $t('chat.noHistory') }}</el-text>
            </div>
          </el-scrollbar>
        </div>

        <!-- 对话窗口 -->
        <div class="chat-entry__chat dialog-bg">
          <AiChat
            :applicationDetails="backingApp"
            :appId="backingApp.id"
            :knowledgeIdList="selectedKnowledgeIds"
            :record="currentRecordList"
            :chatId="currentChatId"
            :persist-session="true"
            type="debug-ai-chat"
            @refresh="onChatRefresh"
            @scroll="handleChatScroll"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AiChat from '@/components/ai-chat/index.vue'
import ApplicationApi from '@/api/application/application'
import ChatLogApi from '@/api/application/chat-log'
import KnowledgeApi from '@/api/knowledge/knowledge'
import ModelApi from '@/api/model/model'
import useStore from '@/stores'
import { t } from '@/locales'
import { beforeDay, datetimeFormat, nowDate } from '@/utils/time'

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
/** 新对话占位 id —— AiChat 约定：chatId='new' 时本次发送会先 open 再发消息 */
const NEW_CHAT_ID = 'new'

const loading = ref(false)
const knowledgeList = ref<any[]>([])
const selectedKnowledgeIds = ref<string[]>([])
// 完整的应用详情对象，直接作为 AiChat 的 applicationDetails 传入
const backingApp = ref<any>(null)

// 历史对话——后端持久化（persist 调试会话），列表与记录均从对话日志接口拉取
const chatLogData = ref<any[]>([])
const chatLogLoading = ref(false)
// 当前会话 id：NEW_CHAT_ID 表示尚未开始的新对话
const currentChatId = ref<string>(NEW_CHAT_ID)
// 当前会话已加载的对话记录，作为 AiChat 的 record 传入
const currentRecordList = ref<any[]>([])
const recordLoading = ref(false)
const recordPagination = ref({ current_page: 1, page_size: 20, total: 0 })

const defaultPrompt = t('views.application.form.prompt.defaultPrompt', {
  data: '{data}',
  question: '{question}',
})

/**
 * 侧栏展示用列表：处于新对话状态时，在顶部插入一个占位项，
 * 让"新建对话"在发出第一条消息前也可见、可高亮。
 */
const displayChatList = computed<any[]>(() => {
  if (currentChatId.value === NEW_CHAT_ID) {
    return [{ id: NEW_CHAT_ID, abstract: t('chat.createChat') }, ...chatLogData.value]
  }
  return chatLogData.value
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
      // top_n=5 对"企业知识库"这种几十段落的库太小 —— 一个多字段问题
      // （如"公司概况"）需要同时命中执照/章程/征信/简历多份文档的段落，
      // 5 段会被段落数最多的那份文档（如 41 段的征信报告）挤占。15 段
      // ×~800 字 ≈ 12K 上下文，配 blend 模式召回更稳。similarity 0.5→0.3：
      // 0.5 把很多 0.3-0.5 的真相关段落也滤掉了。
      top_n: 15,
      similarity: 0.3,
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

/** 拉取专用助手的全部历史会话（按更新时间倒序，由后端返回） */
async function loadChatLogList() {
  if (!backingApp.value) return
  try {
    const res: any = await ChatLogApi.getChatLog(
      backingApp.value.id,
      { current_page: 1, page_size: 100 },
      // 对话日志接口要求传日期范围，这里取足够宽的窗口以涵盖全部历史
      { start_time: beforeDay(3650), end_time: nowDate },
      chatLogLoading,
    )
    chatLogData.value = Array.isArray(res?.data?.records) ? res.data.records : []
  } catch (e) {
    chatLogData.value = []
  }
}

/**
 * 加载某个历史会话的对话记录。order_asc=true：分页接口按时间倒序返回，
 * 即每页取较新的记录；向上翻页时把更旧的记录前插，最后按时间升序展示。
 */
function loadChatRecords(chatId: string) {
  return ChatLogApi.getChatRecordLog(
    backingApp.value.id,
    chatId,
    recordPagination.value,
    recordLoading,
    true,
  ).then((res: any) => {
    recordPagination.value.total = res?.data?.total || 0
    const list = (res?.data?.records || []).map((v: any) => ({
      ...v,
      write_ed: true,
      record_id: v.id,
    }))
    currentRecordList.value = [...list, ...currentRecordList.value].sort((a: any, b: any) =>
      (a.create_time || '').localeCompare(b.create_time || ''),
    )
  })
}

/** 切换到某个历史会话 / 新对话 */
function selectChat(item: any) {
  if (item.id === currentChatId.value) return
  if (item.id === NEW_CHAT_ID) {
    newChat()
    return
  }
  recordPagination.value.current_page = 1
  recordPagination.value.total = 0
  currentRecordList.value = []
  currentChatId.value = item.id
  loadChatRecords(item.id)
}

/** 开启一个新对话 */
function newChat() {
  recordPagination.value.current_page = 1
  recordPagination.value.total = 0
  currentRecordList.value = []
  currentChatId.value = NEW_CHAT_ID
}

/**
 * AiChat 在新对话发出首条消息、拿到真实 chat_id 后回调。
 * 此时后端已落库本次会话——刷新侧栏让它出现在历史列表中。
 */
async function onChatRefresh(newChatId: string) {
  currentChatId.value = newChatId
  await loadChatLogList()
}

/** 对话区滚动到顶部时，向上加载更早的对话记录 */
function handleChatScroll(event: any) {
  if (
    currentChatId.value !== NEW_CHAT_ID &&
    event.scrollTop === 0 &&
    recordPagination.value.total > currentRecordList.value.length
  ) {
    const prevHeight = event.dialogScrollbar.offsetHeight
    recordPagination.value.current_page += 1
    loadChatRecords(currentChatId.value).then(() => {
      event.scrollDiv.setScrollTop(event.dialogScrollbar.offsetHeight - prevHeight)
    })
  }
}

/**
 * 切换 / 关联知识库——会话级隔离：知识库变更必然意味着新的检索上下文，
 * 因此直接开启一个新对话（旧会话仍保留在历史列表中可随时回看）。
 */
function onKnowledgeChange(ids: string[]) {
  persistSelection(ids)
  newChat()
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
    await loadChatLogList()
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

  &__main {
    height: 100%;
    gap: 16px;
  }

  &__history {
    width: 260px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    box-sizing: border-box;
    overflow: hidden;
  }

  &__history-head {
    padding: 12px;
  }

  &__history-label {
    padding: 0 16px 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__history-list {
    flex: 1;
    min-height: 0;
    padding: 4px 8px 8px;
  }

  &__history-item {
    padding: 8px 12px;
    margin-bottom: 2px;
    border-radius: 6px;
    cursor: pointer;

    &:hover {
      background: var(--el-fill-color-light);
    }

    &.is-active {
      background: var(--el-color-primary-light-9);

      .chat-entry__history-item-title {
        color: var(--el-color-primary);
        font-weight: 500;
      }
    }
  }

  &__history-item-title {
    font-size: 14px;
    color: var(--el-text-color-regular);
    line-height: 20px;
  }

  &__history-item-time {
    margin-top: 2px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__history-empty {
    padding: 24px 12px;
    text-align: center;
  }

  &__chat {
    flex: 1;
    min-width: 0;
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
