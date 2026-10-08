"""StockLens deterministic evidence engine. All financial arithmetic is Decimal."""
from __future__ import annotations
import json
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).parent / 'data' / 'filings.json'
BASE = json.loads(DATA_PATH.read_text(encoding='utf-8'))
CATEGORIES = ['全部', '经营质量', '财务趋势', '估值', '行情特征', '行业位置', '重要事件', '风险']
EVIDENCE = [
  dict(id='E01', category='经营质量', tag='positive', label='正面事实', title='2026 上半年营业收入同比增长',
       description='营业收入同比正增长，但增幅温和；这里使用营业收入，不混同营业总收入。',
       field_ids=['h26_revenue','h25_revenue'], formula='(2026H1营业收入 / 2025H1营业收入 - 1) × 100%',
       followup='继续核查销量、价格结构与销售渠道变化，不能单凭收入增速断言需求回暖。'),
  dict(id='E02', category='财务趋势', tag='negative', label='负面事实', title='2026 上半年归母净利润同比下降',
       description='同一半年期的归母净利润下降，与收入的小幅增长方向不一致。',
       field_ids=['h26_profit','h25_profit'], formula='(2026H1归母净利润 / 2025H1归母净利润 - 1) × 100%',
       followup='比较成本、销售费用和非经常性损益，解释利润承压。'),
  dict(id='E03', category='经营质量', tag='conflict', label='方向矛盾', title='收入增长，成本增长更快',
       description='营业成本同比增速高于营业收入增速；合并报表营业毛利率出现同比回落。毛利率是按营业收入和营业成本计算，不是酒类业务毛利率。',
       field_ids=['h26_revenue','h25_revenue','h26_cost','h25_cost'], formula='毛利率 = (营业收入 - 营业成本) / 营业收入；同比差 = 本期毛利率 - 上年同期毛利率',
       followup='拆分产品结构、成本单价和渠道组合，判断毛利率回落的驱动因素。'),
  dict(id='E04', category='经营质量', tag='conflict', label='数据需释义', title='经营现金流跃升，但不应直接等同销售回款改善',
       description='公司在半年报中解释：经营现金流净额上升，主要受控股子公司财务公司吸收集团成员单位存款增加及不可随时支取的同业存款减少影响。这是公司披露的原因，不是我们独立验证的因果。',
       field_ids=['h26_cfo','h25_cfo'], formula='(2026H1经营现金流 / 2025H1经营现金流 - 1) × 100%',
       followup='核查现金流量表和财务公司相关科目，避免把金融业务现金流等同酒类销售回款。'),
  dict(id='E05', category='风险', tag='negative', label='待评估风险', title='合同负债期末余额下降',
       description='合同负债较上年末下降。半年报解释与市场化改革、销售模式改变及预收货款政策调整有关；不能简单认定为订单需求下滑。',
       field_ids=['h26_contract','fy25_contract'], formula='(2026-06-30合同负债 / 2025-12-31合同负债 - 1) × 100%',
       followup='跟踪预收款政策、合同负债与终端动销，注意这项比较是期末余额而不是半年同比。'),
  dict(id='E06', category='财务趋势', tag='negative', label='负面事实', title='2025 全年营收和归母净利润同比下滑',
       description='2025 年与 2024 年是完整会计年度间比较，不能直接和 2026 上半年数值做同比。',
       field_ids=['fy25_revenue','fy24_revenue','fy25_profit','fy24_profit'], formula='2025FY / 2024FY - 1（分别对收入、归母净利润计算）',
       followup='在年度口径之外，继续观察 2026 同期数据是否显示趋势改善。'),
  dict(id='E07', category='财务趋势', tag='negative', label='负面事实', title='2025 全年经营现金流同比下降',
       description='经营现金流净额在两个完整年度之间下降，需结合财务公司业务核查质量。',
       field_ids=['fy25_cfo','fy24_cfo'], formula='(2025FY经营现金流 / 2024FY经营现金流 - 1) × 100%',
       followup='进一步区分酒类经营现金回款与财务公司资金往来。'),
  dict(id='E08', category='估值', tag='unknown', label='证据缺口', title='未接入可验证的同日股价，不输出真实 PE',
       description='报告提供 2025 年基本每股收益，但没有已核验、同一时点的市价。可以使用手动情景股价演算静态 PE；情景输入并非实际行情。',
       field_ids=['fy25_eps'], formula='情景静态 PE = 用户输入的情景股价 / 2025 年基本每股收益',
       followup='接入有日期、复权口径与来源的收盘价后，才可做真实估值比较；2025 静态 PE 不等于滚动 PE。'),
  dict(id='E09', category='行情特征', tag='unknown', label='证据缺口', title='未提供可核对的 K 线、波动率与市场价格',
       description='本版不伪造近 20 日涨跌幅、振幅、均线信号与交易活跃度；这些指标需要带交易日和复权口径的行情数据。',
       field_ids=[], formula='需要真实交易日价格序列及数据供应商元信息',
       followup='接入扶摇行情 API 后计算近 20/60 交易日的收益率与波动率，并公开复权口径。'),
  dict(id='E10', category='行业位置', tag='unknown', label='证据缺口', title='已确认白酒主营业务，未验证同行分位排名',
       description='半年报披露公司主要从事茅台酒及系列酒的生产销售。关于行业处在结构性调整阶段的说法属于公司管理层陈述。缺少同一报告期、同口径同行样本，不给出行业第几或分位数。',
       field_ids=[], formula='同行相对比较需：样本股票、报告期、同口径财务字段',
       followup='补齐公开同行年报或行业成分及财务数据后，再计算行业比较。'),
  dict(id='E11', category='重要事件', tag='source_view', label='公司公告', title='2026 年 7 月指定飞天茅台零售价及合同价调整',
       description='公告明确某指定商品的 i 茅台平台零售价及销售合同价均上调 100 元/瓶。为商品定价调整，绝非证券交易价格；公告只提示会影响业绩，未给出可验证的收益幅度。',
       field_ids=['event_retail_old','event_retail_new','event_contract_old','event_contract_new'], formula='1639 - 1539 = 100 元/瓶；1369 - 1269 = 100 元/瓶',
       followup='后续核验销量、销量结构和定价执行情况，再评价对营收利润的影响。'),
  dict(id='E12', category='风险', tag='source_view', label='管理层陈述', title='公司认为白酒行业面临周期性与结构性调整',
       description='“存量竞争”和结构性调整来自公司 2026 年半年报的管理层讨论，不是独立的行业指数定量验证。',
       field_ids=[], formula='文本型证据：2026 半年度报告第 6 页“主营业务情况说明”',
       followup='用行业总需求与同行财务、渠道库存数据交叉验证管理层判断。'),
  dict(id='E14', category='重要事件', tag='source_view', label='半年报披露', title='2026 上半年完成股份回购并注销',
       description='2026 年半年报披露：截至资产负债表日，已累计回购 2,188,614 股，已支付总金额 2,999,933,749.57 元（不含交易费用），并已办理完成注销。该事项反映已实施的资本动作，不自动推导未来股价表现。',
       field_ids=['buyback_shares','buyback_amount'], formula='回购股数与金额均为公司报告原文披露；不使用回购均价推导交易建议。',
       followup='核对股份变动明细、回购时间段与后续资本安排，区分已完成事项和未来计划。'),
  dict(id='E13', category='风险', tag='unknown', label='结论边界', title='尚未形成足以做买卖判断的完整证据链',
       description='估值、行情、同行比较及终端渠道等重要证据缺失；不输出投资评级、价格目标或确定性预测。',
       field_ids=[], formula='缺失项：可核验市场价、价格序列、同行统一口径、终端渠道样本',
       followup='补充上述数据并交叉验证，再更新研究结论。')
]

