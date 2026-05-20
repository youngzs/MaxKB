<template>
  <div class="pg">
    <!-- 月度刻度表头 -->
    <div class="pg__head">
      <div class="pg__namecol" />
      <div class="pg__track">
        <div
          v-for="tk in ticks"
          :key="'h' + tk.label"
          class="pg__tick"
          :style="{ left: tk.left + '%' }"
        >
          {{ tk.label }}
        </div>
      </div>
    </div>

    <!-- 项目行 -->
    <div
      v-for="p in projects"
      :key="p.id"
      class="pg__row"
      @click="emit('select', p)"
    >
      <div class="pg__namecol">
        <div class="pg__pname" :title="p.name">
          <span
            v-if="p.risk !== 'none'"
            class="pg__riskdot"
            :class="'is-' + p.risk"
          />
          {{ p.name }}
        </div>
        <div class="pg__pmeta">
          {{ $t('views.finance.project.projectType.' + p.project_type) }}
          · {{ ownerName(p.owner_id) }}
        </div>
      </div>
      <div class="pg__track">
        <div
          v-for="tk in ticks"
          :key="'g' + tk.label"
          class="pg__grid"
          :style="{ left: tk.left + '%' }"
        />
        <div class="pg__today" :style="{ left: todayLeft + '%' }" />
        <div class="pg__bar" :style="barStyle(p)">
          <el-tooltip
            v-for="s in p.stages"
            :key="s.id"
            placement="top"
            :show-after="150"
          >
            <template #content>
              <div class="pg__tip">
                <div class="pg__tip-t">{{ s.stage_label || s.stage_key }}</div>
                <div>{{ $t('views.finance.progressPage.stageStatus.' + s.status) }}</div>
                <div>
                  {{ $t('views.finance.progressPage.stageHeader.planned') }}：{{ fmtDate(s.planned_at) }}
                </div>
                <div>
                  {{ $t('views.finance.progressPage.stageHeader.actual') }}：{{ fmtDate(s.actual_at) }}
                </div>
                <template v-if="s.status === 'active' && p.risk !== 'none'">
                  <div
                    v-for="code in p.risk_reasons"
                    :key="code"
                    class="pg__tip-risk"
                  >
                    ⚠ {{ $t('views.finance.progressPage.risk.' + code) }}
                  </div>
                </template>
              </div>
            </template>
            <div
              class="pg__seg"
              :class="[
                'is-' + s.status,
                s.status === 'active' && p.risk !== 'none' ? 'risk-' + p.risk : '',
              ]"
            />
          </el-tooltip>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import moment from 'moment'
import type { GanttProject } from '@/api/finance/type'

const props = defineProps<{
  projects: GanttProject[]
  ownerNameMap: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'select', project: GanttProject): void
}>()

const DAY = 24 * 3600 * 1000

/** 单项目时间窗 [start, end]（毫秒）。end 取阶段日期最大值，无则 start+180d。 */
function projectSpan(p: GanttProject): { start: number; end: number } {
  const start = moment(p.created_at).valueOf()
  const dates: number[] = []
  p.stages.forEach((s) => {
    ;[s.planned_at, s.actual_at, s.entered_at].forEach((d) => {
      if (d) {
        const v = moment(d).valueOf()
        if (!Number.isNaN(v)) dates.push(v)
      }
    })
  })
  let end = dates.length ? Math.max(...dates) : start + 180 * DAY
  if (end <= start) end = start + 30 * DAY
  return { start, end }
}

const spans = computed(() => {
  const map = new Map<string, { start: number; end: number }>()
  props.projects.forEach((p) => map.set(p.id, projectSpan(p)))
  return map
})

/** 全局时间轴范围（含今天，两侧留白）。 */
const axis = computed(() => {
  const all: number[] = [Date.now()]
  spans.value.forEach((s) => {
    all.push(s.start, s.end)
  })
  let min = Math.min(...all)
  let max = Math.max(...all)
  if (max <= min) max = min + 180 * DAY
  const pad = (max - min) * 0.04
  return { min: min - pad, max: max + pad }
})

function pct(ms: number): number {
  const { min, max } = axis.value
  const v = ((ms - min) / (max - min)) * 100
  return Math.max(0, Math.min(100, v))
}

const todayLeft = computed(() => pct(Date.now()))

/** 月度刻度。 */
const ticks = computed(() => {
  const { min, max } = axis.value
  const out: { left: number; label: string }[] = []
  const cur = moment(min).startOf('month')
  const end = moment(max)
  let guard = 0
  while (cur.isSameOrBefore(end) && guard < 120) {
    const ms = cur.valueOf()
    if (ms >= min && ms <= max) {
      out.push({ left: pct(ms), label: cur.format('YYYY-MM') })
    }
    cur.add(1, 'month')
    guard += 1
  }
  return out
})

function barStyle(p: GanttProject) {
  const sp = spans.value.get(p.id)
  if (!sp) return { left: '0%', width: '0%' }
  const left = pct(sp.start)
  const right = pct(sp.end)
  return { left: `${left}%`, width: `${Math.max(right - left, 8)}%` }
}

function ownerName(id: string | null): string {
  if (!id) return '—'
  return props.ownerNameMap[id] || '—'
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  const m = moment(iso)
  return m.isValid() ? m.format('YYYY-MM-DD') : '—'
}
</script>

<style lang="scss" scoped>
.pg {
  width: 100%;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;

  &__head {
    display: flex;
    height: 30px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    background: var(--el-fill-color-light);
  }

  &__namecol {
    width: 220px;
    flex-shrink: 0;
    padding: 6px 12px;
    box-sizing: border-box;
    border-right: 1px solid var(--el-border-color-lighter);
    overflow: hidden;
  }

  &__track {
    position: relative;
    flex: 1;
    min-width: 0;
  }

  &__tick {
    position: absolute;
    top: 7px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    transform: translateX(-50%);
    white-space: nowrap;
  }

  &__row {
    display: flex;
    height: 54px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    cursor: pointer;

    &:last-child {
      border-bottom: none;
    }
    &:hover {
      background: var(--el-fill-color-light);
    }
  }

  &__pname {
    font-size: 14px;
    color: var(--el-text-color-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__pmeta {
    margin-top: 2px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__grid {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--el-border-color-lighter);
  }

  &__today {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--el-color-danger);
    opacity: 0.55;
  }

  &__bar {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 22px;
    display: flex;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--el-border-color);
    box-sizing: border-box;
  }

  &__seg {
    flex: 1;
    min-width: 0;
    border-right: 1px solid rgba(255, 255, 255, 0.7);

    &:last-child {
      border-right: none;
    }
    &.is-done {
      background: var(--el-color-success);
    }
    &.is-active {
      background: var(--el-color-primary);
    }
    &.is-pending {
      background: var(--el-fill-color-darker);
    }
    &.is-skipped {
      background: var(--el-color-info-light-5);
    }
    &.risk-yellow {
      box-shadow: inset 0 0 0 2px var(--el-color-warning);
    }
    &.risk-red {
      box-shadow: inset 0 0 0 2px var(--el-color-danger);
    }
  }

  &__riskdot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;

    &.is-yellow {
      background: var(--el-color-warning);
    }
    &.is-red {
      background: var(--el-color-danger);
    }
  }

  &__tip-t {
    font-weight: 600;
    margin-bottom: 2px;
  }

  &__tip-risk {
    margin-top: 2px;
    color: var(--el-color-warning-light-3);
  }
}
</style>
