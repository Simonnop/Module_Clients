"""
提示词和 HTML 模板
"""
from datetime import datetime


# HTML CSS 模板（用于 LLM 提示词）
HTML_CSS_TEMPLATE = """
<style>
    :root {
        --primary: #1e3a8a;
        --secondary: #3b82f6;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg: #f3f4f6;
        --text-main: #111827;
        --text-sub: #4b5563;
        --border: #e5e7eb;
    }
    body { font-family: -apple-system, system-ui, sans-serif; line-height: 1.5; color: var(--text-main); background-color: var(--bg); margin: 0; }
    .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; }
    .header { background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%); color: #ffffff; padding: 25px 20px; }
    .header h1 { margin: 0; font-size: 20px; font-weight: 700; }
    .date-tag { font-size: 12px; opacity: 0.8; margin-top: 5px; display: block; }
    .status-pill { display: inline-flex; align-items: center; background-color: var(--success); padding: 3px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-top: 12px; }
    .content { padding: 15px; }
    .summary-mini { background-color: #f8fafc; border-left: 4px solid var(--secondary); padding: 10px 12px; margin-bottom: 20px; font-size: 13.5px; }
    .section-header { font-size: 15px; font-weight: 700; color: var(--primary); margin: 20px 0 10px 0; display: flex; align-items: center; gap: 6px; }
    .macro-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
    .macro-item { background: #fff; border: 1px solid var(--border); padding: 10px; border-radius: 6px; display: flex; align-items: flex-start; gap: 10px; }
    .macro-label { font-size: 11px; color: var(--primary); font-weight: 700; white-space: nowrap; background: #eff6ff; padding: 2px 5px; border-radius: 3px; }
    .macro-value { font-size: 12.5px; line-height: 1.4; }
    .stock-vertical-list { display: flex; flex-direction: column; gap: 10px; }
    .stock-card { border: 1px solid var(--border); border-left: 4px solid var(--secondary); padding: 12px; border-radius: 6px; background: #fff; }
    .stock-card.card-1 { border-left-color: #3b82f6; }
    .stock-card.card-2 { border-left-color: #f59e0b; }
    .stock-card.card-3 { border-left-color: #10b981; }
    .stock-card.card-4 { border-left-color: #ef4444; }
    .stock-card.card-5 { border-left-color: #8b5cf6; }
    .stock-card.card-6 { border-left-color: #ec4899; }
    .stock-card.card-7 { border-left-color: #06b6d4; }
    .stock-card.card-8 { border-left-color: #f97316; }
    .stock-card.card-9 { border-left-color: #84cc16; }
    .stock-card.card-10 { border-left-color: #6366f1; }
    .stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .stock-name { font-size: 15px; font-weight: 700; color: var(--primary); }
    .stock-code { font-size: 11px; color: var(--text-sub); font-family: monospace; }
    .stock-tag { font-size: 10px; font-weight: 600; color: var(--text-sub); background: #f3f4f6; padding: 1px 5px; border-radius: 3px; }
    .stock-desc { font-size: 12.5px; color: #374151; margin: 6px 0; line-height: 1.5; background: #f9fafb; padding: 8px; border-radius: 4px; }
    .stock-footer { font-size: 10.5px; color: var(--text-sub); display: flex; justify-content: space-between; border-top: 1px solid #f3f4f6; padding-top: 6px; }
    .strategy-box { background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 12px; margin-top: 20px; }
    .strategy-box h4 { margin: 0 0 8px 0; font-size: 14px; color: #92400e; display: flex; align-items: center; gap: 5px; }
    .strategy-box ul { margin: 0; padding-left: 18px; font-size: 12.5px; color: #78350f; }
    .strategy-box li { margin-bottom: 4px; }
    .footer { padding: 20px; background-color: #111827; color: #9ca3af; text-align: center; font-size: 10px; }
    .json-mini { margin-top: 20px; background: #1f2937; padding: 8px; border-radius: 4px; font-size: 10px; color: #60a5fa; word-break: break-all; white-space: pre-wrap; }
</style>
"""