EXTRA_SOURCES = {
   'E04': [{'source':'H26','page':'第 5 页 / 第 7–8 页','summary':'经营现金流净额增长主要是财务公司吸收集团成员单位存款增加，及不可随时支取的同业存款减少。'}],
   'E05': [{'source':'H26','page':'第 9 页','summary':'主要是公司进行市场化改革，销售模式改变，预收货款政策相应调整。'}],
   'E10': [{'source':'H26','page':'第 6 页','summary':'公司主要业务是茅台酒及系列酒的生产与销售。'}],
   'E12': [{'source':'H26','page':'第 6 页','summary':'白酒行业正在经历周期性与结构性调整，这是公司管理层的行业判断。'}]
}


def d(raw: str | float | int) -> Decimal:
    return Decimal(str(raw))


def quant(x: Decimal, precision: str='0.01') -> Decimal:
    return x.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


def format_num(x: Decimal, digits: int=2) -> str:
    return f'{quant(x, "0." + "0" * digits):,.{digits}f}'


def scenario_data(mode: str) -> dict[str, Any]:
    if mode not in ('normal', 'missing', 'conflict', 'stale', 'offline'):
        raise ValueError('不支持的演示情景')
    fields = {key: {**value, 'status':'ok'} for key,value in BASE['fields'].items()}
    if mode == 'missing':
        fields['h26_cfo']['status'] = 'missing'
    elif mode == 'conflict':
        fields['h26_revenue']['status'] = 'conflict'
        fields['h26_revenue']['conflict_note'] = '模拟第二数据渠道给出不同数值；未获得另一可核验原文，停止采用该项数值。'
    elif mode == 'stale':
        for k,v in fields.items():
            if v['source'] == 'H26':
                v['status'] = 'stale'
    elif mode == 'offline':
        for k,v in fields.items():
            if v['source'] == 'H26':
                v['status'] = 'offline'
    return fields


