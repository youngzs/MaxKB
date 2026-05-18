"""
Build a clean Transitional .docx Jinja template based on the structure of
``盐城安保数据资产 ABS项目调查(模版).docx`` (OOXML Strict, WPS-generated).

The original file is preserved as a reference example; this script outputs
a Transitional-format template the MaxKB finance/template upload endpoint
can parse (python-docx + docxtpl supported), with placeholders for every
field a担保 analyst would fill in per deal.

Placeholder naming follows the suffix→type contract used by the wizard
(see ui/src/views/finance/documents/wizard.vue::displayLabel and
i18n fieldAliases): ``*_amount`` → number, ``*_date`` → date,
``*_summary`` / ``*_desc`` → long_text, others → text.

Run:
    uv run python tools/build_abs_template.py
Output:
    %TEMP%/yancheng-abs-template.docx
"""
from __future__ import annotations

import os
import sys
import tempfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm


# ---- helpers ---------------------------------------------------------


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    """Heading that survives docxtpl rendering with project styling."""
    h = doc.add_heading(text, level=level)
    if level == 0:
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_para(doc: Document, text: str = "", bold: bool = False) -> None:
    p = doc.add_paragraph()
    if text:
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(11)


def add_kv_table(doc: Document, rows: list[tuple[str, str]]) -> None:
    """Two-column key/value table — used for property-list sections."""
    table = doc.add_table(rows=len(rows), cols=2)
    table.style = "Light Grid Accent 1"
    table.autofit = False
    for ri, (k, v) in enumerate(rows):
        cells = table.rows[ri].cells
        cells[0].text = k
        cells[1].text = v
        for c in cells:
            c.width = Cm(8.0)
    doc.add_paragraph()  # spacer after table


