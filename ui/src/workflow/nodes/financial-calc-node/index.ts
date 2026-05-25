import FinancialCalcNodeVue from './index.vue'
import { AppNode, AppNodeModel } from '@/workflow/common/app-node'
class FinancialCalcNode extends AppNode {
  constructor(props: any) {
    super(props, FinancialCalcNodeVue)
  }
}
export default {
  type: 'financial-calc-node',
  model: AppNodeModel,
  view: FinancialCalcNode,
}