def safe_metric(fields: dict, current: str, old: str, kind: str='yoy') -> dict[str,Any]:
    a,b = fields[current], fields[old]
    invalid = [(k, v['status']) for k,v in ((current,a),(old,b)) if v['status'] != 'ok']
    if invalid:
        return {'available':False,'status':invalid[0][1], 'reason': '相关原始字段不可用：' + '、'.join(k+'('+status+')' for k,status in invalid), 'field_ids':[current,old]}
    aa,bb = d(a['raw']),d(b['raw'])
    if bb == 0:
        return {'available':False,'status':'invalid','reason':'对照期分母为 0，不能计算增幅','field_ids':[current,old]}
    pct = (aa/bb-1)*100
    return {'available':True,'value':format_num(aa/Decimal('100000000')) if a['unit']=='元' else format_num(aa),
            'value_raw':str(aa),'unit':'亿元' if a['unit']=='元' else a['unit'],
            'compare_value':format_num(bb/Decimal('100000000')) if b['unit']=='元' else format_num(bb),
            'change':format_num(pct), 'change_signed': ('+' if pct>0 else '')+format_num(pct)+'%',
            'change_raw':str(pct), 'field_ids':[current,old], 'comparison_kind':kind,
            'delta_direction':'up' if pct>0 else ('down' if pct<0 else 'flat')}


def calc_gross_margin(fields: dict) -> dict:
    ks = ['h26_revenue','h26_cost','h25_revenue','h25_cost']
    for k in ks:
        if fields[k]['status'] != 'ok':
            return {'available':False, 'status':fields[k]['status'],'reason':'毛利率计算所需字段存在缺失、冲突、过期或接口错误', 'field_ids':ks}
    r,c,pr,pc = (d(fields[k]['raw']) for k in ks)
    if r <=0 or pr<=0:
        return {'available':False, 'status':'invalid','reason':'营业收入非正，无法计算毛利率','field_ids':ks}
    curr = (r-c)/r*100
    prev = (pr-pc)/pr*100
    delta = curr-prev
    return {'available':True,'value':format_num(curr), 'unit':'%', 'compare_value':format_num(prev),
            'change_signed':('+' if delta>0 else '')+format_num(delta)+'pp',
            'change':format_num(delta),'change_raw':str(delta), 'field_ids':ks, 'delta_direction':'up' if delta>0 else 'down',
            'comparison_kind':'2026H1 对比 2025H1，同口径毛利率差（百分点）'}


def safe_percentage_point_metric(fields: dict, current: str, old: str) -> dict[str,Any]:
    """Percent-type ratios such as ROE must be compared in percentage points, not YoY %."""
    a,b = fields[current],fields[old]
    invalid = [(k, v['status']) for k,v in ((current,a),(old,b)) if v['status']!='ok']
    if invalid:
        return {'available':False,'status':invalid[0][1],
                'reason':'相关原始字段不可用：'+ '、'.join(k+'('+status+')' for k,status in invalid),
                'field_ids':[current,old]}
    aa,bb=d(a['raw']),d(b['raw'])
    delta=aa-bb
    return {'available':True,'value':format_num(aa),'unit':'%',
            'compare_value':format_num(bb),'change':format_num(delta),
            'change_signed':('+' if delta>0 else '')+format_num(delta)+'pp',
            'change_raw':str(delta),'field_ids':[current,old],
            'delta_direction':'up' if delta>0 else ('down' if delta<0 else 'flat'),
            'comparison_kind':'同口径比率的百分点变化，不是相对增长率'}


