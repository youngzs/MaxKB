<template>
  <NodeContainer :nodeModel="nodeModel">
    <h5 class="title-decoration-1 mb-8">{{ $t('workflow.nodeSetting') }}</h5>
    <el-card shadow="never" class="card-never">
      <el-alert
        class="mb-16"
        type="info"
        :closable="false"
        show-icon
        title="财务确定性计算"
        :description="alertDesc"
      />
      <el-form
        ref="formRef"
        @submit.prevent
        :model="form_data"
        label-position="top"
        require-asterisk-position="right"
        label-width="auto"
      >
        <el-form-item label="函数" prop="function" :rules="{ required: true, message: '请选择函数', trigger: 'change' }">
          <el-select v-model="form_data.function" placeholder="选择函数" style="width: 100%">
            <el-option label="get_fact — 单点取数" value="get_fact" />
            <el-option label="compare_periods — 多期对比 + 同比" value="compare_periods" />
            <el-option label="ratio — 比率（如流动比率）" value="ratio" />
            <el-option label="sum_items — 多科目求和" value="sum_items" />
            <el-option label="list_facts — 列出某主体某期全部已抽科目" value="list_facts" />
            <el-option label="solvency_table — 偿债能力分析表（流动/速动/资产负债率 × 多期）" value="solvency_table" />
            <el-option label="profitability_table — 盈利能力分析表（毛利率/净利率/ROE × 多期）" value="profitability_table" />
            <el-option label="operation_table — 营运能力分析表（应收/存货/总资产周转率 × 多期）" value="operation_table" />
            <el-option label="financial_profile — 企业财务综合画像（规模+偿债+盈利+营运）" value="financial_profile" />
          </el-select>
        </el-form-item>

        <el-form-item label="主体名称 (entity)">
          <el-input v-model="form_data.entity" placeholder="如：盐城市保安服务有限公司" />
        </el-form-item>

        <el-form-item label="报告期 (period)" v-if="['get_fact','ratio','sum_items','list_facts'].includes(form_data.function)">
          <el-input v-model="form_data.period" placeholder="年度 2024 / 季度 2024Q1 / 月度 2024-03" />
        </el-form-item>

        <el-form-item label="多个报告期 (periods，分析表留空=自动取全部年度)" v-if="['compare_periods','solvency_table','profitability_table','operation_table','financial_profile'].includes(form_data.function)">
          <el-input v-model="periodsText" type="textarea" :rows="3" placeholder="每行一个，如:&#10;2023&#10;2024&#10;2025" @blur="onPeriodsBlur" />
        </el-form-item>

        <el-form-item label="科目 (line_item)" v-if="['get_fact','compare_periods'].includes(form_data.function)">
          <el-input v-model="form_data.line_item" placeholder="如：货币资金 / 主营业务收入 / 净利润" />
        </el-form-item>

        <el-form-item label="分子 (numerator)" v-if="form_data.function === 'ratio'">
          <el-input v-model="form_data.numerator" placeholder="如：流动资产合计" />
        </el-form-item>
        <el-form-item label="分母 (denominator)" v-if="form_data.function === 'ratio'">
          <el-input v-model="form_data.denominator" placeholder="如：流动负债合计" />
        </el-form-item>

        <el-form-item label="多个科目 (line_items)" v-if="form_data.function === 'sum_items'">
          <el-input v-model="lineItemsText" type="textarea" :rows="3" placeholder="每行一个，如:&#10;货币资金&#10;应收账款&#10;存货" @blur="onLineItemsBlur" />
        </el-form-item>

        <el-form-item label="报表类型 (可选)" v-if="!['list_facts','solvency_table','profitability_table','operation_table','financial_profile'].includes(form_data.function)">
          <el-select v-model="form_data.statement_type" clearable placeholder="不限" style="width: 100%">
            <el-option label="资产负债表" value="balance_sheet" />
            <el-option label="利润表" value="income_statement" />
            <el-option label="现金流量表" value="cash_flow" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>
  </NodeContainer>
</template>

<script setup lang="ts">
import NodeContainer from '@/workflow/common/NodeContainer.vue'
import { computed, ref, onMounted } from 'vue'
import { set } from 'lodash'

const props = defineProps<{ nodeModel: any }>()

const alertDesc =
  '从已抽取的 FinancialFact 表精确取数 + Python 算，不走 LLM。问“金额/比率/同比”类问题时上游路由到本节点。找不到数据时返回 found=false，调用方应降级到 RAG。'

const form = {
  function: 'get_fact',
  entity: '',
  period: '',
  periods: [] as string[],
  line_item: '',
  line_items: [] as string[],
  numerator: '',
  denominator: '',
  statement_type: '',
}

const form_data = computed({
  get: () => {
    if (props.nodeModel.properties.node_data) {
      return props.nodeModel.properties.node_data
    } else {
      set(props.nodeModel.properties, 'node_data', form)
    }
    return props.nodeModel.properties.node_data
  },
  set: (value) => {
    set(props.nodeModel.properties, 'node_data', value)
  },
})

// 多行 textarea 与数组字段的桥接
const periodsText = ref('')
const lineItemsText = ref('')

function _parseLines(raw: string): string[] {
  if (!raw) return []
  return raw.split(/\r?\n/).map((s) => s.trim()).filter((s) => s.length > 0)
}

function onPeriodsBlur() {
  form_data.value.periods = _parseLines(periodsText.value)
}

function onLineItemsBlur() {
  form_data.value.line_items = _parseLines(lineItemsText.value)
}

const formRef = ref<any>()
const validate = () => {
  return new Promise<void>((resolve, reject) => {
    if (!formRef.value) return resolve()
    formRef.value.validate((ok: boolean) => (ok ? resolve() : reject({ node: props.nodeModel })))
  })
}

onMounted(() => {
  // 初始化 textarea 显示值
  if (Array.isArray(form_data.value.periods)) {
    periodsText.value = form_data.value.periods.join('\n')
  }
  if (Array.isArray(form_data.value.line_items)) {
    lineItemsText.value = form_data.value.line_items.join('\n')
  }
})

defineExpose({ validate })
</script>
