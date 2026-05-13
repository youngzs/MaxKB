<template>
  <div class="chat-entry p-16-24" v-loading="loading">
    <!-- 头部 -->
    <div class="chat-entry__header flex-between mb-16">
      <div>
        <h4>{{ $t('views.chatEntry.title') }}</h4>
        <el-text type="info" size="small">{{ $t('views.chatEntry.subTitle') }}</el-text>
      </div>
      <el-input
        v-model="search"
        :placeholder="$t('views.chatEntry.search.placeholder')"
        clearable
        style="width: 280px"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <!-- 最近使用 -->
    <div v-if="recentList.length > 0" class="mb-24">
      <div class="flex align-center mb-12">
        <AppIcon iconName="app-history-outlined" class="mr-8 color-secondary" />
        <h5 class="m-0">{{ $t('views.chatEntry.recent.title') }}</h5>
        <el-button
          link
          size="small"
          class="ml-auto"
          @click="clearRecent"
        >
          {{ $t('views.chatEntry.recent.clear') }}
        </el-button>
      </div>
      <el-row :gutter="12">
        <el-col
          v-for="item in recentList"
          :key="'recent-' + item.id"
          :xs="12" :sm="8" :md="6" :lg="4" :xl="4"
          class="mb-12"
        >
          <div
            class="chat-card chat-card--mini"
            @click="toChat(item)"
            tabindex="0"
            role="button"
          >
            <el-avatar shape="square" :size="32" class="mr-8">
              <img v-if="item.icon" :src="item.icon" />
              <AppIcon v-else iconName="app-agent" />
            </el-avatar>
            <div class="chat-card__title-block flex-1">
              <div class="chat-card__title">{{ item.name }}</div>
              <el-text class="color-secondary" size="small">{{ relativeTime(item.lastChatAt) }}</el-text>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 筛选 -->
    <div class="flex align-center mb-12">
      <el-radio-group v-model="typeFilter" size="small">
        <el-radio-button value="all">{{ $t('views.chatEntry.filter.all') }}（{{ baseList.length }}）</el-radio-button>
        <el-radio-button value="SIMPLE">{{ $t('views.chatEntry.card.simple') }}（{{ countByType('SIMPLE') }}）</el-radio-button>
        <el-radio-button value="WORK_FLOW">{{ $t('views.chatEntry.card.workflow') }}（{{ countByType('WORK_FLOW') }}）</el-radio-button>
      </el-radio-group>
      <el-text type="info" size="small" class="ml-auto">{{ $t('views.chatEntry.hint.onlyPublished') }}</el-text>
    </div>

    <!-- 卡片网格 -->
    <el-row :gutter="16" v-if="filteredList.length > 0">
      <el-col
        v-for="item in filteredList"
        :key="item.id"
        :xs="24" :sm="12" :md="12" :lg="8" :xl="6"
        class="mb-16"
      >
        <div
          class="chat-card"
          @click="toChat(item)"
          @keydown.enter="toChat(item)"
          tabindex="0"
          role="button"
        >
          <div class="chat-card__head flex align-center">
            <el-avatar shape="square" :size="40" class="mr-8">
              <img v-if="item.icon" :src="item.icon" />
              <AppIcon v-else iconName="app-agent" />
            </el-avatar>
            <div class="chat-card__title-block flex-1">
              <div class="chat-card__title">{{ item.name }}</div>
              <el-text class="color-secondary" size="small">
                {{ item.nick_name || '' }}
              </el-text>
            </div>
            <el-tag size="small" v-if="isWorkflow(item.type)">
              {{ $t('views.chatEntry.card.workflow') }}
            </el-tag>
            <el-tag size="small" type="info" v-else>
              {{ $t('views.chatEntry.card.simple') }}
            </el-tag>
          </div>

          <div class="chat-card__desc" :title="item.desc || ''">
            {{ item.desc || ' ' }}
          </div>

          <div class="chat-card__footer flex-between">
            <el-text size="small" class="color-secondary">
              {{ updatedLabel(item) }}
            </el-text>
            <el-button type="primary" plain size="small" @click.stop="toChat(item)">
              <AppIcon iconName="app-create-chat" class="mr-4" />
              {{ $t('views.chatEntry.card.chat') }}
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 空态 -->
    <el-empty
      v-if="!loading && filteredList.length === 0"
      :description="emptyDescription"
    >
      <template #image>
        <AppIcon iconName="app-user-chat" style="font-size: 60px; color: var(--el-color-info);" />
      </template>
      <div class="mt-8">
        <el-text type="info" size="small">{{ $t('views.chatEntry.empty.hint') }}</el-text>
      </div>
      <el-button type="primary" class="mt-12" @click="goCreateAgent">
        {{ $t('views.chatEntry.empty.goCreate') }}
      </el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import ApplicationApi from '@/api/application/application'
import useStore from '@/stores'
import { t } from '@/locales'

const router = useRouter()
const { application, user } = useStore()

const loading = ref(false)
const search = ref('')
const typeFilter = ref<'all' | 'SIMPLE' | 'WORK_FLOW'>('all')
const baseList = ref<any[]>([]) // 已发布的全集
const recentList = ref<any[]>([]) // 最近使用（含 lastChatAt）

// 「最近使用」最大显示数量
const RECENT_MAX = 6
// localStorage key（按 workspace 分桶，多 workspace 不会互相串）
const recentKey = computed(() => `chat-entry:recent:${user.getWorkspaceId() || 'default'}`)

function isWorkflow(type: string) {
  return type === 'WORK_FLOW'
}

function countByType(t: string) {
  return baseList.value.filter((x) => x.type === t).length
}