def scenario_pe(price: Any) -> dict:
    if price is None or str(price).strip() == '':
        return {'available':False,'reason':'请输入假设每股价格；不代表实时或历史证券行情'}
    try:
        p=d(price)
        if not p.is_finite() or p<=0 or p > Decimal('1000000'):
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        return {'available':False,'reason':'请输入大于 0 且不超过 1,000,000 的有限价格（元/股）'}
    eps=d(BASE['fields']['fy25_eps']['raw'])
    return {'available':True,'value':format_num(p/eps),'unit':'倍','price':format_num(p),
            'eps':str(eps),'formula':'情景静态 PE = 假设股价 / 2025 年报告基本每股收益',
            'notice':'手动假设输入，不是行情！使用 2025FY 静态 EPS，不是滚动市盈率或估值结论。',
            'field_ids':['fy25_eps']}


def build_diagnosis(mode: str='normal') -> dict[str,Any]:
    fields=scenario_data(mode)
    metrics={
       'revenue':safe_metric(fields,'h26_revenue','h25_revenue'),
       'profit':safe_metric(fields,'h26_profit','h25_profit'),
       'cashflow':safe_metric(fields,'h26_cfo','h25_cfo'),
       'cost':safe_metric(fields,'h26_cost','h25_cost'),
       'margin':calc_gross_margin(fields),
       'contract':safe_metric(fields,'h26_contract','fy25_contract', kind='2026H1 期末比 2025 年末余额变化，非同比'),
       'fy_revenue':safe_metric(fields,'fy25_revenue','fy24_revenue'),
       'fy_profit':safe_metric(fields,'fy25_profit','fy24_profit'),
       'fy_cashflow':safe_metric(fields,'fy25_cfo','fy24_cfo'),
       'roe':safe_percentage_point_metric(fields,'h26_roe','h25_roe'),
    }
    cards=[]
    # Some statements depend on source text but no numerical field (E10/E12).
    # They must be downgraded too when their sole underlying disclosure is unavailable.
    broken_sources={src for src in BASE['sources'] if any(
        f['source']==src for f in fields.values()) and all(
        f['status'] in ('stale','offline') for f in fields.values() if f['source']==src)}
    for item in EVIDENCE:
        row = dict(item)
        row['sources'] = sorted(set(fields[k]['source'] for k in item['field_ids']) | set(e['source'] for e in EXTRA_SOURCES.get(item['id'],[])))
        row['extra_sources'] = EXTRA_SOURCES.get(item['id'],[])
        row['evidence_type'] = ('research_gap' if item['tag']=='unknown' else 'management_statement' if item['id']=='E12' else 'company_disclosure' if item['tag']=='source_view' else 'calculated_observation')
        blockers=[k for k in item['field_ids'] if fields[k]['status']!='ok']
        text_source_deps={e['source'] for e in EXTRA_SOURCES.get(item['id'],[])}
        text_source_blockers=sorted(text_source_deps & broken_sources)
        row['blocked_sources']=text_source_blockers
        row['available']=not blockers and not text_source_blockers
        row['blocked_by']=blockers
        if blockers or text_source_blockers:
            row['data_warning']='对应原始字段或引用来源在当前情景中不可用；暂停将此条作为有效结论。可打开历史公告复核。'
        cards.append(row)
    if mode != 'normal':
        warnings={
            'missing':'异常模拟：2026H1 经营现金流字段缺失，相关结论已降级；其他字段保留。',
            'conflict':'异常模拟：2026H1 营业收入发生来源冲突，依赖此值的指标均停止计算。',
            'stale':'异常模拟：2026 半年报源被标记为过期，所有该源字段不再用于确定性判断。',
            'offline':'异常模拟：2026 半年报数据接口不可用，保留独立来源的全年数据并显示失败。',
        }
        banner=warnings[mode]
    else:
        banner='截至 2026-08-15 已披露文件的静态研究快照。无实时行情，2026 半年报未经审计。'
    return {'company':BASE['company'], 'sources':BASE['sources'], 'fields':fields,
            'metrics':metrics, 'evidence':cards, 'categories':CATEGORIES, 'mode':mode,
            'banner':banner, 'counts':{k:sum(1 for x in cards if x['tag']==k and x['available']) for k in ['positive','negative','conflict','unknown','source_view']},
            'notice':'信息研究工具，仅做数据与证据呈现；不构成投资建议。公司观点不等于独立事实。'}


