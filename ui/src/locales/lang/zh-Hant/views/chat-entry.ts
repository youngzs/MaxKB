export default {
  title: '對話',
  subTitle: '基於知識庫的智能問答',
  newChat: '新對話',
  kb: {
    label: '知識庫',
    placeholder: '選擇知識庫（可多選）',
    emptyHint: '尚未選擇知識庫，目前回答僅基於模型自身知識。選擇一個或多個知識庫後即可基於資料問答。',
    activeHint: '已關聯 {n} 個知識庫，將綜合檢索後統一作答',
    noKnowledge: '目前工作空間還沒有知識庫，請先到「知識庫」中建立並上傳資料。',
    updateFailed: '更新知識庫失敗，請重試',
  },
  noApp: {
    desc: '未找到可用的對話模型，無法初始化對話助手',
    goModel: '去設定模型',
  },
  dedicatedAppDesc: '「對話」入口專用的知識庫問答助手，由系統自動維護。',
  prologue: '你好，我是知識庫問答助手。請在上方選擇知識庫後向我提問。',
}