def get_html_output_example(target_date):
    """获取 HTML 输出示例"""
    return f'''
<div class="container">
    <div class="header">
        <h1>市场信息AI分析报告</h1>
        <span class="date-tag">源自 {target_date} 信息</span>
        <div class="status-pill">核心关键词1 · 核心关键词2 · 核心关键词3</div>
    </div>

    <div class="content">
        <div class="summary-mini">
            <strong>核心信息：</strong>用1-2句话概括当日市场核心观点和主要特征，包括指数表现、资金流向、政策环境、市场情绪等关键信息。
        </div>

        <div style="font-size: 11px; color: #b45309; background-color: #fffbeb; padding: 10px; font-weight: 600; line-height: 1.5; text-align: center; ">⚠️ 内容源于PDF识别、语音识别以及大语言模型总结，内容极容易出现错误，强烈建议操作前进行人工研判</div>

        <!-- 一、宏观市场分析 -->
        <div class="section-header">
            <span style="font-size: 18px; margin-right: 8px;">📊</span>
            宏观维度解析
        </div>
        <div class="macro-list">
            <div class="macro-item">
                <span class="macro-label">指数趋势</span>
                <span class="macro-value">详细描述指数表现、技术形态等...</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">资金流向</span>
                <span class="macro-value">详细描述资金流向、ETF动向等...</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">政策环境</span>
                <span class="macro-value">详细描述政策调控、监管措施等...</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">风险警示</span>
                <span class="macro-value">详细描述主要风险点...</span>
            </div>
        </div>

        <!-- 三、个股分析 (核心标的) -->
        <div class="section-header">
            <span style="font-size: 18px; margin-right: 8px;">⚡</span>
            核心关注标的
        </div>
        <div class="stock-vertical-list">
            <!-- 看多股票示例 -->
            <div class="stock-card card-1">
                <div class="stock-header">
                    <div class="stock-name-box"><span class="stock-name">股票名称</span><span class="stock-code">股票代码</span></div>
                    <span class="stock-tag">板块名称</span>
                </div>
                <div class="stock-desc">看多逻辑依据：原文依据和看多/看空逻辑依据的详细说明。</div>
                <div class="stock-footer"><span>看多 (具体逻辑)</span><span>来源：信息来源</span></div>
            </div>
            <div class="stock-card card-2">
                <div class="stock-header">
                    <div class="stock-name-box"><span class="stock-name">股票名称</span><span class="stock-code">股票代码</span></div>
                    <span class="stock-tag">板块名称</span>
                </div>
                <div class="stock-desc">看多逻辑依据：原文依据和看多/看空逻辑依据的详细说明。</div>
                <div class="stock-footer"><span>看多 (具体逻辑)</span><span>来源：信息来源</span></div>
            </div>
            <!-- ETF 示例 -->
            <div class="stock-card card-3">
                <div class="stock-header">
                    <div class="stock-name-box"><span class="stock-name">ETF名称</span><span class="stock-code">ETF代码</span></div>
                    <span class="stock-tag">ETF工具</span>
                </div>
                <div class="stock-desc">推断逻辑：基于逻辑推断的看多/看空依据。</div>
                <div class="stock-footer"><span>看多 (逻辑推断)</span><span>来源：信息来源</span></div>
            </div>
        </div>

        <!-- 四、建议与总结 -->
        <div class="section-header">
            <span style="font-size: 18px; margin-right: 8px;">💡</span>
            实战交易策略总结
        </div>
        <div class="macro-list">
            <div class="macro-item">
                <span class="macro-label">总体策略</span>
                <span class="macro-value">用一句话概括总体策略。</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">具体操作</span>
                <span class="macro-value">可参与的方向和标的。</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">回避方向</span>
                <span class="macro-value">需谨慎回避的方向和标的。</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">交易建议</span>
                <span class="macro-value">交易技巧提示。</span>
            </div>
        </div>

        <!-- 五、数据来源 -->
        <div class="section-header">
            <span style="font-size: 18px; margin-right: 8px;">📚</span>
            数据来源
        </div>
        <div class="macro-list">
            <div class="macro-item">
                <span class="macro-label">B站动态</span>
                <span class="macro-value">信息来源1(http://www.bilibili.com/video/xxxxxxxxxx)、信息来源2(http://www.bilibili.com/video/xxxxxxxxxx)、信息来源3(http://www.bilibili.com/video/xxxxxxxxxx)</span>
            </div>
            <div class="macro-item">
                <span class="macro-label">网盘文件</span>
                <span class="macro-value">信息来源1(+文件名称)、信息来源2(+文件名称)、信息来源3(+文件名称)</span>
            </div>
        </div>

        <!-- 六、JSON -->
        <div class="json-mini">
[
    {{
        "code": "股票代码(SH000001)",
        "name": "股票名称",
        "from": "信息来源",
        "type": "直接提及/逻辑推断",
        "sentiment": "看多/看空/中性",
        "reason": "提及的原文或对应的推断逻辑",
        "sector": "所属板块（如有）"
    }},
    ...
]
        </div>
    </div>

    <div class="footer">
        <p>敬畏市场 远离杠杆 控制回撤 长期复利</p>
        <p>AAA韭菜防割 · 敬上</p>
        <p> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} </p>
    </div>
</div>
'''