QUERY_LENSES = [
    ('估值', ['E08','E13'], ('估值','市盈','pe','便宜','贵','多少倍')),
    ('行情', ['E09','E13'], ('行情','股价','涨跌','走势','波动','k线','均线')),
    ('事件', ['E11','E14','E12'], ('公告','新闻','事件','涨价','调价','回购','注销','商品价格')),
    ('现金流', ['E04','E07','E05'], ('现金','回款','流动性','收钱')),
    ('盈利', ['E01','E02','E03','E06'], ('利润','毛利','成本','盈利','赚钱','费用')),
    ('风险', ['E05','E12','E13','E03'], ('风险','合同负债','预收','订单','隐患')),
    ('行业', ['E10','E12','E13'], ('同行','行业','竞争','五粮液','排名','市场地位')),
    ('收入', ['E01','E02','E03','E06'], ('收入','营收','销售额','业绩增长')),
    ('财务', ['E01','E02','E03','E04','E13'], ('财务','经营','整体','诊断','基本面','综合')),
]


def select_evidence_ids(query: str, limit: int=6) -> tuple[str,list[str]]:
    """Multi-intent routing that never invents an evidence record.
    Rule route is a fallback, NOT a claim of semantic LLM understanding.
    """
    q=query.casefold()
    matching=[]
    for name, ids, patterns in QUERY_LENSES:
        if name=='事件':
            if any(x in q for x in ('回购','注销')) and not any(x in q for x in ('调价','涨价','酒价')):
                ids=['E14','E13']
            elif any(x in q for x in ('调价','涨价','酒价','商品价格')) and not any(x in q for x in ('回购','注销')):
                ids=['E11','E13']
        hits=sum(len(word) for word in patterns if word.casefold() in q)
        if hits:
            matching.append((hits,name,ids))
    if not matching:
        return '综合诊断',['E01','E02','E03','E04','E13']
    matching.sort(key=lambda x:-x[0])  # ties keep curation order
    chosen=[]
    for _,_,ids in matching:
        for i in ids:
            if i not in chosen:
                chosen.append(i)
            if len(chosen)>=limit:
                break
        if len(chosen)>=limit:
            break
    # Always include contrasts for revenue / profitability questions.
    if ('利润' in q or '盈利' in q or '营收' in q or '收入' in q) and 'E02' in chosen and 'E01' not in chosen:
        if len(chosen)>=limit: chosen[-1]='E01'
        else: chosen.append('E01')
    return ' / '.join(r[1] for r in matching[:2]),list(dict.fromkeys(chosen))[:limit]


