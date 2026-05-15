export default {
  title: 'Chat',
  subTitle: 'Knowledge-based Q&A',
  newChat: 'New chat',
  kb: {
    label: 'Knowledge',
    placeholder: 'Select knowledge bases (multiple)',
    emptyHint:
      'No knowledge base selected — answers come from the model alone. Select one or more knowledge bases to ground answers on your documents.',
    activeHint: '{n} knowledge base(s) linked — answers are synthesized across all of them',
    noKnowledge:
      'This workspace has no knowledge base yet. Create one and upload documents under "Knowledge" first.',
    updateFailed: 'Failed to update knowledge bases, please retry',
  },
  noApp: {
    desc: 'No available chat model found — cannot initialize the assistant',
    goModel: 'Configure a model',
  },
  dedicatedAppDesc: 'Knowledge Q&A assistant dedicated to the Chat entry, maintained automatically.',
  prologue: 'Hi, I am the knowledge Q&A assistant. Pick a knowledge base above and ask me anything.',
}
