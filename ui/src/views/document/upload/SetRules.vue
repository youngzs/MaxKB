<template>
  <div class="set-rules">
    <el-row>
      <el-col :span="10" class="p-24">
        <h4 class="title-decoration-1 mb-16">{{ $t('views.document.setRules.title.setting') }}</h4>
        <div class="set-rules__right">
          <el-scrollbar>
            <div class="left-height" @click.stop>
              <el-radio-group v-model="radio" class="card__radio">
                <el-card shadow="never" class="mb-16" :class="radio === '1' ? 'border-active' : ''">
                  <el-radio value="1" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.intelligent.label') }}</p>
                    <el-text type="info">{{
                      $t('views.document.setRules.intelligent.text')
                    }}</el-text>
                  </el-radio>
                </el-card>
                <el-card shadow="never" class="mb-16" :class="radio === '2' ? 'border-active' : ''">
                  <el-radio value="2" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.advanced.label') }}</p>
                    <el-text type="info">
                      {{ $t('views.document.setRules.advanced.text') }}
                    </el-text>
                  </el-radio>

                  <el-card
                    v-if="radio === '2'"
                    shadow="never"
                    class="card-never mt-16"
                    style="margin-left: 30px"
                  >
                    <div class="set-rules__form">
                      <div class="form-item mb-16">
                        <div class="title flex align-center mb-8">
                          <span style="margin-right: 4px">{{
                            $t('views.document.setRules.patterns.label')
                          }}</span>
                          <el-tooltip
                            effect="dark"
                            :content="$t('views.document.setRules.patterns.tooltip')"
                            placement="right"
                          >
                            <AppIcon iconName="app-warning" class="app-warning-icon"></AppIcon>
                          </el-tooltip>
                        </div>
                        <div @click.stop>
                          <el-select
                            v-model="form.patterns"
                            multiple
                            :reserve-keyword="false"
                            allow-create
                            default-first-option
                            filterable
                            :placeholder="$t('views.document.setRules.patterns.placeholder')"
                          >
                            <el-option
                              v-for="(item, index) in splitPatternList"
                              :key="index"
                              :label="item.key"
                              :value="item.value"
                            >
                            </el-option>
                          </el-select>
                        </div>
                      </div>
                      <div class="form-item mb-16">
                        <div class="title mb-8">
                          {{ $t('views.document.setRules.limit.label') }}
                        </div>
                        <el-slider
                          v-model="form.limit"
                          show-input
                          :show-input-controls="false"
                          :min="50"
                          :max="100000"
                        />
                      </div>
                      <div class="form-item mb-16">
                        <div class="title mb-8">
                          {{ $t('views.document.setRules.with_filter.label') }}
                        </div>
                        <el-switch size="small" v-model="form.with_filter" />
                        <div style="margin-top: 4px">
                          <el-text type="info">
                            {{ $t('views.document.setRules.with_filter.text') }}</el-text
                          >
                        </div>
                      </div>
                    </div>
                  </el-card>
                </el-card>
              </el-radio-group>
            </div>
          </el-scrollbar>
          <div>
            <el-checkbox
              v-model="checkedConnect"
              @change="changeHandle"
              style="white-space: normal"
            >
              {{ $t('views.document.setRules.checkedConnect.label') }}
            </el-checkbox>
          </div>
          <div class="text-right mt-8">
            <el-button @click="splitDocument">
              {{ $t('views.document.buttons.preview') }}</el-button
            >
          </div>
        </div>
      </el-col>

      <el-col :span="14" class="p-24 border-l">
        <div v-loading="loading" :element-loading-text="progressText">
          <h4 class="title-decoration-1 mb-8">{{ $t('views.document.setRules.title.preview') }}</h4>

          <!-- 扫描版/CID 乱码 PDF 在预览阶段 0 段是正常的:这些文件需要 OCR 异步重抽,
               导入后会自动补内容。提示用户不要误以为解析失败。-->
          <el-alert
            v-if="hasEmptyPreviewDoc"
            type="info"
            :closable="false"
            show-icon
            class="mb-12"
          >
            <template #title>
              <span class="lighter">
                {{ emptyDocCount }} 个文档预览为空(扫描件 / 特殊字体 PDF / 图片)。
                导入后 OCR 会异步重抽,1-3 分钟后字符数会自动填充 ——
                <strong>正常点"开始导入"即可</strong>,不需要重新上传。
              </span>
            </template>
          </el-alert>

          <ParagraphPreview v-model:data="paragraphList" :isConnect="checkedConnect" :knowledge-id="id"/>
        </div>
      </el-col>
    </el-row>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
import ParagraphPreview from '@/views/knowledge/component/ParagraphPreview.vue'
import { useRoute } from 'vue-router'
import { cutFilename } from '@/utils/common'
import useStore from '@/stores'
import type { KeyValue } from '@/api/type/common'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { postSplitDocumentStream } from '@/api/knowledge/document'
const { knowledge } = useStore()
const documentsFiles = computed(() => knowledge.documentsFiles)
const splitPatternList = ref<Array<KeyValue<string, string>>>([])
const route = useRoute()
const {
  query: { id}, // id为knowledgeID
} = route as any

const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})

const radio = ref('1')
const loading = ref(false)
const progressText = ref('')
const paragraphList = ref<any[]>([])