def route_query(query: str, mode='normal', chosen_ids=None) -> dict:
    """Grounded structured answer: fact / interpretation / missing / next-step are separate.

    LLM only supplies candidate IDs. It cannot supply the numbers or assertions.
    """
    q=(query or '').strip()
    if not q or len(q)>500:
        raise ValueError('问题不能为空且不得超过 500 字')
    data=build_diagnosis(mode)
    valid=set(x['id'] for x in data['evidence'])
    if chosen_ids is None:
        lens,ids=select_evidence_ids(q)
    else:
        lens='大模型辅助定位'
        ids=list(dict.fromkeys(x for x in chosen_ids if isinstance(x,str) and x in valid))[:6]
        if not ids:
            lens,ids=select_evidence_ids(q)
    picked=[x for x in data['evidence'] if x['id'] in ids]
    picked.sort(key=lambda x:ids.index(x['id']))
    ready={x['id']:x for x in picked if x['available']}
    blocked=[x for x in picked if not x['available']]
    metrics=data['metrics']
    def val(key):
        m=metrics[key]
        return m['change_signed'] if m['available'] else None
    fact=[]
    inference=[]
    unknown=[]
    next_steps=[]
    def add(target, txt, *eids):
        if all(id in ready for id in eids):
            target.append({'text':txt,'evidence_ids':list(eids)})
    add(fact,f"2026H1 营业收入同比 {val('revenue')}。",'E01') if val('revenue') else None
    add(fact,f"2026H1 归母净利润同比 {val('profit')}。",'E02') if val('profit') else None
    if 'E01' in ready and 'E02' in ready and val('revenue') and val('profit'):
        add(inference,'收入与归母净利润增速方向不一致，存在需要拆解的盈利质量问题；不能仅凭两项指标确定原因。','E01','E02')
    if val('cost') and val('margin'):
        add(fact,f"营业成本同比 {val('cost')}，合并口径毛利率变化 {val('margin')}。",'E03')
        add(inference,'毛利率回落与收入、成本变化相符；价格、产品结构和费用仍需进一步核查，不能单凭毛利率变化确认因果。','E03')
    if val('cashflow'):
        add(fact,f"合并经营现金流净额同比 {val('cashflow')}。",'E04')
        add(inference,'公司公告解释了财务公司资金变动因素，不能据此断言酒类终端销售回款大幅增长。','E04')
    if val('contract'):
        add(fact,f"合同负债较 2025 年末 {val('contract')}（期末余额比较，不是半年同比）。",'E05')
        add(inference,'公司披露与销售模式及预收货款政策调整有关，不能直接把余额下降等同需求下降。','E05')
    if val('fy_revenue') and val('fy_profit'):
        add(fact,f"2025FY 收入同比 {val('fy_revenue')}，归母净利润同比 {val('fy_profit')}（全年口径）。",'E06')
    if val('fy_cashflow'):
        add(fact,f"2025FY 合并经营现金流净额同比 {val('fy_cashflow')}。",'E07')
    if 'E08' in ready:
        unknown.append({'text':'未接入已核验的同日市场股价，真实静态 PE 与估值高低无法判定；手动情景价并非行情。','evidence_ids':['E08']})
    if 'E09' in ready:
        unknown.append({'text':'无带交易日和复权口径的历史行情，无法验证近期波动率与走势。','evidence_ids':['E09']})
    if 'E10' in ready:
        add(fact,'公司披露主营茅台酒及系列酒生产销售。','E10')
        unknown.append({'text':'尚缺统一报告期的同行样本，不能给出行业排名或分位数。','evidence_ids':['E10']})
    if 'E11' in ready:
        add(fact,'公司公告：指定酒品零售价和销售合同价均上调 100 元/瓶，属于商品定价变化而非股票价格。','E11')
        unknown.append({'text':'商品调价对最终销量、业绩的量化影响尚未经过本项目独立验证。','evidence_ids':['E11']})
    if 'E12' in ready:
        add(inference,'白酒行业周期性和结构性调整是管理层报告中的行业判断，缺少独立的同口径行业核验。','E12')
    if 'E14' in ready:
        add(fact,'半年报披露：截至 2026-06-30，公司累计回购并注销 2,188,614 股，支付 2,999,933,749.57 元（不含交易费用）。','E14')
        unknown.append({'text':'回购事实不能证明未来股价上涨，也不代表新的回购计划。','evidence_ids':['E14']})
    if 'E13' in ready:
        unknown.append({'text':'市场价格、同行样本与终端渠道等仍有研究缺口，不能形成交易结论。','evidence_ids':['E13']})
    for e in ready.values():
        if e['followup'] not in next_steps:
            next_steps.append(e['followup'])
    for e in blocked:
        unknown.append({'text':f"{e['id']}「{e['title']}」被暂停：{e['data_warning']}", 'evidence_ids':[e['id']]})
    if not fact and not inference and not unknown:
        unknown=[{'text':'当前问题缺少可用的证据，不提供确定性结论。','evidence_ids':[]}]
    # One terse natural language summary, with the structured evidence visible alongside it.
    summary=' '.join(x['text'] for x in fact[:3]+inference[:1]+unknown[:1])
    if blocked:
        summary+=f' 另有 {len(blocked)} 条证据因异常被暂停，未用于推断。'
    return {'question':q, 'lens':lens,
            'mode':'规则路由（离线）' if chosen_ids is None else 'LLM 辅助证据定位（数值仍由确定性计算引擎生成）',
            'reply':summary,'analysis':{'facts':fact,'inferences':inference,'unknowns':unknown,'next_steps':next_steps[:4]},
            'suspended_ids':[x['id'] for x in blocked],
            'evidence_ids':ids,'evidence':picked,'is_investment_advice':False,
            'data_cutoff':data['company']['data_cutoff']}