def add_finlist_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    """Generic financial / loan-list table with header row."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Light Grid Accent 1"
    table.autofit = True
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for run in hdr[i].paragraphs[0].runs:
            run.bold = True
    for ri, row in enumerate(rows, start=1):
        cells = table.rows[ri].cells
        for ci, val in enumerate(row):
            cells[ci].text = val
    doc.add_paragraph()


# ---- document --------------------------------------------------------


def build() -> Document:
    doc = Document()

    # Page setup roughly mirroring the original (A4, 2.54cm margins is the
    # python-docx default — good enough for a template).

    # === Cover ===
    add_heading(doc, "{{ guarantor_name }}", level=0)
    add_heading(doc, "担保业务调查报告", level=0)
    doc.add_paragraph()

    # Cover summary table — debtor / amount / tenor / fee / product / staff
    cover = doc.add_table(rows=6, cols=2)
    cover.style = "Light Grid Accent 1"
    cover_rows = [
        ("债务人：{{ debtor_name }}", "担保期限：{{ guarantee_tenor }}"),
        ("申请金额：{{ guarantee_amount }} 万元", "担保费率：{{ guarantee_fee_rate }}"),
        (
            "产品类型：{{ product_type }}",
            "原始权益人：{{ original_obligee }}",
        ),
        (
            "反担保措施：单位反担保 {{ counter_guarantor_name }}（{{ counter_guarantor_rating }}）",
            "",
        ),
        ("业务A角：{{ business_owner_a }}", "业务B角：{{ business_owner_b }}"),
        ("项目编号：{{ project_code }}", "报告日期：{{ report_date }}"),
    ]
    for ri, (a, b) in enumerate(cover_rows):
        cover.rows[ri].cells[0].text = a
        cover.rows[ri].cells[1].text = b

    doc.add_page_break()

    # === Title + intro ===
    add_heading(doc, "关于 {{ debtor_name }} 的担保业务调查报告", level=1)
    add_para(doc, "公司领导：")
    add_para(
        doc,
        "根据公司《担保业务基本规程》的要求，现将对 {{ debtor_name }} 的担保业务调查情况，报告如下：",
    )
    add_para(
        doc,
        "{{ business_application_summary }}",
    )

    # === 尽调工作简述 ===
    add_heading(doc, "尽调工作简述", level=2)

    add_heading(doc, "（一）尽调工作人员", level=3)
    add_para(
        doc,
        "尽职调查人 {{ business_owner_a }} 和 {{ business_owner_b }} 于 {{ visit_date }} 到 "
        "{{ debtor_name }} 进行走访、调查，形成了本尽职调查报告。",
    )

    add_heading(doc, "（二）尽调工作方式", level=3)
    add_para(doc, "{{ dd_methodology_desc }}")

    add_heading(doc, "（三）尽调工作过程", level=3)
    add_para(doc, "{{ dd_process_desc }}")

    add_heading(doc, "（四）尽调工作声明", level=3)
    add_para(
        doc,
        "我们严格按照公司的有关制度，把握尽职调查要点，遵循依法合规、审慎诚信的原则，"
        "认真履行尽职调查职责，对本尽职调查报告中所陈述和披露信息的真实性、完整性和"
        "准确性负责。",
    )
    add_para(doc, "项目经理 A：{{ business_owner_a }}")
    add_para(doc, "项目经理 B：{{ business_owner_b }}")
    add_para(doc, "业务部主任：{{ business_director }}")
    add_para(doc, "{{ report_date }}")

    # === 一、项目简介 ===
    add_heading(doc, "一、项目简介", level=1)

    add_heading(doc, "（一）ABS 项目基本信息", level=2)
    abs_info = [
        ("合作券商名称", "{{ partner_broker }}"),
        ("ABS 专项计划管理人名称", "{{ abs_plan_manager }}"),
        ("原始权益人名称", "{{ original_obligee }}"),
        ("ABS 发行总规模（一期）", "{{ abs_total_size_amount }} 万元"),
        ("ABS 发行期限", "{{ abs_tenor }}"),
        ("票面利率", "{{ abs_coupon_rate }}"),
        ("本笔底层资产规模及数量", "{{ guarantee_amount }} 万元 / {{ underlying_asset_count }} 个"),
        ("本笔底层资产涉及债务人数量", "{{ underlying_obligor_count }}"),
        ("担保金额", "{{ guarantee_amount }} 万元"),
        ("担保费率", "{{ guarantee_fee_rate }}（发行成功后分年收取）"),
        ("担保主体", "{{ guarantor_name }}"),
        (
            "反担保措施",
            "{{ debtor_name }} {{ guarantee_amount }} 万元项目："
            "单位反担保：{{ counter_guarantor_name }}（{{ counter_guarantor_rating }}）",
        ),
        ("其他需要说明的情况", "{{ abs_other_notes }}"),
    ]
    add_kv_table(doc, abs_info)

    add_heading(doc, "（二）债务人在我司担保信用记录", level=2)
    add_para(doc, "{{ debtor_credit_history_desc }}")

    add_heading(doc, "（三）ABS 审批进展", level=2)
    add_para(doc, "{{ abs_approval_progress_desc }}")

    add_heading(doc, "（四）产品交易结构", level=2)
    add_para(doc, "本次 {{ abs_product_alias }} 资产支持专项计划交易架构如下：")
    add_heading(doc, "1）项目申报发行阶段", level=3)
    add_para(doc, "{{ abs_issuance_structure_desc }}")
    add_heading(doc, "2）项目代偿追偿阶段", level=3)
    add_para(doc, "{{ abs_recourse_structure_desc }}")

    # === 二、底层资产 ===
    add_heading(doc, "二、底层资产基本情况", level=1)
    add_para(
        doc,
        "本次发行的资产支持专项计划，拟包含底层资产 {{ underlying_asset_count_total }} 笔、"
        "总规模 {{ abs_total_size_amount }} 万元，我司拟担保总额 {{ abs_total_size_amount }} 万元；"
        "其中本笔底层资产规模 {{ guarantee_amount }} 万元，我司拟担保金额 {{ guarantee_amount }} 万元。",
    )
    add_para(doc, "底层资产描述：")
    add_para(doc, "{{ underlying_asset_summary }}")

    # === 三、债务人基本情况 ===
    add_heading(doc, "三、债务人基本情况：{{ debtor_name }}", level=1)

    add_heading(doc, "（一）企业概况", level=2)
    add_para(doc, "{{ debtor_profile_desc }}")

    add_heading(doc, "（二）股权结构", level=2)
    add_finlist_table(
        doc,
        ["股东", "认缴出资（万元）", "出资比例"],
        [
            ["{{ debtor_shareholder }}", "{{ debtor_registered_capital }}", "{{ debtor_shareholder_pct }}"],
        ],
    )

    add_heading(doc, "（三）法定代表人简历", level=2)
    add_para(doc, "法定代表人：{{ debtor_legal_rep }}")
    add_para(doc, "{{ debtor_legal_rep_resume_desc }}")

    add_heading(doc, "（四）企业资信情况", level=2)
    add_para(
        doc,
        "1、据 {{ credit_report_date }} 征信报告查询：{{ debtor_credit_report_summary }}",
    )
    # Loan list table (header + a single example row using placeholders so
    # the analyst can copy-paste rows when editing the actual deal).
    add_finlist_table(
        doc,
        ["序号", "贷款机构", "贷款余额（万元）", "日期", "备注"],
        [
            ["1", "{{ loan_1_lender }}", "{{ loan_1_balance_amount }}", "{{ loan_1_period }}", "{{ loan_1_note }}"],
            ["…", "（按需复制行）", "", "", ""],
            ["", "合计", "{{ debtor_total_loan_balance_amount }}", "", ""],
        ],
    )
    add_para(doc, "2、{{ debtor_history_no_default_desc }}")
    add_para(doc, "3、{{ debtor_litigation_check_desc }}")

    add_heading(doc, "（五）企业经营发展情况", level=2)
    add_para(doc, "{{ debtor_business_summary }}")

    add_heading(doc, "（六）企业财务状况分析", level=2)
    add_para(doc, "企业提供了 {{ debtor_finstmt_period }} 的财务报表。")
    add_para(doc, "{{ debtor_finstmt_summary }}")
    # Standard ratio table — rows kept as placeholders per year column
    add_finlist_table(
        doc,
        ["指标", "{{ debtor_fy_y1 }}", "{{ debtor_fy_y2 }}", "{{ debtor_fy_y3 }}"],
        [
            ["流动比率", "{{ debtor_current_ratio_y1 }}", "{{ debtor_current_ratio_y2 }}", "{{ debtor_current_ratio_y3 }}"],
            ["速动比率", "{{ debtor_quick_ratio_y1 }}", "{{ debtor_quick_ratio_y2 }}", "{{ debtor_quick_ratio_y3 }}"],
            ["资产负债率", "{{ debtor_debt_ratio_y1 }}", "{{ debtor_debt_ratio_y2 }}", "{{ debtor_debt_ratio_y3 }}"],
            ["销售净利率", "{{ debtor_net_margin_y1 }}", "{{ debtor_net_margin_y2 }}", "{{ debtor_net_margin_y3 }}"],
            ["净资产收益率", "{{ debtor_roe_y1 }}", "{{ debtor_roe_y2 }}", "{{ debtor_roe_y3 }}"],
        ],
    )

    # === 四、反担保企业 ===
    add_heading(doc, "四、反担保企业基本情况：{{ counter_guarantor_name }}", level=1)

    add_heading(doc, "（一）企业基本情况", level=2)
    add_para(doc, "{{ counter_guarantor_profile_desc }}")

    add_heading(doc, "（二）法定代表人简介", level=2)
    add_para(doc, "法定代表人：{{ counter_guarantor_legal_rep }}")
    add_para(doc, "{{ counter_guarantor_legal_rep_resume_desc }}")

    add_heading(doc, "（三）股东情况", level=2)
    add_finlist_table(
        doc,
        ["序号", "股东名称", "出资方式", "出资额（万元）", "出资比例"],
        [
            [
                "1",
                "{{ counter_guarantor_shareholder }}",
                "{{ counter_guarantor_contribution_method }}",
                "{{ counter_guarantor_registered_capital }}",
                "{{ counter_guarantor_shareholder_pct }}",
            ],
            ["", "合计", "", "{{ counter_guarantor_registered_capital }}", "100%"],
        ],
    )

    add_heading(doc, "（四）企业信用记录", level=2)
    add_para(doc, "{{ counter_guarantor_credit_record_desc }}")

    add_heading(doc, "（五）企业财务数据", level=2)
    add_para(doc, "{{ counter_guarantor_finstmt_summary }}")

    # === 五、现场尽职调查 ===
    add_heading(doc, "五、现场尽职调查记录", level=1)

    add_heading(doc, "（一）债务人办公地点及生产经营场地情况", level=2)
    add_para(doc, "{{ debtor_site_visit_desc }}")

    add_heading(doc, "（二）债务人现场访谈记录", level=2)
    add_para(doc, "{{ on_site_interview_summary }}")

    # === 六、分类评级 ===
    add_heading(doc, "六、分类评级情况", level=1)
    add_para(
        doc,
        "本次评价业务分类级别：{{ business_classification }}，详见《担保业务分类级别评价表》",
    )

    # === 七、调查意见 ===
    add_heading(doc, "七、调查意见", level=1)
    add_para(doc, "{{ investigation_opinion_desc }}")

    add_para(
        doc,
        "调查人承诺：对以上陈述内容的真实性负责，并且担保申请人与调查人无任何亲属或其他私人利益关系。",
    )
    add_para(doc, "业务经理 A（签名）：{{ business_owner_a }}")
    add_para(doc, "业务经理 B（签名）：{{ business_owner_b }}")
    add_para(doc, "{{ report_date }}")

    return doc


def main() -> int:
    out = os.path.join(tempfile.gettempdir(), "yancheng-abs-template.docx")
    doc = build()
    doc.save(out)
    print(f"Wrote {out}")
    # Quick placeholder count sanity check.
    import re

    with open(out, "rb") as f:
        import zipfile
        import io

        with zipfile.ZipFile(io.BytesIO(f.read())) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    keys = sorted(set(re.findall(r"{{\s*([a-zA-Z0-9_]+)\s*}}", xml)))
    print(f"{len(keys)} unique placeholders:")
    for k in keys:
        print(f"  - {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