def build_llm_prompt(target_date, content_text):
    """构建 LLM 提示词"""
    html_css_template = HTML_CSS_TEMPLATE
    html_output_example = get_html_output_example(target_date)

    question = f"""请基于以下{target_date}的A股市场相关信息进行深度量化分析。

**【硬性约束指令】**

1. **排版要求（非常重要）**：
   - 开头的核心关键词最多四个
   - 必须使用**纵向卡片流**布局。禁止使用 2x2 网格，禁止使用传统的 <table> 表格。
   - 每个宏观维度占一行（macro-item），每个个股/ETF占一个独立卡片（stock-card）,同一个板块的卡片用同一种颜色,不同板块的使用不同的颜色。
   - 必须保持布局紧凑，减少不必要的留白，适合手机竖屏快速滑动阅读。
   - **section-header 必须包含 emoji 图标**：宏观维度解析使用 📊 (图表emoji)，核心关注标的使用 ⚡ (闪电emoji)。不要使用SVG，因为邮件客户端不支持。
   - **stock-header 必须使用 stock-name-box**：使用 `<div class="stock-name-box">` 包裹股票名称和代码，不要使用内联样式。
   - **stock-card 必须使用颜色样式类**：使用 `class=\"stock-card card-1"`、`class=\"stock-card card-2"`、`class=\"stock-card card-3"`、`class=\"stock-card card-4"`、`class=\"stock-card card-5"`、`class=\"stock-card card-6"`、`class=\"stock-card card-7"`、`class=\"stock-card card-8"`、`class=\"stock-card card-9"`、`class=\"stock-card card-10"` 等样式类。**重要：同一个板块的所有股票必须使用相同的颜色样式类**（例如：所有商业航天板块的股票都用 `card-1`，所有半导体板块的股票都用 `card-2`，以此类推）。不同板块使用不同的颜色样式类，以便视觉区分。

2. **内容深度**：
   - **宏观**：必须覆盖指数表现、资金流向、政策调控、主要风险。**重要：区分历史描述和未来判断**。如果材料描述的是{target_date}当天的行情（如"今天涨了""昨日涨停"），这是历史事实，应放在"指数趋势""资金流向"等宏观分析中作为背景。只有对未来（今天及之后）的判断才是操作建议。
   - **微观标的**：
     - **只关注未来操作建议**：材料中提到的股票，必须区分是"已经上涨的描述"还是"未来看好的建议"。只有明确表达未来看好、建议关注、可以买入、值得关注等未来操作意图的标的，才应放入"核心关注标的"部分。
     - **历史描述的处理（极其重要，必须严格区分）**：
       - **核心理解**：材料中的"今天"指的是{target_date}（即昨天），不是未来！
       - **历史描述示例（不是未来建议）**：
         - 描述历史事实："今天涨了""今天涨停了""今天新高了""今天表现强势""今天走强""今天表现不错"等
         - **关键：即使包含操作词汇，如果"今天"指的是{target_date}，也是历史！**例如："今天可以买入""今天可以操作""今天可以关注""今天是一个可以博弈的机会""今天有分歧低吸机会"等，这些**都是描述昨天已经发生的操作建议，不是未来的操作建议！**
       - **未来建议的识别标准（必须同时满足）**：
         1. 明确指向未来时间：如"明天可以关注""后续可以买入""建议关注""看好后续""有望继续""可以参与""建议低吸"等
         2. **不包含"今天"**：如果表述中包含"今天"，且"今天"指的是{target_date}，则不是未来建议
         3. 必须是操作意图：明确表达买入、关注、参与等操作动作
       - **判断流程**：
         1. 首先判断材料中的"今天"是否指的是{target_date}（即昨天）
         2. 如果是，则所有关于"今天"的表述（包括"今天可以操作"）都是历史描述，不是未来建议
         3. 只有明确指向未来（明天、后续、建议关注等）且不包含指向{target_date}的"今天"的表述，才是真正的未来操作建议
       - 如果材料只是描述某只股票的历史表现或昨天的操作建议，但没有表达未来操作建议，则**不应放入核心标的**，可在宏观分析中作为市场现象提及。
     - **未来建议的识别**：
       - **真正的未来建议关键词**："可以关注""值得买入""建议关注""看好后续""有望继续""可以参与""建议低吸""后续""明天"等，且**不包含指向{target_date}的"今天"**
       - **不是未来建议的表述**：
         - 所有包含"今天"且"今天"指的是{target_date}的表述，如"今天涨了""今天表现好""今天可以操作""今天可以买入""今天是一个可以博弈的机会"等
         - 这些都是在描述昨天已经发生的事情或昨天的操作建议，不是未来的操作建议！
     - 直接提及的股票：必须列出原文依据，说明逻辑，并明确标注是"历史描述"还是"未来建议"。
     - 逻辑推断的ETF：基于板块热度推断对应的芯片、科技或行业ETF。
   - **双向分析**：必须搜索是否存在看空/谨慎信息。若无，请在微观部分明确标注"未发现明确看空标的"。

3. **数据准确性（极其重要）**：
   - **股票名称验证（最高优先级）**：原始素材中的股票名称来自语音识别转文字，存在大量同音字错误。必须通过网络搜索验证每个股票名称和代码的准确性。  
   - **验证步骤（必须执行）**：
       1. 根据语音识别的读音，搜索可能的正确股票名称（考虑同音字）
       2. 结合上下文（板块、业务描述、代码等）确认正确的股票名称
       3. 验证股票代码与股票名称是否匹配
       4. 如果无法确定，在股票名称后标注"（待确认）"或"（疑似XX）"，不要随意猜测
       5. 读音不会差距很大, 推断后需要重新确认!!!!!
   - 股票代码必须符合 `SHxxxxxx` 或 `SZxxxxxx` 格式（6位数字）。
   - 必须在每个标的卡片底部标注明确的"信息来源"（如：龙哥第一买点、鉴茶财经等）。

4. **输出格式**：
   - 仅输出 HTML 的 `<div class="container">` 完整内部结构。
   - 不要包含 `<!DOCTYPE>` 或 `<html>` 标签。
   - 在报告末尾包含一个紧凑的 JSON 代码块。

**重要提示：**
- **时间维度区分（极其重要，必须理解）**：
  - **关键理解**：材料中的"今天"指的是{target_date}（即昨天），不是未来！材料描述的是{target_date}当天的行情，这些是**已经发生的历史事实**。
  - **常见历史描述（不是未来建议）**：
    - 描述历史事实：如"今天涨了""今天涨停了""今天表现强势""今天新高了""今天表现不错""今天走强"等
    - **关键：即使包含操作词汇，如果"今天"指的是{target_date}，也是历史！**例如："今天可以买入""今天可以操作""今天可以关注""今天是一个可以博弈的机会""今天有分歧低吸机会""今天的翘板绝对是可以参与到的"等，这些**都是描述昨天已经发生的操作建议，不是未来的操作建议！**
    - 所有这些表述都是在描述{target_date}当天发生的事情或当天的操作建议，**不是对未来的看好**，不应作为今天的操作建议！
  - 报告的目标是生成**今天（{target_date}之后）的操作建议**，因此必须严格区分：
    - **历史描述**：描述过去已经发生的事情（包括材料中说的"今天"），应放在宏观分析中作为市场背景，或在股票卡片中明确标注"（历史表现：{target_date}已上涨X%）"。**如果只有历史描述，没有未来操作建议，则不应放入核心关注标的！**
    - **未来建议**：表达对未来的判断和操作建议，如"可以关注""值得买入""建议低吸""看好后续""有望继续""可以参与""后续可以关注""明天可以关注"等，且**不包含指向{target_date}的"今天"**，这才是核心关注标的的重点。
  - **实战交易策略总结**部分必须全部是**针对今天的操作建议**，不能只是复述昨天的行情。
- 请完整呈现所给出的参考内容, 不要删减（极其重要）
- 区分直接提及和逻辑推断，不要混淆
- 只关注A股（不要港股/海外）
- 所有结论必须有原文依据或明确的推断逻辑
- **股票名称和代码验证是最高优先级**：语音识别错误率很高，必须通过搜索验证每个股票名称和代码的准确性。错误的股票名称会导致报告完全失效！股票代码格式应为：SH/SZ + 6位数字（如：SH600000、SZ000001）

**【样式参考】**
{html_css_template}

**【结构参考】**
{html_output_example}

**【原始素材内容】**
{content_text}
"""
    return question


