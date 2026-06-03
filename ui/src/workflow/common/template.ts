import { baseNodes } from '@/workflow/common/data'
export const applicationTemplate: any = {
  solvency: {"nodes": [{"id": "base-node", "type": "base-node", "x": 120, "y": 260, "properties": {"config": {}, "height": 600, "showNode": true, "stepName": "基本信息", "node_data": {"desc": "偿债能力分析表模板（流动/速动/资产负债率）", "name": "偿债能力分析", "prologue": "我可以一键计算某公司的偿债能力分析表（流动比率、速动比率、资产负债率），数据来自结构化财务三表。\n试试：丰县智禾现代农业有限公司的偿债能力分析", "tts_type": "BROWSER"}, "input_field_list": [], "user_input_config": {"title": "用户输入"}, "api_input_field_list": [], "user_input_field_list": []}}, {"id": "start-node", "type": "start-node", "x": 120, "y": 900, "properties": {"config": {"fields": [{"label": "用户问题", "value": "question"}], "globalFields": [{"label": "当前时间", "value": "time"}]}, "fields": [{"label": "用户问题", "value": "question"}], "height": 280, "showNode": true, "stepName": "开始", "globalFields": [{"label": "当前时间", "value": "time"}]}}, {"id": "fin-calc-1", "type": "financial-calc-node", "x": 560, "y": 420, "properties": {"config": {"fields": [{"label": "计算结果文本", "value": "data"}, {"label": "结果", "value": "result"}, {"label": "是否命中", "value": "found"}, {"label": "数据来源", "value": "sources"}, {"label": "函数", "value": "function"}, {"label": "提示", "value": "message"}]}, "height": 360, "showNode": true, "stepName": "财务计算", "node_data": {"function": "solvency_table", "entity": "{{开始.question}}", "period": "", "numerator": "", "denominator": "", "statement_type": "", "periods": [], "line_item": "", "line_items": []}}}, {"id": "ai-chat-1", "type": "ai-chat-node", "x": 1000, "y": 420, "properties": {"config": {"fields": [{"label": "AI 回答内容", "value": "answer"}]}, "height": 540, "showNode": true, "stepName": "AI合成", "node_data": {"prompt": "下面是从结构化资产负债表精确计算得到的偿债能力分析表：\n\n{{财务计算.data}}\n\n数据来源文档ID：{{财务计算.sources}}\n\n用户问题：{{开始.question}}\n\n请原样输出上面的 Markdown 表格并简评趋势；数据不足如实告知，不要编造。", "system": "你只能依据上面『财务计算』节点给出的表格作答，不得自行从原始报表重算或编造数字。", "model_id": "", "dialogue_number": 0, "is_result": true}}}], "edges": [{"id": "e1", "type": "app-edge", "properties": {}, "sourceNodeId": "start-node", "targetNodeId": "fin-calc-1", "sourceAnchorId": "start-node_right", "targetAnchorId": "fin-calc-1_left"}, {"id": "e2", "type": "app-edge", "properties": {}, "sourceNodeId": "fin-calc-1", "targetNodeId": "ai-chat-1", "sourceAnchorId": "fin-calc-1_right", "targetAnchorId": "ai-chat-1_left"}]},
  profitability: {"nodes": [{"id": "base-node", "type": "base-node", "x": 120, "y": 260, "properties": {"config": {}, "height": 600, "showNode": true, "stepName": "基本信息", "node_data": {"desc": "盈利能力分析表模板（毛利率/净利率/ROE）", "name": "盈利能力分析", "prologue": "我可以一键计算某公司的盈利能力分析表（毛利率、净利率、净资产收益率ROE）。\n试试：东海县拓诚餐饮管理有限公司的盈利能力分析", "tts_type": "BROWSER"}, "input_field_list": [], "user_input_config": {"title": "用户输入"}, "api_input_field_list": [], "user_input_field_list": []}}, {"id": "start-node", "type": "start-node", "x": 120, "y": 900, "properties": {"config": {"fields": [{"label": "用户问题", "value": "question"}], "globalFields": [{"label": "当前时间", "value": "time"}]}, "fields": [{"label": "用户问题", "value": "question"}], "height": 280, "showNode": true, "stepName": "开始", "globalFields": [{"label": "当前时间", "value": "time"}]}}, {"id": "fin-calc-1", "type": "financial-calc-node", "x": 560, "y": 420, "properties": {"config": {"fields": [{"label": "计算结果文本", "value": "data"}, {"label": "结果", "value": "result"}, {"label": "是否命中", "value": "found"}, {"label": "数据来源", "value": "sources"}, {"label": "函数", "value": "function"}, {"label": "提示", "value": "message"}]}, "height": 360, "showNode": true, "stepName": "财务计算", "node_data": {"function": "profitability_table", "entity": "{{开始.question}}", "period": "", "numerator": "", "denominator": "", "statement_type": "", "periods": [], "line_item": "", "line_items": []}}}, {"id": "ai-chat-1", "type": "ai-chat-node", "x": 1000, "y": 420, "properties": {"config": {"fields": [{"label": "AI 回答内容", "value": "answer"}]}, "height": 540, "showNode": true, "stepName": "AI合成", "node_data": {"prompt": "下面是从结构化利润表/资产负债表精确计算得到的盈利能力分析表：\n\n{{财务计算.data}}\n\n数据来源文档ID：{{财务计算.sources}}\n\n用户问题：{{开始.question}}\n\n请原样输出上面的 Markdown 表格并简评趋势；数据不足如实告知，不要编造。", "system": "你只能依据上面『财务计算』节点给出的表格作答，不得自行从原始报表重算或编造数字。", "model_id": "", "dialogue_number": 0, "is_result": true}}}], "edges": [{"id": "e1", "type": "app-edge", "properties": {}, "sourceNodeId": "start-node", "targetNodeId": "fin-calc-1", "sourceAnchorId": "start-node_right", "targetAnchorId": "fin-calc-1_left"}, {"id": "e2", "type": "app-edge", "properties": {}, "sourceNodeId": "fin-calc-1", "targetNodeId": "ai-chat-1", "sourceAnchorId": "fin-calc-1_right", "targetAnchorId": "ai-chat-1_left"}]},
  operation: {"nodes": [{"id": "base-node", "type": "base-node", "x": 120, "y": 260, "properties": {"config": {}, "height": 600, "showNode": true, "stepName": "基本信息", "node_data": {"desc": "营运能力分析表模板（应收/存货/总资产周转率）", "name": "营运能力分析", "prologue": "我可以一键计算某公司的营运能力分析表（应收账款/存货/总资产周转率）。\n试试：东海县拓诚餐饮管理有限公司的营运能力分析", "tts_type": "BROWSER"}, "input_field_list": [], "user_input_config": {"title": "用户输入"}, "api_input_field_list": [], "user_input_field_list": []}}, {"id": "start-node", "type": "start-node", "x": 120, "y": 900, "properties": {"config": {"fields": [{"label": "用户问题", "value": "question"}], "globalFields": [{"label": "当前时间", "value": "time"}]}, "fields": [{"label": "用户问题", "value": "question"}], "height": 280, "showNode": true, "stepName": "开始", "globalFields": [{"label": "当前时间", "value": "time"}]}}, {"id": "fin-calc-1", "type": "financial-calc-node", "x": 560, "y": 420, "properties": {"config": {"fields": [{"label": "计算结果文本", "value": "data"}, {"label": "结果", "value": "result"}, {"label": "是否命中", "value": "found"}, {"label": "数据来源", "value": "sources"}, {"label": "函数", "value": "function"}, {"label": "提示", "value": "message"}]}, "height": 360, "showNode": true, "stepName": "财务计算", "node_data": {"function": "operation_table", "entity": "{{开始.question}}", "period": "", "numerator": "", "denominator": "", "statement_type": "", "periods": [], "line_item": "", "line_items": []}}}, {"id": "ai-chat-1", "type": "ai-chat-node", "x": 1000, "y": 420, "properties": {"config": {"fields": [{"label": "AI 回答内容", "value": "answer"}]}, "height": 540, "showNode": true, "stepName": "AI合成", "node_data": {"prompt": "下面是从结构化三表精确计算得到的营运能力分析表：\n\n{{财务计算.data}}\n\n数据来源文档ID：{{财务计算.sources}}\n\n用户问题：{{开始.question}}\n\n请原样输出上面的 Markdown 表格并简评趋势；数据不足如实告知，不要编造。", "system": "你只能依据上面『财务计算』节点给出的表格作答，不得自行从原始报表重算或编造数字。", "model_id": "", "dialogue_number": 0, "is_result": true}}}], "edges": [{"id": "e1", "type": "app-edge", "properties": {}, "sourceNodeId": "start-node", "targetNodeId": "fin-calc-1", "sourceAnchorId": "start-node_right", "targetAnchorId": "fin-calc-1_left"}, {"id": "e2", "type": "app-edge", "properties": {}, "sourceNodeId": "fin-calc-1", "targetNodeId": "ai-chat-1", "sourceAnchorId": "fin-calc-1_right", "targetAnchorId": "ai-chat-1_left"}]},
  profile: {"nodes": [{"id": "base-node", "type": "base-node", "x": 120, "y": 260, "properties": {"config": {}, "height": 600, "showNode": true, "stepName": "基本信息", "node_data": {"desc": "企业财务综合画像模板（规模+偿债+盈利+营运）", "name": "企业财务综合画像", "prologue": "我可以一键输出某公司的财务综合画像：规模、偿债、盈利、营运四组表 + 综合点评。\n试试：丰县智禾现代农业有限公司财务综合画像", "tts_type": "BROWSER"}, "input_field_list": [], "user_input_config": {"title": "用户输入"}, "api_input_field_list": [], "user_input_field_list": []}}, {"id": "start-node", "type": "start-node", "x": 120, "y": 900, "properties": {"config": {"fields": [{"label": "用户问题", "value": "question"}], "globalFields": [{"label": "当前时间", "value": "time"}]}, "fields": [{"label": "用户问题", "value": "question"}], "height": 280, "showNode": true, "stepName": "开始", "globalFields": [{"label": "当前时间", "value": "time"}]}}, {"id": "fin-calc-1", "type": "financial-calc-node", "x": 560, "y": 420, "properties": {"config": {"fields": [{"label": "计算结果文本", "value": "data"}, {"label": "结果", "value": "result"}, {"label": "是否命中", "value": "found"}, {"label": "数据来源", "value": "sources"}, {"label": "函数", "value": "function"}, {"label": "提示", "value": "message"}]}, "height": 360, "showNode": true, "stepName": "财务计算", "node_data": {"function": "financial_profile", "entity": "{{开始.question}}", "period": "", "numerator": "", "denominator": "", "statement_type": "", "periods": [], "line_item": "", "line_items": []}}}, {"id": "ai-chat-1", "type": "ai-chat-node", "x": 1000, "y": 420, "properties": {"config": {"fields": [{"label": "AI 回答内容", "value": "answer"}]}, "height": 540, "showNode": true, "stepName": "AI合成", "node_data": {"prompt": "下面是某企业财务综合画像（规模/偿债/盈利/营运四组表）：\n\n{{财务计算.data}}\n\n数据来源文档ID：{{财务计算.sources}}\n\n用户问题：{{开始.question}}\n\n请原样输出全部表格（保留四个小标题），并在末尾给出【综合点评】从四维度各一句话总结财务状况与融资风险关注点；数据不足如实告知。", "system": "你只能依据上面『财务计算』节点给出的表格作答，不得自行从原始报表重算或编造数字。", "model_id": "", "dialogue_number": 0, "is_result": true}}}], "edges": [{"id": "e1", "type": "app-edge", "properties": {}, "sourceNodeId": "start-node", "targetNodeId": "fin-calc-1", "sourceAnchorId": "start-node_right", "targetAnchorId": "fin-calc-1_left"}, {"id": "e2", "type": "app-edge", "properties": {}, "sourceNodeId": "fin-calc-1", "targetNodeId": "ai-chat-1", "sourceAnchorId": "fin-calc-1_right", "targetAnchorId": "ai-chat-1_left"}]},
  duediligence: {"nodes": [{"id": "base-node", "type": "base-node", "x": 120, "y": 260, "properties": {"config": {}, "height": 600, "showNode": true, "stepName": "基本信息", "node_data": {"desc": "尽调要点问答模板（单公司RAG，使用前请在尽调检索节点选知识库）", "name": "尽调要点问答", "prologue": "我是融资尽调助手，基于知识库回答工商/股东/征信/担保/财务尽调问题。\n注意：使用前请在『尽调检索』节点选择要查询的知识库。\n试试：某公司的工商基本信息和担保关系", "tts_type": "BROWSER"}, "input_field_list": [], "user_input_config": {"title": "用户输入"}, "api_input_field_list": [], "user_input_field_list": []}}, {"id": "start-node", "type": "start-node", "x": 120, "y": 900, "properties": {"config": {"fields": [{"label": "用户问题", "value": "question"}], "globalFields": [{"label": "当前时间", "value": "time"}]}, "fields": [{"label": "用户问题", "value": "question"}], "height": 280, "showNode": true, "stepName": "开始", "globalFields": [{"label": "当前时间", "value": "time"}]}}, {"id": "search-1", "type": "search-knowledge-node", "x": 560, "y": 420, "properties": {"config": {"fields": [{"label": "检索结果的分段列表", "value": "paragraph_list"}, {"label": "检索结果", "value": "data"}]}, "height": 480, "showNode": true, "stepName": "尽调检索", "node_data": {"show_knowledge": false, "knowledge_id_list": [], "knowledge_setting": {"top_n": 30, "similarity": 0.3, "search_mode": "blend", "max_paragraph_char_number": 40000}, "search_scope_type": "custom", "search_scope_source": "knowledge", "search_scope_reference": [], "question_reference_address": ["start-node", "question"]}}}, {"id": "ai-chat-1", "type": "ai-chat-node", "x": 1000, "y": 420, "properties": {"config": {"fields": [{"label": "AI 回答内容", "value": "answer"}]}, "height": 540, "showNode": true, "stepName": "AI合成", "node_data": {"prompt": "你是融资尽职调查助手。下面是检索到的相关资料：\n\n{{尽调检索.data}}\n\n用户问题：{{开始.question}}\n\n请基于资料给出尽调结论；若问综合尽调，按【工商基本信息/股东与法人/经营与征信/担保与反担保/财务概况/风险提示】分点。只依据检索资料，缺失写“资料未涉及”，不要编造。", "system": "你是严谨的融资尽调助手，只依据检索到的资料作答，不编造。", "model_id": "", "dialogue_number": 0, "is_result": true}}}], "edges": [{"id": "e1", "type": "app-edge", "properties": {}, "sourceNodeId": "start-node", "targetNodeId": "search-1", "sourceAnchorId": "start-node_right", "targetAnchorId": "search-1_left"}, {"id": "e2", "type": "app-edge", "properties": {}, "sourceNodeId": "search-1", "targetNodeId": "ai-chat-1", "sourceAnchorId": "search-1_right", "targetAnchorId": "ai-chat-1_left"}]},
  blank: {
    edges: [],
    nodes: baseNodes,
  },
  assistant: {
    nodes: [
      {
        id: 'base-node',
        type: 'base-node',
        x: 120,
        y: 260.30849999999987,
        properties: {
          config: {},
          height: 734.766,
          showNode: true,
          stepName: '基本信息',
          node_data: {
            desc: '模板',
            name: '知识库问答助手',
            prologue:
              '您好，我是 XXX 小助手，您可以向我提出 XXX 使用问题。\n- XXX 主要功能有什么？\n- XXX 如何收费？\n- 需要转人工服务',
            tts_type: 'BROWSER',
          },
          input_field_list: [],
          user_input_config: {
            title: '用户输入',
          },
          api_input_field_list: [],
          user_input_field_list: [],
        },
      },
      {
        id: 'start-node',
        type: 'start-node',
        x: 120,
        y: 929.6914999999999,
        properties: {
          config: {
            fields: [
              {
                label: '用户问题',
                value: 'question',
              },
            ],
            globalFields: [
              {
                label: '当前时间',
                value: 'time',
              },
              {
                label: '历史聊天记录',
                value: 'history_context',
              },
              {
                label: '对话 ID',
                value: 'chat_id',
              },
            ],
          },
          fields: [
            {
              label: '用户问题',
              value: 'question',
            },
          ],
          height: 364,
          showNode: true,
          stepName: '开始',
          globalFields: [
            {
              label: '当前时间',
              value: 'time',
            },
          ],
        },
      },
      {
        id: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605',
        type: 'search-knowledge-node',
        x: 710,
        y: 929.6914999999999,
        properties: {
          config: {
            fields: [
              {
                label: '检索结果的分段列表',
                value: 'paragraph_list',
              },
              {
                label: '满足直接回答的分段列表',
                value: 'is_hit_handling_method_list',
              },
              {
                label: '检索结果',
                value: 'data',
              },
              {
                label: '满足直接回答的分段内容',
                value: 'directly_return',
              },
            ],
          },
          height: 794,
          showNode: true,
          stepName: '知识库检索',
          condition: 'AND',
          node_data: {
            knowledge_id_list: [],
            knowledge_setting: {
              top_n: 3,
              similarity: 0.6,
              search_mode: 'embedding',
              max_paragraph_char_number: 5000,
            },
            tag_filter: [],
            question_reference_address: ['start-node', 'question'],
            all_knowledge_id_list: [],
            knowledge_list: [],
          },
        },
      },
      {
        id: '420a6e4f-44ff-4847-bb81-0923630846b5',
        type: 'condition-node',
        x: 1300,
        y: 929.6914999999999,
        properties: {
          width: 600,
          config: {
            fields: [
              {
                label: '分支名称',
                value: 'branch_name',
              },
            ],
          },
          height: 544.148,
          showNode: true,
          stepName: '判断器',
          condition: 'AND',
          node_data: {
            branch: [
              {
                id: '7887',
                type: 'IF',
                condition: 'and',
                conditions: [
                  {
                    field: ['fd0324fc-f5e4-4fa6-a2d9-cb251b467605', 'is_hit_handling_method_list'],
                    value: 1,
                    compare: 'is_not_null',
                  },
                ],
              },
              {
                id: '6847',
                type: 'ELSE IF 1',
                condition: 'and',
                conditions: [
                  {
                    field: ['fd0324fc-f5e4-4fa6-a2d9-cb251b467605', 'paragraph_list'],
                    value: 1,
                    compare: 'is_not_null',
                  },
                ],
              },
              {
                id: '2794',
                type: 'ELSE',
                condition: 'and',
                conditions: [],
              },
            ],
          },
          branch_condition_list: [
            {
              index: 0,
              height: 121.383,
              id: '7887',
            },
            {
              index: 1,
              height: 121.383,
              id: '6847',
            },
            {
              index: 2,
              height: 44,
              id: '2794',
            },
          ],
        },
      },
      {
        id: '36a440a9-5b00-4d82-b13a-8e7819112918',
        type: 'reply-node',
        x: 1890,
        y: 120,
        properties: {
          config: {
            fields: [
              {
                label: '内容',
                value: 'answer',
              },
            ],
          },
          height: 386,
          showNode: true,
          stepName: '指定回复',
          condition: 'AND',
          node_data: {
            fields: ['fd0324fc-f5e4-4fa6-a2d9-cb251b467605', 'directly_return'],
            content: '',
            is_result: true,
            reply_type: 'referencing',
          },
        },
      },
      {
        id: 'f7c3b4a2-cb80-4e47-b050-7fef0315daaf',
        type: 'ai-chat-node',
        x: 1890,
        y: 929.6914999999999,
        properties: {
          config: {
            fields: [
              {
                label: 'AI 回答内容',
                value: 'answer',
              },
              {
                label: '思考过程',
                value: 'reasoning_content',
              },
            ],
          },
          height: 993.383,
          showNode: true,
          stepName: 'AI 对话',
          condition: 'AND',
          node_data: {
            prompt: '已知信息：\n{{知识库检索.data}}\n问题：\n{{开始.question}}',
            system: '',
            model_id: '',
            is_result: true,
            max_tokens: null,
            temperature: null,
            dialogue_type: 'WORKFLOW',
            model_setting: {
              reasoning_content_end: '</think>',
              reasoning_content_start: '<think>',
              reasoning_content_enable: false,
            },
            dialogue_number: 1,
          },
        },
      },
      {
        id: '04dd6c1e-95f9-4757-bb3e-134d503fce54',
        type: 'reply-node',
        x: 1890,
        y: 1798.383,
        properties: {
          config: {
            fields: [
              {
                label: '内容',
                value: 'answer',
              },
            ],
          },
          height: 504,
          showNode: true,
          stepName: '指定回复1',
          condition: 'AND',
          node_data: {
            fields: [],
            content: '抱歉，没有在知识库查询到相关内容，请提供更详细的信息。',
            is_result: true,
            reply_type: 'content',
          },
        },
      },
    ],
    edges: [
      {
        id: '73f8992c-65ef-409a-a151-378d0927f2aa',
        type: 'app-edge',
        sourceNodeId: 'start-node',
        targetNodeId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605',
        startPoint: {
          x: 280,
          y: 929.6914999999999,
        },
        endPoint: {
          x: 550,
          y: 929.6914999999999,
        },
        properties: {},
        pointsList: [
          {
            x: 280,
            y: 929.6914999999999,
          },
          {
            x: 390,
            y: 929.6914999999999,
          },
          {
            x: 440,
            y: 929.6914999999999,
          },
          {
            x: 550,
            y: 929.6914999999999,
          },
        ],
        sourceAnchorId: 'start-node_right',
        targetAnchorId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605_left',
      },
      {
        id: '6a8d23d9-5179-424e-80c2-f08d37cdb8d4',
        type: 'app-edge',
        sourceNodeId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605',
        targetNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        startPoint: {
          x: 870,
          y: 929.6914999999999,
        },
        endPoint: {
          x: 1010,
          y: 929.6914999999999,
        },
        properties: {},
        pointsList: [
          {
            x: 870,
            y: 929.6914999999999,
          },
          {
            x: 980,
            y: 929.6914999999999,
          },
          {
            x: 900,
            y: 929.6914999999999,
          },
          {
            x: 1010,
            y: 929.6914999999999,
          },
        ],
        sourceAnchorId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605_right',
        targetAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_left',
      },
      {
        id: '56006748-d9fe-491b-a14b-04fd568cac08',
        type: 'app-edge',
        sourceNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        targetNodeId: '36a440a9-5b00-4d82-b13a-8e7819112918',
        startPoint: {
          x: 1590,
          y: 793.3089999999999,
        },
        endPoint: {
          x: 1730,
          y: 120,
        },
        properties: {},
        pointsList: [
          {
            x: 1590,
            y: 793.3089999999999,
          },
          {
            x: 1700,
            y: 793.3089999999999,
          },
          {
            x: 1620,
            y: 120,
          },
          {
            x: 1730,
            y: 120,
          },
        ],
        sourceAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_7887_right',
        targetAnchorId: '36a440a9-5b00-4d82-b13a-8e7819112918_left',
      },
      {
        id: '9bc8721b-07aa-4730-9347-910ed64e26b9',
        type: 'app-edge',
        sourceNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        targetNodeId: 'f7c3b4a2-cb80-4e47-b050-7fef0315daaf',
        startPoint: {
          x: 1590,
          y: 922.6919999999999,
        },
        endPoint: {
          x: 1730,
          y: 929.6914999999999,
        },
        properties: {},
        pointsList: [
          {
            x: 1590,
            y: 922.6919999999999,
          },
          {
            x: 1700,
            y: 922.6919999999999,
          },
          {
            x: 1620,
            y: 929.6914999999999,
          },
          {
            x: 1730,
            y: 929.6914999999999,
          },
        ],
        sourceAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_6847_right',
        targetAnchorId: 'f7c3b4a2-cb80-4e47-b050-7fef0315daaf_left',
      },
      {
        id: 'c276a5b6-ec29-4ab9-b911-a0a929ff193f',
        type: 'app-edge',
        sourceNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        targetNodeId: '04dd6c1e-95f9-4757-bb3e-134d503fce54',
        startPoint: {
          x: 1590,
          y: 1013.3834999999998,
        },
        endPoint: {
          x: 1730,
          y: 1798.383,
        },
        properties: {},
        pointsList: [
          {
            x: 1590,
            y: 1013.3834999999998,
          },
          {
            x: 1700,
            y: 1013.3834999999998,
          },
          {
            x: 1620,
            y: 1798.383,
          },
          {
            x: 1730,
            y: 1798.383,
          },
        ],
        sourceAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_2794_right',
        targetAnchorId: '04dd6c1e-95f9-4757-bb3e-134d503fce54_left',
      },
    ],
  },
  // 财务问答模板:assistant 模板的财务定制版。
  // 适用场景:知识库里已经通过 Phase 1-3 入了审计报告/财务报表 PDF
  // (OCR 已经把 HTML 表格转成标准 markdown 表格,带具体数字)。
  //
  // 关键差异 vs assistant:
  // - search-knowledge tag_filter 预设 doc_type=审计报告/财务报表,只查带数据的文档
  // - top_n 15 + max_paragraph_char_number 15000:财务表格长,需要更多上下文
  // - ai-chat system prompt 强调"用表格里的数字回答 + 标注来源"
  // - prologue 引导用户问数字类问题
  finance: {
    nodes: [
      {
        id: 'base-node',
        type: 'base-node',
        x: 120,
        y: 260.30849999999987,
        properties: {
          config: {},
          height: 734.766,
          showNode: true,
          stepName: '基本信息',
          node_data: {
            desc: '财务问答模板',
            name: '财务问答助手',
            prologue:
              '我是财务问答助手,可以基于知识库里的审计报告和财务报表回答你的问题。\n你可以问:\n- 2024 年净利润是多少?\n- 营业收入近三年变化趋势\n- 资产负债率是多少?\n- 期末货币资金多少?',
            tts_type: 'BROWSER',
          },
          input_field_list: [],
          user_input_config: {
            title: '用户输入',
          },
          api_input_field_list: [],
          user_input_field_list: [],
        },
      },
      {
        id: 'start-node',
        type: 'start-node',
        x: 120,
        y: 929.6914999999999,
        properties: {
          config: {
            fields: [
              {
                label: '用户问题',
                value: 'question',
              },
            ],
            globalFields: [
              {
                label: '当前时间',
                value: 'time',
              },
              {
                label: '历史聊天记录',
                value: 'history_context',
              },
              {
                label: '对话 ID',
                value: 'chat_id',
              },
            ],
          },
          fields: [
            {
              label: '用户问题',
              value: 'question',
            },
          ],
          height: 364,
          showNode: true,
          stepName: '开始',
          globalFields: [
            {
              label: '当前时间',
              value: 'time',
            },
          ],
        },
      },
      {
        id: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605',
        type: 'search-knowledge-node',
        x: 710,
        y: 929.6914999999999,
        properties: {
          config: {
            fields: [
              { label: '检索结果的分段列表', value: 'paragraph_list' },
              { label: '满足直接回答的分段列表', value: 'is_hit_handling_method_list' },
              { label: '检索结果', value: 'data' },
              { label: '满足直接回答的分段内容', value: 'directly_return' },
            ],
          },
          height: 794,
          showNode: true,
          stepName: '知识库检索',
          condition: 'AND',
          node_data: {
            knowledge_id_list: [],
            knowledge_setting: {
              // 财务表跨多段:放大 top_n + 上下文窗口
              top_n: 15,
              similarity: 0.5,
              search_mode: 'embedding',
              max_paragraph_char_number: 15000,
            },
            // 预设标签:只查带数据的文档。同 key 多 value=OR。
            // 用户上传时只要 doc_type 自动打标命中(Phase 2 已完成),就能精确召回。
            tag_filter: [
              { key: 'doc_type', value: '审计报告' },
              { key: 'doc_type', value: '财务报表' },
            ],
            question_reference_address: ['start-node', 'question'],
            all_knowledge_id_list: [],
            knowledge_list: [],
          },
        },
      },
      {
        id: '420a6e4f-44ff-4847-bb81-0923630846b5',
        type: 'condition-node',
        x: 1300,
        y: 929.6914999999999,
        properties: {
          width: 600,
          config: {
            fields: [{ label: '分支名称', value: 'branch_name' }],
          },
          height: 544.148,
          showNode: true,
          stepName: '判断器',
          condition: 'AND',
          node_data: {
            branch: [
              {
                id: '6847',
                type: 'IF',
                condition: 'and',
                conditions: [
                  {
                    field: ['fd0324fc-f5e4-4fa6-a2d9-cb251b467605', 'paragraph_list'],
                    value: 1,
                    compare: 'is_not_null',
                  },
                ],
              },
              { id: '2794', type: 'ELSE', condition: 'and', conditions: [] },
            ],
          },
          branch_condition_list: [
            { index: 0, height: 121.383, id: '6847' },
            { index: 1, height: 44, id: '2794' },
          ],
        },
      },
      {
        id: 'f7c3b4a2-cb80-4e47-b050-7fef0315daaf',
        type: 'ai-chat-node',
        x: 1890,
        y: 929.6914999999999,
        properties: {
          config: {
            fields: [
              { label: 'AI 回答内容', value: 'answer' },
              { label: '思考过程', value: 'reasoning_content' },
            ],
          },
          height: 993.383,
          showNode: true,
          stepName: 'AI 对话',
          condition: 'AND',
          node_data: {
            // 财务专用 system prompt:强调结构化数据 + 引用规范
            system:
              '你是一名严谨的财务问答助手,服务对象是融资分析师。\n\n' +
              '工作准则:\n' +
              '1. 知识库召回的段落含审计报告/财务报表的 markdown 表格 (带 |---|---| 分隔,数字精确到小数点)。' +
              '回答数字类问题时,必须直接引用表格里的精确数字,不要四舍五入也不要自己计算 (除非用户明确要求)。\n' +
              '2. 每条数字回答都标注 [来源:文档名 / 报告期],例如:净利润 28,828,115.03 元 [来源:道其2025审计报告 / 本期金额]。\n' +
              '3. 如果用户问的数字在已召回的段落中找不到,明确说"该数据未在已收录的报表中找到",' +
              '不要猜测、不要按比例推算。\n' +
              '4. 跨期对比(同比/环比)时,先列出各期原值,再算变化率,展示计算过程。\n' +
              '5. 用清晰的 markdown 表格呈现多期/多科目对比;单项查询直接回答数字+单位+期间。\n' +
              '6. 财务术语用规范说法 (营业收入 / 净利润 / 资产合计 / 负债合计 / 所有者权益 等);避免口语化。',
            prompt:
              '【知识库召回的财务报表段落】\n{{知识库检索.data}}\n\n' +
              '【用户问题】\n{{开始.question}}\n\n' +
              '请基于上面的报表数据回答用户问题。',
            model_id: '',
            is_result: true,
            max_tokens: null,
            temperature: null,
            dialogue_type: 'WORKFLOW',
            model_setting: {
              reasoning_content_end: '</think>',
              reasoning_content_start: '<think>',
              reasoning_content_enable: false,
            },
            dialogue_number: 1,
          },
        },
      },
      {
        id: '04dd6c1e-95f9-4757-bb3e-134d503fce54',
        type: 'reply-node',
        x: 1890,
        y: 1798.383,
        properties: {
          config: {
            fields: [{ label: '内容', value: 'answer' }],
          },
          height: 504,
          showNode: true,
          stepName: '指定回复',
          condition: 'AND',
          node_data: {
            fields: [],
            content:
              '抱歉,我没有在知识库找到与你问题相关的财务数据。可能原因:\n' +
              '- 该公司/期间的审计报告还没入知识库\n' +
              '- 上传的文档没有被标记为"审计报告"或"财务报表"\n' +
              '- 问题中的科目名与报表里的标准名不一致(试试用规范说法,如"营业收入"而非"销售额")',
            is_result: true,
            reply_type: 'content',
          },
        },
      },
    ],
    edges: [
      {
        id: '73f8992c-65ef-409a-a151-378d0927f2aa',
        type: 'app-edge',
        sourceNodeId: 'start-node',
        targetNodeId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605',
        startPoint: { x: 280, y: 929.6914999999999 },
        endPoint: { x: 550, y: 929.6914999999999 },
        properties: {},
        pointsList: [
          { x: 280, y: 929.6914999999999 },
          { x: 390, y: 929.6914999999999 },
          { x: 440, y: 929.6914999999999 },
          { x: 550, y: 929.6914999999999 },
        ],
        sourceAnchorId: 'start-node_right',
        targetAnchorId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605_left',
      },
      {
        id: '6a8d23d9-5179-424e-80c2-f08d37cdb8d4',
        type: 'app-edge',
        sourceNodeId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605',
        targetNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        startPoint: { x: 870, y: 929.6914999999999 },
        endPoint: { x: 1010, y: 929.6914999999999 },
        properties: {},
        pointsList: [
          { x: 870, y: 929.6914999999999 },
          { x: 980, y: 929.6914999999999 },
          { x: 900, y: 929.6914999999999 },
          { x: 1010, y: 929.6914999999999 },
        ],
        sourceAnchorId: 'fd0324fc-f5e4-4fa6-a2d9-cb251b467605_right',
        targetAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_left',
      },
      {
        id: '9bc8721b-07aa-4730-9347-910ed64e26b9',
        type: 'app-edge',
        sourceNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        targetNodeId: 'f7c3b4a2-cb80-4e47-b050-7fef0315daaf',
        startPoint: { x: 1590, y: 922.6919999999999 },
        endPoint: { x: 1730, y: 929.6914999999999 },
        properties: {},
        pointsList: [
          { x: 1590, y: 922.6919999999999 },
          { x: 1700, y: 922.6919999999999 },
          { x: 1620, y: 929.6914999999999 },
          { x: 1730, y: 929.6914999999999 },
        ],
        sourceAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_6847_right',
        targetAnchorId: 'f7c3b4a2-cb80-4e47-b050-7fef0315daaf_left',
      },
      {
        id: 'c276a5b6-ec29-4ab9-b911-a0a929ff193f',
        type: 'app-edge',
        sourceNodeId: '420a6e4f-44ff-4847-bb81-0923630846b5',
        targetNodeId: '04dd6c1e-95f9-4757-bb3e-134d503fce54',
        startPoint: { x: 1590, y: 1013.3834999999998 },
        endPoint: { x: 1730, y: 1798.383 },
        properties: {},
        pointsList: [
          { x: 1590, y: 1013.3834999999998 },
          { x: 1700, y: 1013.3834999999998 },
          { x: 1620, y: 1798.383 },
          { x: 1730, y: 1798.383 },
        ],
        sourceAnchorId: '420a6e4f-44ff-4847-bb81-0923630846b5_2794_right',
        targetAnchorId: '04dd6c1e-95f9-4757-bb3e-134d503fce54_left',
      },
    ],
  },
}

