export default {
  title: '对话',
  subTitle: '基于知识库的智能问答',
  newChat: '新对话',
  kb: {
    label: '知识库',
    allKb: '全库对话',
    allKbTip: '开启后无需逐个勾选，自动检索工作空间内全部知识库（含后续新增）',
    allKbHint: '全库模式：正在综合检索全部 {n} 个知识库',
    placeholder: '选择知识库（可多选）',
    emptyHint: '尚未选择知识库，当前回答仅基于模型自身知识。选择一个或多个知识库后即可基于资料问答。',
    activeHint: '已关联 {n} 个知识库，将综合检索后统一作答',
    noKnowledge: '当前工作空间还没有知识库，请先到「知识库」中创建并上传资料。',
    updateFailed: '更新知识库失败，请重试',
  },
  noApp: {
    desc: '未找到可用的对话模型，无法初始化对话助手',
    goModel: '去配置模型',
  },
  dedicatedAppDesc: '「对话」入口专用的知识库问答助手，由系统自动维护。',
  prologue: '你好，我是知识库问答助手。请在上方选择知识库后向我提问。',
}