def get_email_html_template(target_date, html_body):
    """获取邮件 HTML 模板"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{target_date} A股市场分析报告</title>
    <style>
        :root {{
            --primary: #1e3a8a;
            --secondary: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f3f4f6;
            --text-main: #111827;
            --text-sub: #4b5563;
            --border: #e5e7eb;
        }}
        body {{
            font-family: -apple-system, system-ui, "Segoe UI", Roboto, sans-serif;
            line-height: 1.5;
            color: var(--text-main);
            margin: 0;
            padding: 0;
            background-color: var(--bg);
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
        }}
        @media (min-width: 768px) {{
            .container {{
                margin: 20px auto;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
            color: #ffffff;
            padding: 30px 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 700;
        }}
        .date-tag {{
            font-size: 13px;
            opacity: 0.8;
            margin-top: 6px;
            display: block;
        }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            background-color: var(--success);
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 15px;
        }}
        .content {{
            padding: 20px;
        }}
        .summary-mini {{
            background-color: #f8fafc;
            border-left: 4px solid var(--secondary);
            padding: 12px 15px;
            margin-bottom: 24px;
            font-size: 14px;
            line-height: 1.6;
        }}
        .section-header {{
            font-size: 16px;
            font-weight: 700;
            color: var(--primary);
            margin: 24px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .macro-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 24px;
        }}
        .macro-item {{
            background: #fff;
            border: 1px solid var(--border);
            padding: 12px;
            border-radius: 6px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .macro-label {{
            font-size: 11px;
            color: var(--primary);
            font-weight: 700;
            white-space: nowrap;
            background: #eff6ff;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .macro-value {{
            font-size: 13px;
            color: var(--text-main);
            line-height: 1.4;
        }}
        .stock-vertical-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .stock-card {{
            border: 1px solid var(--border);
            border-left: 4px solid var(--secondary);
            padding: 15px;
            border-radius: 6px;
            background: #fff;
        }}
        .stock-card.card-1 {{ border-left-color: #3b82f6; }}
        .stock-card.card-2 {{ border-left-color: #f59e0b; }}
        .stock-card.card-3 {{ border-left-color: #10b981; }}
        .stock-card.card-4 {{ border-left-color: #ef4444; }}
        .stock-card.card-5 {{ border-left-color: #8b5cf6; }}
        .stock-card.card-6 {{ border-left-color: #ec4899; }}
        .stock-card.card-7 {{ border-left-color: #06b6d4; }}
        .stock-card.card-8 {{ border-left-color: #f97316; }}
        .stock-card.card-9 {{ border-left-color: #84cc16; }}
        .stock-card.card-10 {{ border-left-color: #6366f1; }}
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .stock-name-box {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stock-name {{
            font-size: 16px;
            font-weight: 700;
            color: var(--primary);
        }}
        .stock-code {{
            font-size: 12px;
            color: var(--text-sub);
            font-family: monospace;
        }}
        .stock-tag {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-sub);
            background: #f3f4f6;
            padding: 1px 6px;
            border-radius: 3px;
        }}
        .stock-desc {{
            font-size: 13px;
            color: #374151;
            margin: 8px 0;
            line-height: 1.5;
            background: #f9fafb;
            padding: 10px;
            border-radius: 4px;
        }}
        .stock-footer {{
            font-size: 11px;
            color: var(--text-sub);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #f3f4f6;
            padding-top: 8px;
        }}
        .strategy-box {{
            background: #fffbeb;
            border: 1px solid #fef3c7;
            border-radius: 8px;
            padding: 15px;
            margin-top: 30px;
        }}
        .strategy-box h4 {{
            margin: 0 0 10px 0;
            font-size: 15px;
            color: #92400e;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .strategy-box ul {{
            margin: 0;
            padding-left: 20px;
            font-size: 13px;
            color: #78350f;
        }}
        .strategy-box li {{ margin-bottom: 6px; }}
        .footer {{
            padding: 30px 20px;
            background-color: #111827;
            color: #9ca3af;
            text-align: center;
            font-size: 11px;
        }}
        .json-mini {{
            margin-top: 25px;
            background: #1f2937;
            padding: 10px;
            border-radius: 4px;
            font-size: 11px;
            color: #60a5fa;
            white-space: pre-wrap;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""
