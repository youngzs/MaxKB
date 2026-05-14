import DocxRenderNodeVue from './index.vue'
import { AppNode, AppNodeModel } from '@/workflow/common/app-node'
class DocxRenderNode extends AppNode {
  constructor(props: any) {
    super(props, DocxRenderNodeVue)
  }
}
export default {
  type: 'docx-render-node',
  model: AppNodeModel,
  view: DocxRenderNode,
}
