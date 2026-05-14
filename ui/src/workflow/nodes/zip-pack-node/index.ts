import ZipPackNodeVue from './index.vue'
import { AppNode, AppNodeModel } from '@/workflow/common/app-node'
class ZipPackNode extends AppNode {
  constructor(props: any) {
    super(props, ZipPackNodeVue)
  }
}
export default {
  type: 'zip-pack-node',
  model: AppNodeModel,
  view: ZipPackNode,
}