export const knowledgeTemplate: any = {
  default: {
    edges: [
      {
        id: '846dd161-450e-4d2f-8119-78557d88421c',
        type: 'app-edge',
        endPoint: {
          x: 550,
          y: 720,
        },
        pointsList: [
          {
            x: 280,
            y: 720,
          },
          {
            x: 390,
            y: 720,
          },
          {
            x: 440,
            y: 720,
          },
          {
            x: 550,
            y: 720,
          },
        ],
        properties: {},
        startPoint: {
          x: 280,
          y: 720,
        },
        sourceNodeId: '768aed24-8139-4689-870f-2065ef05473c',
        targetNodeId: '1bed736e-711f-4afd-8454-2c8502444af7',
        sourceAnchorId: '768aed24-8139-4689-870f-2065ef05473c_right',
        targetAnchorId: '1bed736e-711f-4afd-8454-2c8502444af7_left',
      },
      {
        id: '79cf563e-0b4d-4d41-ad6f-4ee0c6042af6',
        type: 'app-edge',
        endPoint: {
          x: 1010,
          y: 720,
        },
        pointsList: [
          {
            x: 870,
            y: 720,
          },
          {
            x: 980,
            y: 720,
          },
          {
            x: 900,
            y: 720,
          },
          {
            x: 1010,
            y: 720,
          },
        ],
        properties: {},
        startPoint: {
          x: 870,
          y: 720,
        },
        sourceNodeId: '1bed736e-711f-4afd-8454-2c8502444af7',
        targetNodeId: '9018d6b6-be6e-420b-9a0d-7226fd789398',
        sourceAnchorId: '1bed736e-711f-4afd-8454-2c8502444af7_right',
        targetAnchorId: '9018d6b6-be6e-420b-9a0d-7226fd789398_left',
      },
      {
        id: '38111bbe-f2ff-428e-acf8-c2f49e45fb08',
        type: 'app-edge',
        endPoint: {
          x: 550,
          y: 1460,
        },
        pointsList: [
          {
            x: 280,
            y: 1460,
          },
          {
            x: 390,
            y: 1460,
          },
          {
            x: 440,
            y: 1460,
          },
          {
            x: 550,
            y: 1460,
          },
        ],
        properties: {},
        startPoint: {
          x: 280,
          y: 1460,
        },
        sourceNodeId: 'affa7bad-1898-4bdb-967b-9e12a72492c6',
        targetNodeId: 'd81adcf1-bfd4-4a1c-b62c-e9ae0eb9488d',
        sourceAnchorId: 'affa7bad-1898-4bdb-967b-9e12a72492c6_right',
        targetAnchorId: 'd81adcf1-bfd4-4a1c-b62c-e9ae0eb9488d_left',
      },
      {
        id: '632ed493-fd99-461b-9510-f4e3d02120d0',
        type: 'app-edge',
        endPoint: {
          x: 1010,
          y: 1460,
        },
        pointsList: [
          {
            x: 870,
            y: 1460,
          },
          {
            x: 980,
            y: 1460,
          },
          {
            x: 900,
            y: 1460,
          },
          {
            x: 1010,
            y: 1460,
          },
        ],
        properties: {},
        startPoint: {
          x: 870,
          y: 1460,
        },
        sourceNodeId: 'd81adcf1-bfd4-4a1c-b62c-e9ae0eb9488d',
        targetNodeId: 'a1d0fa5d-4779-4364-8b54-7eff69bd1ec4',
        sourceAnchorId: 'd81adcf1-bfd4-4a1c-b62c-e9ae0eb9488d_right',
        targetAnchorId: 'a1d0fa5d-4779-4364-8b54-7eff69bd1ec4_left',
      },
      {
        id: '5888e8cc-75fc-4df7-a627-1dc6feedea17',
        type: 'app-edge',
        endPoint: {
          x: 1790,
          y: 1440,
        },
        pointsList: [
          {
            x: 1490,
            y: 720,
          },
          {
            x: 1600,
            y: 720,
          },
          {
            x: 1680,
            y: 1440,
          },
          {
            x: 1790,
            y: 1440,
          },
        ],
        properties: {},
        startPoint: {
          x: 1490,
          y: 720,
        },
        sourceNodeId: '9018d6b6-be6e-420b-9a0d-7226fd789398',
        targetNodeId: 'ade860cd-db62-4538-9943-c8f42c1b927e',
        sourceAnchorId: '9018d6b6-be6e-420b-9a0d-7226fd789398_right',
        targetAnchorId: 'ade860cd-db62-4538-9943-c8f42c1b927e_left',
      },
      {
        id: '3f294d6b-6f4f-4a5c-9d49-f118033eec70',
        type: 'app-edge',
        endPoint: {
          x: 1790,
          y: 1440,
        },
        pointsList: [
          {
            x: 1490,
            y: 1460,
          },
          {
            x: 1600,
            y: 1460,
          },
          {
            x: 1680,
            y: 1440,
          },
          {
            x: 1790,
            y: 1440,
          },
        ],
        properties: {},
        startPoint: {
          x: 1490,
          y: 1460,
        },
        sourceNodeId: 'a1d0fa5d-4779-4364-8b54-7eff69bd1ec4',
        targetNodeId: 'ade860cd-db62-4538-9943-c8f42c1b927e',
        sourceAnchorId: 'a1d0fa5d-4779-4364-8b54-7eff69bd1ec4_right',
        targetAnchorId: 'ade860cd-db62-4538-9943-c8f42c1b927e_left',
      },
      {
        id: 'd04c1570-6572-4505-bf84-f29d81c30e57',
        type: 'app-edge',
        endPoint: {
          x: 1790,
          y: 1440,
        },
        pointsList: [
          {
            x: 1490,
            y: 2190,
          },
          {
            x: 1600,
            y: 2190,
          },
          {
            x: 1680,
            y: 1440,
          },
          {
            x: 1790,
            y: 1440,
          },
        ],
        properties: {},
        startPoint: {
          x: 1490,
          y: 2190,
        },
        sourceNodeId: 'dddebd93-ea1a-4880-8a52-ea8112f7e769',
        targetNodeId: 'ade860cd-db62-4538-9943-c8f42c1b927e',
        sourceAnchorId: 'dddebd93-ea1a-4880-8a52-ea8112f7e769_right',
        targetAnchorId: 'ade860cd-db62-4538-9943-c8f42c1b927e_left',
      },
      {
        id: '536d7d47-9ad8-4144-a6df-35e3e2398327',
        type: 'app-edge',
        endPoint: {
          x: 2430,
          y: 1430,
        },
        pointsList: [
          {
            x: 2110,
            y: 1440,
          },
          {
            x: 2220,
            y: 1440,
          },
          {
            x: 2320,
            y: 1430,
          },
          {
            x: 2430,
            y: 1430,
          },
        ],
        properties: {},
        startPoint: {
          x: 2110,
          y: 1440,
        },
        sourceNodeId: 'ade860cd-db62-4538-9943-c8f42c1b927e',
        targetNodeId: '1c5abed5-e181-41f7-96f5-b5175cc37f3c',
        sourceAnchorId: 'ade860cd-db62-4538-9943-c8f42c1b927e_right',
        targetAnchorId: '1c5abed5-e181-41f7-96f5-b5175cc37f3c_left',
      },
      {
        id: '8b5bb2b5-5baa-4e54-b848-fa87231d9585',
        type: 'app-edge',
        endPoint: {
          x: 1010,
          y: 2190,
        },
        pointsList: [
          {
            x: 870,
            y: 2190,
          },
          {
            x: 980,
            y: 2190,
          },
          {
            x: 900,
            y: 2190,
          },
          {
            x: 1010,
            y: 2190,
          },
        ],
        properties: {},
        startPoint: {
          x: 870,
          y: 2190,
        },
        sourceNodeId: '08503db8-f2e3-4eb3-96f7-957f30a6da6e',
        targetNodeId: 'dddebd93-ea1a-4880-8a52-ea8112f7e769',
        sourceAnchorId: '08503db8-f2e3-4eb3-96f7-957f30a6da6e_right',
        targetAnchorId: 'dddebd93-ea1a-4880-8a52-ea8112f7e769_left',
      },
    ],
    nodes: [
      {
        x: 120,
        y: 115.05849999999998,
        id: 'knowledge-base-node',
        type: 'knowledge-base-node',
        properties: {
          config: {
            fields: [],
            globalFields: [],
          },
          height: 394.383,
          showNode: true,
          stepName: '\u57fa\u672c\u4fe1\u606f',
          node_data: {
            desc: '',
            name: '',
            prologue:
              '\u60a8\u597d\uff0c\u6211\u662f XXX \u5c0f\u52a9\u624b\uff0c\u60a8\u53ef\u4ee5\u5411\u6211\u63d0\u51fa XXX \u4f7f\u7528\u95ee\u9898\u3002\n- XXX \u4e3b\u8981\u529f\u80fd\u6709\u4ec0\u4e48\uff1f\n- XXX \u5982\u4f55\u6536\u8d39\uff1f\n- \u9700\u8981\u8f6c\u4eba\u5de5\u670d\u52a1',
            tts_type: 'BROWSER',
          },
          input_field_list: [],
          user_input_config: {
            title: '\u6587\u6863\u5904\u7406\u8bbe\u7f6e',
          },
          user_input_field_list: [],
        },
      },
      {
        x: 120,
        y: 720,
        id: '768aed24-8139-4689-870f-2065ef05473c',
        type: 'data-source-local-node',
        properties: {
          kind: 'data-source',
          config: {
            fields: [
              {
                label: '\u6587\u4ef6\u5217\u8868',
                value: 'file_list',
              },
            ],
          },
          height: 566,
          showNode: true,
          stepName: '\u6587\u672c\u6587\u4ef6',
          node_data: {
            file_type_list: ['TXT', 'DOCX', 'PDF', 'HTML', 'XLS', 'XLSX', 'CSV'],
            file_size_limit: 100,
            file_count_limit: 50,
          },
          input_field_list: [],
          user_input_config: {},
          user_input_field_list: [],
        },
      },
      {
        x: 710,
        y: 720,
        id: '1bed736e-711f-4afd-8454-2c8502444af7',
        type: 'document-extract-node',
        properties: {
          config: {
            fields: [
              {
                label: '\u6587\u6863\u5185\u5bb9',
                value: 'content',
              },
              {
                label: '\u6587\u6863\u5217\u8868',
                value: 'document_list',
              },
            ],
          },
          height: 394,
          showNode: true,
          stepName: '\u6587\u6863\u5185\u5bb9\u63d0\u53d6',
          condition: 'OR',
          node_data: {
            document_list: ['768aed24-8139-4689-870f-2065ef05473c', 'file_list'],
          },
        },
      },
      {
        x: 1250,
        y: 2190,
        id: 'dddebd93-ea1a-4880-8a52-ea8112f7e769',
        type: 'document-split-node',
        properties: {
          width: 500,
          config: {
            fields: [
              {
                label: '\u5206\u6bb5\u5217\u8868',
                value: 'paragraph_list',
              },
            ],
          },
          height: 652,
          showNode: true,
          stepName: 'Web\u667a\u80fd\u5206\u6bb5',
          condition: 'AND',
          node_data: {
            limit: 4096,
            patterns: [],
            chunk_size: 256,
            limit_type: 'custom',
            with_filter: false,
            document_list: ['08503db8-f2e3-4eb3-96f7-957f30a6da6e', 'document_list'],
            patterns_type: 'custom',
            split_strategy: 'auto',
            chunk_size_type: 'custom',
            limit_reference: [],
            with_filter_type: 'custom',
            patterns_reference: [],
            chunk_size_reference: [],
            with_filter_reference: [],
            document_name_relate_problem: false,
            paragraph_title_relate_problem: true,
            document_name_relate_problem_type: 'custom',
            paragraph_title_relate_problem_type: 'custom',
            document_name_relate_problem_reference: [],
            paragraph_title_relate_problem_reference: [],
          },
        },
      },
      {
        x: 2590,
        y: 1430,
        id: '1c5abed5-e181-41f7-96f5-b5175cc37f3c',
        type: 'knowledge-write-node',
        properties: {
          config: {
            fields: [],
          },
          height: 278,
          showNode: true,
          stepName: '\u77e5\u8bc6\u5e93\u5199\u5165',
          condition: 'AND',
          node_data: {
            document_list: ['ade860cd-db62-4538-9943-c8f42c1b927e', 'Segmented_List'],
          },
        },
      },
      {
        x: 1250,
        y: 720,
        id: '9018d6b6-be6e-420b-9a0d-7226fd789398',
        type: 'document-split-node',
        properties: {
          width: 500,
          config: {
            fields: [
              {
                label: '\u5206\u6bb5\u5217\u8868',
                value: 'paragraph_list',
              },
            ],
          },
          height: 652,
          showNode: true,
          stepName: '\u667a\u80fd\u5206\u6bb5',
          condition: 'AND',
          node_data: {
            limit: 4096,
            patterns: [],
            chunk_size: 256,
            limit_type: 'custom',
            with_filter: false,
            document_list: ['1bed736e-711f-4afd-8454-2c8502444af7', 'document_list'],
            patterns_type: 'custom',
            split_strategy: 'auto',
            chunk_size_type: 'custom',
            limit_reference: [],
            with_filter_type: 'custom',
            patterns_reference: [],
            chunk_size_reference: [],
            with_filter_reference: [],
            document_name_relate_problem: true,
            paragraph_title_relate_problem: true,
            document_name_relate_problem_type: 'custom',
            paragraph_title_relate_problem_type: 'custom',
            document_name_relate_problem_reference: [],
            paragraph_title_relate_problem_reference: [],
          },
        },
      },
      {
        x: 120,
        y: 1460,
        id: 'affa7bad-1898-4bdb-967b-9e12a72492c6',
        type: 'data-source-local-node',
        properties: {
          kind: 'data-source',
          config: {
            fields: [
              {
                label: '\u6587\u4ef6\u5217\u8868',
                value: 'file_list',
              },
            ],
          },
          height: 536,
          showNode: true,
          stepName: 'QA\u95ee\u7b54\u5bf9',
          node_data: {
            file_type_list: ['XLS', 'XLSX', 'CSV', 'ZIP'],
            file_size_limit: 100,
            file_count_limit: 50,
          },
          input_field_list: [],
          user_input_config: {},
          user_input_field_list: [],
        },
      },
      {
        x: 710,
        y: 1460,
        id: 'd81adcf1-bfd4-4a1c-b62c-e9ae0eb9488d',
        type: 'document-extract-node',
        properties: {
          config: {
            fields: [
              {
                label: '\u6587\u6863\u5185\u5bb9',
                value: 'content',
              },
              {
                label: '\u6587\u6863\u5217\u8868',
                value: 'document_list',
              },
            ],
          },
          height: 394,
          showNode: true,
          stepName: '\u6587\u6863\u5185\u5bb9\u63d0\u53d61',
          condition: 'AND',
          node_data: {
            document_list: ['affa7bad-1898-4bdb-967b-9e12a72492c6', 'file_list'],
          },
        },
      },
      {
        x: 1250,
        y: 1460,
        id: 'a1d0fa5d-4779-4364-8b54-7eff69bd1ec4',
        type: 'document-split-node',
        properties: {
          width: 500,
          config: {
            fields: [
              {
                label: '\u5206\u6bb5\u5217\u8868',
                value: 'paragraph_list',
              },
            ],
          },
          height: 580,
          showNode: true,
          stepName: 'QA\u95ee\u7b54\u5bf9\u5206\u6bb5',
          condition: 'AND',
          node_data: {
            limit: 4096,
            patterns: [],
            chunk_size: 256,
            limit_type: 'custom',
            with_filter: false,
            document_list: ['d81adcf1-bfd4-4a1c-b62c-e9ae0eb9488d', 'document_list'],
            patterns_type: 'custom',
            split_strategy: 'qa',
            chunk_size_type: 'custom',
            limit_reference: [],
            with_filter_type: 'custom',
            patterns_reference: [],
            chunk_size_reference: [],
            with_filter_reference: [],
            document_name_relate_problem: true,
            paragraph_title_relate_problem: false,
            document_name_relate_problem_type: 'custom',
            paragraph_title_relate_problem_type: 'custom',
            document_name_relate_problem_reference: [],
            paragraph_title_relate_problem_reference: [],
          },
        },
      },
      {
        x: 1950,
        y: 1440,
        id: 'ade860cd-db62-4538-9943-c8f42c1b927e',
        type: 'variable-aggregation-node',
        properties: {
          config: {
            fields: [
              {
                label: '\u6587\u6863\u5206\u6bb5\u5217\u8868',
                value: 'Segmented_List',
              },
            ],
          },
          height: 570.7660000000001,
          showNode: true,
          stepName: '\u805a\u5408\u6587\u6863\u5206\u6bb5\u5217\u8868',
          condition: 'OR',
          node_data: {
            strategy: 'first_non_null',
            is_result: true,
            group_list: [
              {
                id: 'kU2zR8yRzNIt3RXKHmJtL',
                field: 'Segmented_List',
                label: '\u6587\u6863\u5206\u6bb5\u5217\u8868',
                variable_list: [
                  {
                    v_id: 'N59Lo_VyRKuYASHaKN6g0',
                    variable: ['9018d6b6-be6e-420b-9a0d-7226fd789398', 'paragraph_list'],
                  },
                  {
                    v_id: 'IRQkWPB7THGXlkSBCWmkY',
                    variable: ['a1d0fa5d-4779-4364-8b54-7eff69bd1ec4', 'paragraph_list'],
                  },
                  {
                    v_id: 'jGrIINd-6O6UEzNmZvFap',
                    variable: ['dddebd93-ea1a-4880-8a52-ea8112f7e769', 'paragraph_list'],
                  },
                ],
              },
            ],
          },
        },
      },
      {
        x: 710,
        y: 2190,
        id: '08503db8-f2e3-4eb3-96f7-957f30a6da6e',
        type: 'data-source-web-node',
        properties: {
          kind: 'data-source',
          config: {
            fields: [
              {
                label: '\u6587\u6863\u5217\u8868',
                value: 'document_list',
              },
            ],
          },
          height: 292,
          showNode: true,
          stepName: 'Web\u7ad9\u70b9',
        },
      },
    ],
  },
}