// 是否有文档预览为空段 —— 扫描件 / CID 乱码 PDF / 图片走 OCR 异步路径,
// 在 sync split 阶段段落是空的,导入后 celery OCR 任务才会补内容。
// 提示用户这是正常的,不要误以为是解析失败。
const emptyDocCount = computed(
  () =>
    paragraphList.value.filter(
      (d: any) =>
        !d.content ||
        d.content.length === 0 ||
        d.content.every((p: any) => !(p.content || '').trim()),
    ).length,
)
const hasEmptyPreviewDoc = computed(
  () => paragraphList.value.length > 0 && emptyDocCount.value > 0,
)
const patternLoading = ref<boolean>(false)
const checkedConnect = ref<boolean>(false)

const firstChecked = ref(true)

const form = reactive<{
  patterns: Array<string>
  limit: number
  with_filter: boolean
  [propName: string]: any
}>({
  patterns: [],
  limit: 500,
  with_filter: true,
})

function changeHandle(val: boolean) {
  if (val && firstChecked.value) {
    paragraphList.value = paragraphList.value.map((item: any) => ({
      ...item,
      content: item.content.map((v: any) => ({
        ...v,
        problem_list: v.title.trim()
          ? [
              {
                content: v.title.trim(),
              },
            ]
          : [],
      })),
    }))
    firstChecked.value = false
  }
}
// 应用分段结果到预览（裁剪超长文件名 + 关联问题）
function applySplitResult(list: any[]) {
  list.map((item: any) => {
    if (item.name.length > 128) {
      item.name = cutFilename(item.name, 128)
    }
    if (checkedConnect.value) {
      item.content.map((v: any) => {
        v['problem_list'] = v.title.trim() ? [{ content: v.title.trim() }] : []
      })
    }
  })
  paragraphList.value = list
}

// 原同步分段：共享/资源管理场景使用，也是流式失败时的回退路径
function legacySplit(fd: FormData) {
  loadSharedApi({ type: 'document', systemType: apiType.value })
    .postSplitDocument(id, fd)
    .then((res: any) => {
      applySplitResult(res.data)
      loading.value = false
      progressText.value = ''
    })
    .catch(() => {
      loading.value = false
      progressText.value = ''
    })
}

// 读取 SSE 流：逐文件进度 + 末尾完整结果。返回最终分段 list。
async function readSplitStream(response: any): Promise<any[]> {
  if (!response || !response.body) {
    throw new Error('no stream body')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  let finalList: any[] | null = null
  let errMsg = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() || '' // 末段可能不完整，留待下一块
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      let obj: any
      try {
        obj = JSON.parse(line.slice(5).trim())
      } catch (e) {
        continue
      }
      if (obj.progress) {
        const p = obj.progress
        progressText.value =
          '正在解析 ' + p.current + '/' + p.total + (p.filename ? '：' + p.filename : '')
      } else if (obj.code === 500) {
        errMsg = obj.message || 'split failed'
      } else if (obj.data) {
        finalList = obj.data
      }
    }
  }
  if (errMsg) throw new Error(errMsg)
  return finalList || []
}

function splitDocument() {
  loading.value = true
  progressText.value = ''
  const fd = new FormData()
  // 与 file[] 等长追加 relative_paths[]。webkitdirectory 模式下
  // file.raw.webkitRelativePath 形如 '借款人资料/盐城市保安服务有限公司/营业执照.pdf'；
  // 单文件选择模式下 webkitRelativePath 是空字符串 —— 后端也接受空字符串作为"无路径"。
  documentsFiles.value.forEach((item) => {
    if (item?.raw) {
      fd.append('file', item?.raw)
      const rel = (item.raw as any)?.webkitRelativePath || ''
      fd.append('relative_paths', rel)
    }
  })
  if (radio.value === '2') {
    Object.keys(form).forEach((key) => {
      if (key == 'patterns') {
        form.patterns.forEach((item) => fd.append('patterns', item))
      } else {
        fd.append(key, form[key])
      }
    })
  }
  // workspace 知识库上传走流式 SSE（实时进度 + 防反代 504）；
  // 共享/资源管理场景接口前缀不同，沿用原同步；流式异常自动回退同步。
  if (apiType.value !== 'workspace') {
    legacySplit(fd)
    return
  }
  postSplitDocumentStream(id, fd)
    .then((response: any) => {
      if (response.status && response.status >= 400) {
        throw new Error('split http ' + response.status)
      }
      return readSplitStream(response)
    })
    .then((list: any[]) => {
      applySplitResult(list)
      loading.value = false
      progressText.value = ''
    })
    .catch(() => {
      // 流式失败 → 回退同步分段，保证功能不退化
      progressText.value = ''
      legacySplit(fd)
    })
}

const initSplitPatternList = () => {
  loadSharedApi({ type: 'document', systemType: apiType.value })
    .listSplitPattern(id, patternLoading)
    .then((ok: any) => {
      splitPatternList.value = ok.data
    })
}

watch(radio, () => {
  if (radio.value === '2') {
    initSplitPatternList()
  }
})

onMounted(() => {
  splitDocument()
})

defineExpose({
  paragraphList,
  checkedConnect,
  loading,
})
</script>
<style scoped lang="scss">
.set-rules {
  width: 100%;

  .left-height {
    max-height: calc(var(--create-knowledge-height) - 110px);
    overflow-x: hidden;
  }
  &__form {
    .title {
      font-size: 14px;
      font-weight: 400;
    }
  }
}
</style>