function updatedLabel(item: any) {
  const d = item.update_time || item.create_time
  if (!d) return ''
  try {
    return new Date(d).toLocaleString()
  } catch (e) {
    return d
  }
}

function relativeTime(ts: number) {
  if (!ts) return ''
  const diff = Date.now() - ts
  const m = Math.floor(diff / 60000)
  if (m < 1) return t('views.chatEntry.recent.justNow')
  if (m < 60) return t('views.chatEntry.recent.minutesAgo', { n: m })
  const h = Math.floor(m / 60)
  if (h < 24) return t('views.chatEntry.recent.hoursAgo', { n: h })
  const d = Math.floor(h / 24)
  if (d < 30) return t('views.chatEntry.recent.daysAgo', { n: d })
  return new Date(ts).toLocaleDateString()
}

const filteredList = computed(() => {
  const q = search.value.trim().toLowerCase()
  let list = baseList.value
  if (typeFilter.value !== 'all') {
    list = list.filter((x) => x.type === typeFilter.value)
  }
  if (q) {
    list = list.filter((x) => (x.name || '').toLowerCase().includes(q))
  }
  return list
})

const emptyDescription = computed(() =>
  search.value.trim()
    ? t('views.chatEntry.empty.noMatch')
    : t('views.chatEntry.empty.noPublished'),
)

async function loadList() {
  loading.value = true
  try {
    const res: any = await ApplicationApi.getAllApplication({} as any, loading)
    const all: any[] = Array.isArray(res?.data) ? res.data : []
    baseList.value = all.filter((x) => x.is_publish === true)
    rebuildRecentList()
  } catch (e) {
    baseList.value = []
  } finally {
    loading.value = false
  }
}

function readRecentEntries(): Array<{ id: string; lastChatAt: number }> {
  try {
    const raw = localStorage.getItem(recentKey.value)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((x) => x && x.id && typeof x.lastChatAt === 'number')
  } catch (e) {
    return []
  }
}

function writeRecentEntries(entries: Array<{ id: string; lastChatAt: number }>) {
  try {
    localStorage.setItem(recentKey.value, JSON.stringify(entries.slice(0, RECENT_MAX)))
  } catch (e) {
    // 配额满了就放弃，不影响主流程
  }
}

function rebuildRecentList() {
  const entries = readRecentEntries()
  // 把 entry 与最新的应用元数据合并（应用可能已被改名/删除）
  recentList.value = entries
    .map((e) => {
      const app = baseList.value.find((a) => a.id === e.id)
      return app ? { ...app, lastChatAt: e.lastChatAt } : null
    })
    .filter((x): x is any => x !== null)
    .sort((a, b) => b.lastChatAt - a.lastChatAt)
    .slice(0, RECENT_MAX)
}

function recordRecent(appId: string) {
  const entries = readRecentEntries().filter((e) => e.id !== appId)
  entries.unshift({ id: appId, lastChatAt: Date.now() })
  writeRecentEntries(entries)
  rebuildRecentList()
}

function clearRecent() {
  try { localStorage.removeItem(recentKey.value) } catch (e) {}
  recentList.value = []
}

function toChat(row: any) {
  // 复用 application/index.vue 的 toChat 逻辑
  const api =
    row.type === 'WORK_FLOW'
      ? (id: string) => ApplicationApi.getApplicationDetail(id)
      : (id: string) => Promise.resolve({ data: row })

  api(row.id).then((ok: any) => {
    let aips: Array<{ name: string; value: any }> = []
    try {
      const baseNodes = (ok?.data?.work_flow?.nodes || []).filter(
        (v: any) => v.id === 'base-node',
      )
      const lists = baseNodes.map((v: any) => {
        if (v?.properties?.api_input_field_list) {
          return v.properties.api_input_field_list.map((x: any) => ({
            name: x.variable,
            value: x.default_value,
          }))
        }
        if (v?.properties?.input_field_list) {
          return v.properties.input_field_list
            .filter((x: any) => x.assignment_method === 'api_input')
            .map((x: any) => ({ name: x.variable, value: x.default_value }))
        }
        return []
      })
      aips = lists.reduce((acc: any[], cur: any[]) => [...acc, ...cur], [])
    } catch (e) {
      aips = []
    }

    const params = new URLSearchParams()
    aips.forEach((p: any) => {
      if (p.name) params.append(p.name, p.value ?? '')
    })
    const qs = params.toString() ? '?' + params.toString() : ''

    ApplicationApi.getAccessToken(row.id, loading).then((res: any) => {
      const accessToken = res?.data?.access_token
      if (!accessToken) return
      recordRecent(row.id)
      const url = application.location + accessToken + qs
      window.open(url)
    })
  })
}

function goCreateAgent() {
  router.push({ name: 'application' })
}

onMounted(() => {
  loadList()
})
</script>

<style lang="scss" scoped>
.chat-entry {
  min-height: 100%;

  &__header {
    h4 {
      margin: 0 0 4px 0;
    }
  }
}

.chat-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.18s, transform 0.18s, border-color 0.18s;
  height: 100%;
  display: flex;
  flex-direction: column;
  outline: none;

  &--mini {
    padding: 10px 12px;
    flex-direction: row;
    align-items: center;
  }

  &:hover,
  &:focus {
    border-color: var(--el-color-primary);
    box-shadow: 0 4px 16px 0 rgba(var(--el-text-color-primary-rgb), 0.08);
    transform: translateY(-1px);
  }

  &__head {
    margin-bottom: 10px;
  }

  &__title {
    font-weight: 500;
    color: var(--el-text-color-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }

  &__title-block {
    overflow: hidden;
  }

  &__desc {
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.5;
    height: 42px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    margin-bottom: 12px;
  }

  &__footer {
    margin-top: auto;
  }
}
</style>
