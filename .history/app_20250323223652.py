import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import akshare as ak
import os
import time
import numpy as np
from datetime import datetime
import glob
import re
import traceback

# 设置matplotlib支持中文
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 定义数据目录
data_dir = "financial_data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# 定义下载目录
download_dir = "financial_reports"
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

# 定义图表目录
chart_dir = "financial_charts"
if not os.path.exists(chart_dir):
    os.makedirs(chart_dir)

# 获取当前日期作为文件名一部分
current_date = datetime.now().strftime("%Y%m%d")

def get_stock_prefix(code):
    """根据股票代码判断其所属交易所"""
    code = str(code)
    if code.startswith(('0', '3')):
        return "sz"  # 深交所
    elif code.startswith(('6', '9')):
        return "sh"  # 上交所
    elif code.startswith('83'):
        return "bj"  # 北交所/新三板精选层
    elif code.startswith('4'):
        return "bj"  # 北交所
    elif code.startswith('8'):
        return "bj"  # 新三板
    elif code.startswith('5'):
        return "sh"  # 上交所基金
    elif code.startswith('1'):
        return "sz"  # 深交所基金
    else:
        return "sz"  # 默认使用深交所

def download_financial_reports(stock_code):
    """下载股票财务报表"""
    # 显示下载进度
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 获取股票前缀
        prefix = get_stock_prefix(stock_code)
        full_code = prefix + stock_code
        
        try:
            # 获取股票名称
            status_text.text("正在获取股票信息...")
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            stock_name = stock_info.loc[0, "股票简称"] if not stock_info.empty else "未知"
        except Exception as e:
            st.warning(f"无法获取股票名称: {e}")
            stock_name = "未知"
        
        progress_bar.progress(10)
        status_text.text(f"开始下载 {stock_code}({stock_name}) 的财务报表...")
        
        # 定义要下载的报表类型
        report_types = ["资产负债表", "利润表", "现金流量表"]
        
        successful_downloads = 0
        report_data = {}
        
        for i, report_type in enumerate(report_types):
            try:
                status_text.text(f"正在下载 {stock_name}({stock_code}) 的{report_type}...")
                df = ak.stock_financial_report_sina(stock=full_code, symbol=report_type)
                
                # 检查数据是否为空
                if df is None or df.empty:
                    st.warning(f"警告: {report_type}没有数据")
                    continue
                    
                # 根据报表类型生成不同的文件名
                file_type = ""
                if report_type == "资产负债表":
                    file_type = "balance_sheet"
                elif report_type == "利润表":
                    file_type = "income_statement"
                elif report_type == "现金流量表":
                    file_type = "cash_flow"
                
                file_path = os.path.join(data_dir, f"{stock_code}_{file_type}_{current_date}.csv")
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                
                # 存储报表数据以供后续分析
                report_data[report_type] = df
                
                successful_downloads += 1
                
                # 更新进度条
                progress_bar.progress(10 + (i + 1) * 30)
                    
            except Exception as e:
                st.error(f"下载{report_type}时出错: {e}")
        
        if successful_downloads > 0:
            status_text.text("下载完成！")
            progress_bar.progress(100)
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            st.success(f"成功下载了 {stock_code}({stock_name}) 的 {successful_downloads} 个财务报表")
            return report_data, stock_name
        else:
            status_text.empty()
            progress_bar.empty()
            st.error("未能成功下载任何财务报表，请检查股票代码是否正确或稍后再试")
            return None, stock_name

    except Exception as e:
        status_text.empty()
        progress_bar.empty()
        st.error(f"程序执行出错: {e}")
        return None, "未知"

def load_existing_reports(stock_code):
    """加载已存在的财务报表数据"""
    reports_dir = f"reports/{stock_code}"
    
    # 检查目录是否存在
    if not os.path.exists(reports_dir):
        return None, None
    
    # 读取资产负债表
    bs_file = f"{reports_dir}/balance_sheet.csv"
    if os.path.exists(bs_file):
        try:
            balance_sheet = pd.read_csv(bs_file, index_col=0)
            # 确保列名都是字符串类型
            balance_sheet.columns = balance_sheet.columns.astype(str)
        except Exception as e:
            st.error(f"加载资产负债表时出错: {e}")
            balance_sheet = None
    else:
        balance_sheet = None
    
    # 读取利润表
    is_file = f"{reports_dir}/income_statement.csv"
    if os.path.exists(is_file):
        try:
            income_statement = pd.read_csv(is_file, index_col=0)
            # 确保列名都是字符串类型
            income_statement.columns = income_statement.columns.astype(str)
        except Exception as e:
            st.error(f"加载利润表时出错: {e}")
            income_statement = None
    else:
        income_statement = None
    
    # 转置表格并重置索引
    if balance_sheet is not None:
        bs_items = balance_sheet.index.tolist()
        balance_sheet = balance_sheet.transpose().reset_index()
        balance_sheet.rename(columns={'index': '日期'}, inplace=True)
    
    if income_statement is not None:
        is_items = income_statement.index.tolist()
        income_statement = income_statement.transpose().reset_index()
        income_statement.rename(columns={'index': '日期'}, inplace=True)
    
    return balance_sheet, income_statement

def get_financial_metrics(income_statement, stock_code):
    """提取营业收入和净利润数据"""
    if income_statement is None or income_statement.empty:
        return None, None, None
    
    # 确保列名都是字符串类型
    income_statement.columns = income_statement.columns.astype(str)
    
    # 确保第一列是字符串类型
    first_col = income_statement.columns[0]
    income_statement[first_col] = income_statement[first_col].astype(str)
    
    # 尝试识别包含项目名称的列
    project_col = None
    project_col_candidates = ['项目', '报表项目', '科目', '会计科目', '项目名称']
    
    # 查找第一列是否包含项目列名称
    for candidate in project_col_candidates:
        if candidate in income_statement.columns:
            project_col = candidate
            break
    
    # 如果没有找到明确的项目列，检查第一列是否包含常见的财务项目
    if project_col is None:
        first_col = income_statement.columns[0]
        # 检查第一列的值是否包含常见的财务术语
        for term in ['营业收入', '营业总收入', '营业利润', '净利润', '利润总额']:
            if income_statement[first_col].str.contains(term).any():
                project_col = first_col
                break
    
    # 如果仍然没有找到项目列，检查是否需要转置数据
    if project_col is None:
        # 检查第一行是否包含日期信息
        first_row = income_statement.iloc[0]
        date_pattern = re.compile(r'20\d{2}[-/年]\d{1,2}[-/月]?')
        has_dates = any(isinstance(val, str) and date_pattern.search(val) for val in first_row)
        
        if has_dates:
            # 数据需要转置，第一行可能是日期
            income_statement = income_statement.T
            # 使用第一行作为列名
            income_statement.columns = income_statement.iloc[0]
            # 删除第一行（现在已成为列名）
            income_statement = income_statement.iloc[1:].reset_index()
            # 重命名index列为日期
            income_statement.rename(columns={'index': '日期'}, inplace=True)
            project_col = '日期'  # 项目列现在变成了'日期'列
    
    # 如果还是没有找到，使用第一列作为项目列
    if project_col is None:
        project_col = income_statement.columns[0]
    
    # 查找营业收入行
    revenue_row = None
    revenue_patterns = ['营业收入', '营业总收入', '主营业务收入', '主营收入', '总收入']
    for pattern in revenue_patterns:
        matching_rows = income_statement[income_statement[project_col].str.contains(pattern, na=False)]
        if not matching_rows.empty:
            revenue_row = matching_rows.iloc[0]
            break
    
    # 查找净利润行
    profit_row = None
    profit_patterns = ['净利润', '归属于母公司所有者的净利润', '归母净利润', '归属于母公司股东的净利润']
    for pattern in profit_patterns:
        matching_rows = income_statement[income_statement[project_col].str.contains(pattern, na=False)]
        if not matching_rows.empty:
            profit_row = matching_rows.iloc[0]
            break
    
    # 如果没有找到营业收入或净利润，返回None
    if revenue_row is None or profit_row is None:
        return None, None, None
    
    # 创建一个新的DataFrame存储财务指标
    financial_metrics = pd.DataFrame()
    
    # 如果是日期在列名中，需要将数据重组
    if '日期' in income_statement.columns:
        financial_metrics['日期'] = income_statement['日期']
        financial_metrics['营业收入'] = revenue_row
        financial_metrics['净利润'] = profit_row
    else:
        # 日期在行中，需要提取除了项目列之外的所有列
        date_cols = [col for col in income_statement.columns if col != project_col]
        
        # 创建日期、营业收入和净利润列表
        dates = []
        revenue_values = []
        profit_values = []
        
        for col in date_cols:
            # 尝试将收入和利润转换为数值
            try:
                revenue_value = pd.to_numeric(revenue_row[col], errors='coerce')
                profit_value = pd.to_numeric(profit_row[col], errors='coerce')
                
                # 只有当收入和利润都为有效数值时才添加
                if pd.notna(revenue_value) and pd.notna(profit_value):
                    dates.append(col)
                    revenue_values.append(revenue_value)
                    profit_values.append(profit_value)
            except Exception:
                continue
        
        # 创建DataFrame
        financial_metrics['日期'] = dates
        financial_metrics['营业收入'] = revenue_values
        financial_metrics['净利润'] = profit_values
    
    # 将收入和利润列转换为数值型
    financial_metrics['营业收入'] = pd.to_numeric(financial_metrics['营业收入'], errors='coerce')
    financial_metrics['净利润'] = pd.to_numeric(financial_metrics['净利润'], errors='coerce')
    
    # 检查是否有有效数据
    if financial_metrics.empty or len(financial_metrics) < 1:
        return None, None, None
    
    # 按日期排序（最新的在前）
    try:
        financial_metrics['日期'] = pd.to_datetime(financial_metrics['日期'], errors='coerce')
        financial_metrics = financial_metrics.sort_values('日期', ascending=False).reset_index(drop=True)
    except:
        # 如果日期无法转换，保持原有顺序
        pass
    
    # 返回营收和净利润列表，以及日期
    return financial_metrics['营业收入'].tolist(), financial_metrics['净利润'].tolist(), financial_metrics['日期'].tolist()

def plot_financial_metrics(revenue, profit, dates, stock_code, stock_name):
    """绘制财务指标图表"""
    if revenue is None or profit is None or len(revenue) < 2:
        st.error("数据不足，无法绘制财务指标图表")
        return

    # 将列表转换为DataFrame
    financial_data = pd.DataFrame({
        '日期': dates,
        '营业收入': revenue,
        '净利润': profit
    })
    
    # 按日期排序（确保从老到新）
    try:
        financial_data['日期'] = pd.to_datetime(financial_data['日期'])
        financial_data = financial_data.sort_values('日期')
    except:
        st.warning("日期排序失败，使用原始数据顺序")
        
    # 计算同比增长率
    try:
        financial_data['营业收入_同比增长'] = [None] + [
            (financial_data.iloc[i, 1] / financial_data.iloc[i-1, 1] - 1) * 100 
            if financial_data.iloc[i-1, 1] != 0 else None 
            for i in range(1, len(financial_data))
        ]
        
        financial_data['净利润_同比增长'] = [None] + [
            (financial_data.iloc[i, 2] / financial_data.iloc[i-1, 2] - 1) * 100 
            if financial_data.iloc[i-1, 2] != 0 else None 
            for i in range(1, len(financial_data))
        ]
        
        # 计算平均增长率
        avg_revenue_growth = financial_data['营业收入_同比增长'].dropna().mean()
        avg_profit_growth = financial_data['净利润_同比增长'].dropna().mean()
    except Exception as e:
        st.warning(f"计算增长率时出现问题: {e}")
        avg_revenue_growth = None
        avg_profit_growth = None

    # 如果数据量太少，可能无法进行可视化
    if len(financial_data) < 2:
        st.warning("数据点数量不足，无法绘制趋势图")
        return

    # 绘制营业收入和净利润趋势图
    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(financial_data))
    x_labels = [d.strftime('%Y-%m-%d') if isinstance(d, pd.Timestamp) else str(d) for d in financial_data['日期']]
    
    # 使用双Y轴，左边是营业收入，右边是净利润
    ax.plot(x, financial_data['营业收入'], 'b-', marker='o', linewidth=2, label='营业收入')
    ax.set_ylabel('营业收入', color='b', fontsize=12)
    ax.tick_params(axis='y', labelcolor='b')
    
    # 添加数据标签
    for i, v in enumerate(financial_data['营业收入']):
        ax.text(i, v * 1.02, f'{v/1e8:.2f}亿', color='b', ha='center')
    
    # 创建右侧Y轴
    ax2 = ax.twinx()
    ax2.plot(x, financial_data['净利润'], 'r-', marker='s', linewidth=2, label='净利润')
    ax2.set_ylabel('净利润', color='r', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='r')
    
    # 添加数据标签
    for i, v in enumerate(financial_data['净利润']):
        ax2.text(i, v * 1.02, f'{v/1e8:.2f}亿', color='r', ha='center')
    
    # 设置X轴
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45)
    
    # 添加标题和图例
    plt.title(f'{stock_code} {stock_name} 营业收入与净利润趋势', fontsize=14)
    
    # 合并两个图例
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # 添加平均增长率注释
    if avg_revenue_growth is not None and avg_profit_growth is not None:
        annotation_text = f"营业收入平均增长率: {avg_revenue_growth:.2f}%\n净利润平均增长率: {avg_profit_growth:.2f}%"
        plt.annotate(annotation_text, xy=(0.05, 0.05), xycoords='figure fraction', 
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
    
    # 显示图表
    plt.tight_layout()
    st.pyplot(fig)
    
    # 绘制增长率图表
    if len(financial_data) >= 3:  # 至少需要3个点才能有2个增长率
        fig, ax = plt.subplots(figsize=(12, 6))
        x = range(1, len(financial_data))  # 第一个点没有增长率
        x_labels = [d.strftime('%Y-%m-%d') if isinstance(d, pd.Timestamp) else str(d) for d in financial_data['日期'][1:]]
        
        # 去除None值
        revenue_growth = financial_data['营业收入_同比增长'].dropna().tolist()
        profit_growth = financial_data['净利润_同比增长'].dropna().tolist()
        
        # 使用条形图
        width = 0.35
        ax.bar(x, revenue_growth, width, label='营业收入同比增长率', color='blue', alpha=0.7)
        ax.bar([i + width for i in x], profit_growth, width, label='净利润同比增长率', color='red', alpha=0.7)
        
        # 添加数据标签
        for i, v in enumerate(revenue_growth):
            ax.text(i + 1, v + (5 if v > 0 else -10), f'{v:.2f}%', color='blue', ha='center')
        
        for i, v in enumerate(profit_growth):
            ax.text(i + 1 + width, v + (5 if v > 0 else -10), f'{v:.2f}%', color='red', ha='center')
        
        # 设置X轴
        ax.set_xticks([i + width/2 for i in x])
        ax.set_xticklabels(x_labels, rotation=45)
        
        # 添加标题和图例
        plt.title(f'{stock_code} {stock_name} 同比增长率', fontsize=14)
        ax.set_ylabel('增长率(%)', fontsize=12)
        ax.legend()
        
        # 添加0线
        ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        
        # 添加平均增长率线
        if avg_revenue_growth is not None:
            ax.axhline(y=avg_revenue_growth, color='blue', linestyle='--', alpha=0.5)
            ax.text(x[-1], avg_revenue_growth, f'营收平均: {avg_revenue_growth:.2f}%', color='blue')
        
        if avg_profit_growth is not None:
            ax.axhline(y=avg_profit_growth, color='red', linestyle='--', alpha=0.5)
            ax.text(x[-1], avg_profit_growth, f'利润平均: {avg_profit_growth:.2f}%', color='red')
        
        # 显示图表
        plt.tight_layout()
        st.pyplot(fig)
        
        # 绘制饼图展示最近一年的净利润与营业收入比例
        if len(financial_data) > 0:
            latest_data = financial_data.iloc[-1]
            latest_year = latest_data['日期'].year if isinstance(latest_data['日期'], pd.Timestamp) else "最新"
            
            fig, ax = plt.subplots(figsize=(8, 8))
            profit_ratio = latest_data['净利润'] / latest_data['营业收入'] * 100
            cost_ratio = 100 - profit_ratio
            
            labels = ['净利润', '成本及费用']
            sizes = [profit_ratio, cost_ratio]
            colors = ['#ff9999','#66b3ff']
            explode = (0.1, 0)  # 突出净利润
            
            ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                  shadow=True, startangle=90)
            ax.axis('equal')  # 保证饼图是圆的
            
            plt.title(f'{stock_code} {stock_name} {latest_year}年净利润占比', fontsize=14)
            st.pyplot(fig)
            
            # 添加净利润率的文字说明
            st.info(f"{latest_year}年净利润率: {profit_ratio:.2f}%，这意味着每100元营业收入中有{profit_ratio:.2f}元转化为净利润。")
    else:
        st.warning("数据点不足，无法计算同比增长率")
        
    # 保存图表
    chart_file = os.path.join(chart_dir, f"{stock_code}_financial_metrics.png")
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    plt.plot(x_labels, financial_data['营业收入'], 'b-', marker='o', linewidth=2, label='营业收入')
    plt.plot(x_labels, financial_data['净利润'], 'r-', marker='s', linewidth=2, label='净利润')
    plt.title(f'{stock_code} {stock_name} 营业收入与净利润趋势', fontsize=14)
    plt.xticks(rotation=45)
    plt.legend()
    
    if len(financial_data) >= 3:
        plt.subplot(2, 1, 2)
        plt.bar(x_labels[1:], revenue_growth, width=0.35, label='营业收入同比增长率', color='blue', alpha=0.7)
        plt.bar([i + width for i in range(len(x_labels[1:]))], profit_growth, width=0.35, label='净利润同比增长率', color='red', alpha=0.7)
        plt.title(f'{stock_code} {stock_name} 同比增长率', fontsize=14)
        plt.xticks(rotation=45)
        plt.legend()
    
    plt.tight_layout()
    plt.savefig(chart_file)
    plt.close()
    
    st.success(f"财务指标图表已保存至 {chart_file}")
    
    # 返回计算得到的平均增长率
    return {
        "avg_revenue_growth": avg_revenue_growth,
        "avg_profit_growth": avg_profit_growth
    }

def get_financial_ratios(balance_sheet, income_statement):
    """计算财务比率"""
    if balance_sheet is None or income_statement is None or balance_sheet.empty or income_statement.empty:
        st.warning("资产负债表或利润表数据为空")
        return None
    
    # 打印资产负债表前多行供调试，显示所有数据
    st.write("资产负债表结构预览:")
    st.dataframe(balance_sheet)
    
    # 确保所有列名都是字符串类型（重要）
    balance_sheet = balance_sheet.copy(deep=True)
    income_statement = income_statement.copy(deep=True)
    
    # 检查并转换列名
    balance_sheet.columns = [str(col) for col in balance_sheet.columns]
    income_statement.columns = [str(col) for col in income_statement.columns]
    
    # 获取共同的日期列（第一列是项目名，从第二列开始是日期数据）
    bs_dates = [str(date) for date in balance_sheet.columns[1:]]
    is_dates = [str(date) for date in income_statement.columns[1:]]
    
    st.write(f"资产负债表日期列: {', '.join(bs_dates)}")
    st.write(f"利润表日期列: {', '.join(is_dates)}")
    
    common_dates = sorted(set(bs_dates) & set(is_dates), reverse=True)
    st.write(f"共同日期列: {', '.join(common_dates)}")
    st.write(f"共同日期总数: {len(common_dates)}")
    
    # 使用所有可用的日期数据，不限制上限
    st.write(f"将使用全部 {len(common_dates)} 个共同日期的数据")
    
    if not common_dates:
        st.error("资产负债表和利润表没有共同的日期")
        return None
    
    # 检查数据类型
    st.write(f"资产负债表第一列的数据类型: {balance_sheet.iloc[:, 0].dtype}")
    st.write(f"利润表第一列的数据类型: {income_statement.iloc[:, 0].dtype}")
    
    # 使用更高效的方式创建新的DataFrame，避免DataFrame碎片化
    bs_data_dict = {}
    is_data_dict = {}
    
    # 第一列转换为字符串
    bs_data_dict[balance_sheet.columns[0]] = balance_sheet.iloc[:, 0].astype(str)
    is_data_dict[income_statement.columns[0]] = income_statement.iloc[:, 0].astype(str)
    
    # 复制其他列
    for col in balance_sheet.columns[1:]:
        bs_data_dict[col] = balance_sheet[col]
    
    for col in income_statement.columns[1:]:
        is_data_dict[col] = income_statement[col]
    
    # 一次性创建新的DataFrame
    balance_sheet = pd.DataFrame(bs_data_dict)
    income_statement = pd.DataFrame(is_data_dict)
    
    # 打印第一列的所有值，帮助确定匹配关键词
    st.write("资产负债表第一列的所有值:")
    st.write(balance_sheet.iloc[:, 0].tolist())
    
    # 使用更多的匹配模式
    asset_patterns = ['总资产', '资产总计', '资产总额', '资产负债表', '资产合计', '资产总和']
    equity_patterns = ['所有者权益', '股东权益', '净资产', '所有者权益合计', '股东权益合计', '权益合计', '权益总计', '股东权益总计']
    profit_patterns = ['净利润', '归属于母公司股东的净利润', '归属于上市公司股东的净利润', '利润总额', '净利', '利润', '净利润(含少数股东损益)', '净利润(扣除少数股东损益)']
    
    # 使用"或"条件连接所有模式
    asset_pattern = '|'.join(asset_patterns)
    equity_pattern = '|'.join(equity_patterns)
    profit_pattern = '|'.join(profit_patterns)
    
    # 查找资产负债表中的总资产和净资产行
    try:
        asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains(asset_pattern, na=False, regex=True)]
    except Exception as e:
        st.error(f"查找总资产行时出错: {e}")
        asset_rows = pd.DataFrame()  # 创建空DataFrame
    
    try:
        equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains(equity_pattern, na=False, regex=True)]
    except Exception as e:
        st.error(f"查找净资产行时出错: {e}")
        equity_rows = pd.DataFrame()
    
    # 如果找不到匹配行，尝试更模糊的匹配
    if asset_rows.empty:
        st.warning("未找到总资产行，尝试更模糊的匹配")
        try:
            asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('资产', na=False, regex=True)]
        except Exception as e:
            st.error(f"模糊匹配总资产行时出错: {e}")
    
    if equity_rows.empty:
        st.warning("未找到净资产行，尝试更模糊的匹配")
        try:
            equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('权益', na=False, regex=True)]
        except Exception as e:
            st.error(f"模糊匹配净资产行时出错: {e}")
    
    # 查找利润表中的净利润行
    try:
        profit_rows = income_statement[income_statement.iloc[:, 0].str.contains(profit_pattern, na=False, regex=True)]
    except Exception as e:
        st.error(f"查找净利润行时出错: {e}")
        profit_rows = pd.DataFrame()
    
    if profit_rows.empty:
        st.warning("未找到净利润行，尝试更模糊的匹配")
        try:
            profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('利润', na=False, regex=True)]
        except Exception as e:
            st.error(f"模糊匹配净利润行时出错: {e}")
    
    # 显示查找结果
    st.write(f"找到的总资产行数: {len(asset_rows)}")
    if not asset_rows.empty:
        st.dataframe(asset_rows)
    
    st.write(f"找到的净资产行数: {len(equity_rows)}")
    if not equity_rows.empty:
        st.dataframe(equity_rows)
    
    st.write(f"找到的净利润行数: {len(profit_rows)}")
    if not profit_rows.empty:
        st.dataframe(profit_rows)
    
    if asset_rows.empty or equity_rows.empty or profit_rows.empty:
        st.error("无法找到所需的财务数据行")
        return None
    
    # 获取第一行
    asset_row = asset_rows.iloc[0]
    equity_row = equity_rows.iloc[0]
    profit_row = profit_rows.iloc[0]
    
    st.write(f"使用的总资产行: {asset_row.iloc[0]}")
    st.write(f"使用的净资产行: {equity_row.iloc[0]}")
    st.write(f"使用的净利润行: {profit_row.iloc[0]}")
    
    # 创建财务比率数据
    ratio_data = {
        '日期': [],
        '总资产(亿元)': [],
        '净资产(亿元)': [],
        '净利润(亿元)': [],
        'ROA(%)': [],  # 总资产收益率
        'ROE(%)': []   # 净资产收益率
    }
    
    # 获取原始日期列，用于索引
    bs_orig_dates = balance_sheet.columns[1:]
    is_orig_dates = income_statement.columns[1:]
    
    for date in common_dates:
        try:
            # 查找原始列索引
            bs_idx = bs_dates.index(date)
            is_idx = is_dates.index(date)
            
            # 获取实际的列名
            bs_col = bs_orig_dates[bs_idx]
            is_col = is_orig_dates[is_idx]
            
            st.write(f"处理日期 {date}，资产负债表列: {bs_col}，利润表列: {is_col}")
            
            # 检查是否有有效数据
            try:
                asset_value = asset_row[bs_col]
                equity_value = equity_row[bs_col]
                profit_value = profit_row[is_col]
                
                st.write(f"原始数据 - 总资产: {asset_value}, 净资产: {equity_value}, 净利润: {profit_value}")
                
                # 检查数据是否为空
                if pd.notna(asset_value) and pd.notna(equity_value) and pd.notna(profit_value):
                    try:
                        # 尝试转换为浮点数
                        total_asset = float(str(asset_value).replace(',', ''))
                        net_equity = float(str(equity_value).replace(',', ''))
                        net_profit = float(str(profit_value).replace(',', ''))
                        
                        st.write(f"转换后数据 - 总资产: {total_asset}, 净资产: {net_equity}, 净利润: {net_profit}")
                        
                        # 计算比率
                        roa = (net_profit / total_asset) * 100 if total_asset != 0 else None
                        roe = (net_profit / net_equity) * 100 if net_equity != 0 else None
                        
                        ratio_data['日期'].append(date)
                        ratio_data['总资产(亿元)'].append(total_asset / 100000000)
                        ratio_data['净资产(亿元)'].append(net_equity / 100000000)
                        ratio_data['净利润(亿元)'].append(net_profit / 100000000)
                        ratio_data['ROA(%)'].append(roa)
                        ratio_data['ROE(%)'].append(roe)
                        
                        st.write(f"计算的财务比率 - ROA: {roa}, ROE: {roe}")
                    except (ValueError, TypeError) as e:
                        st.warning(f"日期 {date} 的数据转换出错: {e}")
                else:
                    st.warning(f"日期 {date} 的数据包含空值")
            except Exception as e:
                st.warning(f"访问日期 {date} 数据时出错: {e}")
        except Exception as e:
            st.warning(f"处理日期 {date} 时出错: {e}")
    
    # 检查是否成功提取数据
    if not ratio_data['日期']:
        st.error("无法提取有效的财务比率数据")
        return None
        
    # 创建DataFrame
    ratio_df = pd.DataFrame(ratio_data)
    
    # 显示提取的数据
    st.write("提取的财务比率数据:")
    st.dataframe(ratio_df)
    
    st.success("成功提取财务比率数据")
    return ratio_df

def plot_financial_ratios(ratio_df, stock_code, stock_name):
    """绘制财务比率图表"""
    if ratio_df is None or ratio_df.empty or len(ratio_df) < 1:
        st.warning("没有足够的数据来绘制财务比率图表")
        return
    
    # 检查必要的列是否存在
    required_cols = ['日期', 'ROA(%)', 'ROE(%)']
    if not all(col in ratio_df.columns for col in required_cols):
        st.warning(f"财务比率数据缺少必要的列：{', '.join([col for col in required_cols if col not in ratio_df.columns])}")
        return
    
    st.subheader("财务比率分析")
    
    # 显示财务比率表格数据
    st.write("#### 财务比率数据")
    
    # 显示所有行
    st.dataframe(ratio_df)
    
    # 检查是否有足够的数据点绘制图表
    if len(ratio_df) < 2:
        st.warning("数据点太少，无法绘制有意义的趋势图")
        return
    
    try:
        # 如果数据点多于15个，只使用最近15个以确保图表清晰
        df_plot = ratio_df
        if len(ratio_df) > 15:
            st.info(f"数据点较多 ({len(ratio_df)}个)，图表将只显示最近15个数据点以确保清晰度")
            df_plot = ratio_df.iloc[:15].copy()
        
        # 反转日期顺序以便按时间顺序显示
        df_plot = df_plot.iloc[::-1].reset_index(drop=True)
        dates = df_plot['日期'].tolist()
        
        # 绘制资产规模趋势图
        st.write("#### 资产规模趋势")
        
        # 检查是否有总资产和净资产列
        has_assets = '总资产(亿元)' in df_plot.columns and '净资产(亿元)' in df_plot.columns
        
        if has_assets:
            # 创建图表
            fig, ax1 = plt.subplots(figsize=(14, 8))  # 增大图表尺寸
            
            # 总资产柱状图
            total_assets = df_plot['总资产(亿元)'].values
            bars = ax1.bar(dates, total_assets, alpha=0.7, color='steelblue', label='总资产')
            ax1.set_xlabel('报告期')
            ax1.set_ylabel('总资产（亿元）', color='steelblue')
            ax1.tick_params(axis='y', labelcolor='steelblue')
            
            # 调整x轴标签的显示
            if len(dates) > 5:
                plt.xticks(rotation=90)  # 垂直显示日期
            else:
                plt.xticks(rotation=45)
            
            # 在柱子上显示数值（如果数据点不多于10个）
            if len(total_assets) <= 10:
                for i, v in enumerate(total_assets):
                    if pd.notna(v):
                        ax1.text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=9)
            
            # 净资产折线图
            ax2 = ax1.twinx()
            net_equity = df_plot['净资产(亿元)'].values
            ax2.plot(dates, net_equity, color='red', marker='o', label='净资产')
            ax2.set_ylabel('净资产（亿元）', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            
            # 在点上显示数值（如果数据点不多于10个）
            if len(net_equity) <= 10:
                for i, v in enumerate(net_equity):
                    if pd.notna(v):
                        ax2.annotate(f'{v:.1f}', (i, v), xytext=(0, 5), textcoords='offset points', 
                                   ha='center', va='bottom', fontsize=9, color='red')
            
            # 添加标题和网格
            plt.title(f'{stock_code} ({stock_name}) 资产规模趋势')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # 合并图例
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            # 显示图表
            st.pyplot(fig)
            
            # 添加资产构成环形图（最近一期）
            st.write("#### 最近一期资产构成")
            latest_data = ratio_df.iloc[0]
            latest_date = latest_data['日期']
            
            # 检查是否有净资产和总资产数据
            if '净资产(亿元)' in latest_data and '总资产(亿元)' in latest_data:
                net_asset = latest_data['净资产(亿元)']
                total_asset = latest_data['总资产(亿元)']
                debt = total_asset - net_asset  # 负债 = 总资产 - 净资产
                
                if pd.notna(net_asset) and pd.notna(total_asset) and total_asset > 0:
                    # 创建环形图
                    fig, ax = plt.subplots(figsize=(10, 10))
                    
                    # 计算负债率
                    debt_ratio = (debt / total_asset) * 100
                    asset_ratio = (net_asset / total_asset) * 100
                    
                    # 数据和标签
                    sizes = [asset_ratio, debt_ratio]
                    labels = [f'净资产: {net_asset:.2f}亿元 ({asset_ratio:.1f}%)', 
                              f'负债: {debt:.2f}亿元 ({debt_ratio:.1f}%)']
                    colors = ['lightgreen', 'lightcoral']
                    
                    # 创建一个环形图
                    wedges, texts = ax.pie(sizes, wedgeprops=dict(width=0.5), startangle=90, colors=colors)
                    
                    # 添加图例
                    ax.legend(wedges, labels, loc="center", bbox_to_anchor=(0.5, 0.5))
                    
                    # 标题
                    plt.title(f"{latest_date} 资产负债构成 (总资产: {total_asset:.2f}亿元)")
                    ax.axis('equal')  # 确保饼图是圆的
                    
                    # 显示图表
                    st.pyplot(fig)
                    
                    # 添加资产和负债趋势
                    if len(df_plot) >= 2:
                        st.write("#### 净资产占比趋势")
                        
                        # 计算所有期间的净资产比率
                        asset_ratios = []
                        debt_ratios = []
                        valid_dates = []
                        
                        for i, row in df_plot.iterrows():
                            if pd.notna(row['净资产(亿元)']) and pd.notna(row['总资产(亿元)']) and row['总资产(亿元)'] > 0:
                                net_a = row['净资产(亿元)']
                                total_a = row['总资产(亿元)']
                                debt_a = total_a - net_a
                                
                                asset_ratios.append((net_a / total_a) * 100)
                                debt_ratios.append((debt_a / total_a) * 100)
                                valid_dates.append(row['日期'])
                        
                        if valid_dates:
                            # 绘制净资产占比趋势图
                            fig, ax = plt.subplots(figsize=(14, 8))
                            
                            # 创建堆叠区域图
                            ax.fill_between(valid_dates, 0, asset_ratios, alpha=0.5, color='lightgreen', label='净资产占比')
                            ax.fill_between(valid_dates, asset_ratios, [100] * len(valid_dates), alpha=0.5, color='lightcoral', label='负债占比')
                            
                            # 添加资产比率数值
                            if len(valid_dates) <= 10:
                                for i, (date, ratio) in enumerate(zip(valid_dates, asset_ratios)):
                                    ax.text(date, ratio/2, f'{ratio:.1f}%', ha='center', va='center', fontsize=9, color='darkgreen')
                                    ax.text(date, (ratio + 100)/2, f'{100-ratio:.1f}%', ha='center', va='center', fontsize=9, color='darkred')
                            
                            # 设置y轴范围
                            ax.set_ylim(0, 100)
                            
                            # 调整x轴标签显示
                            if len(valid_dates) > 5:
                                plt.xticks(rotation=90)
                            else:
                                plt.xticks(rotation=45)
                            
                            # 添加标题和标签
                            plt.title(f"{stock_code} ({stock_name}) 资产负债比例趋势")
                            plt.xlabel('报告期')
                            plt.ylabel('占比 (%)')
                            plt.grid(True, alpha=0.3)
                            plt.legend(loc='upper right')
                            plt.tight_layout()
                            
                            # 显示图表
                            st.pyplot(fig)
                else:
                    st.info("净资产或总资产数据不完整，无法创建资产构成图")
        
        # 绘制ROA和ROE趋势图
        st.write("#### ROA和ROE趋势")
        
        # 检查是否有ROA和ROE列以及值是否都有效
        has_ratios = 'ROA(%)' in df_plot.columns and 'ROE(%)' in df_plot.columns
        valid_roa = has_ratios and df_plot['ROA(%)'].notna().any()
        valid_roe = has_ratios and df_plot['ROE(%)'].notna().any()
        
        if valid_roa or valid_roe:
            fig, ax = plt.subplots(figsize=(14, 8))  # 增大图表尺寸
            
            # 如果有有效的ROA数据，绘制ROA折线图
            if valid_roa:
                roa_data = df_plot['ROA(%)'].values
                ax.plot(dates, roa_data, marker='o', color='steelblue', label='ROA(%)')
                
                # 在点上显示数值（如果数据点不多于10个）
                if len(roa_data) <= 10:
                    for i, v in enumerate(roa_data):
                        if pd.notna(v):
                            ax.annotate(f'{v:.2f}%', (i, v), xytext=(0, 5), textcoords='offset points', 
                                      ha='center', va='bottom', fontsize=9, color='steelblue')
            
            # 如果有有效的ROE数据，绘制ROE折线图
            if valid_roe:
                roe_data = df_plot['ROE(%)'].values
                ax.plot(dates, roe_data, marker='s', color='red', label='ROE(%)')
                
                # 在点上显示数值（如果数据点不多于10个）
                if len(roe_data) <= 10:
                    for i, v in enumerate(roe_data):
                        if pd.notna(v):
                            ax.annotate(f'{v:.2f}%', (i, v), xytext=(0, -15), textcoords='offset points', 
                                      ha='center', va='top', fontsize=9, color='red')
            
            # 调整x轴标签的显示
            if len(dates) > 5:
                plt.xticks(rotation=90)  # 垂直显示日期
            else:
                plt.xticks(rotation=45)
            
            # 添加标题和标签
            plt.title(f'{stock_code} ({stock_name}) ROA和ROE趋势')
            plt.xlabel('报告期')
            plt.ylabel('比率 (%)')
            plt.grid(True, alpha=0.3)
            plt.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
            
            # 添加图例
            if valid_roa or valid_roe:
                plt.legend()
            
            plt.tight_layout()
            
            # 显示图表
            st.pyplot(fig)
            
            # 添加ROA和ROE比较扇形图（最近一期）
            st.write("#### 最近一期ROA和ROE对比")
            
            latest_data = ratio_df.iloc[0]
            latest_date = latest_data['日期']
            
            # 检查是否有ROA和ROE数据
            valid_latest_roa = 'ROA(%)' in latest_data and pd.notna(latest_data['ROA(%)'])
            valid_latest_roe = 'ROE(%)' in latest_data and pd.notna(latest_data['ROE(%)'])
            
            if valid_latest_roa and valid_latest_roe:
                roa_val = latest_data['ROA(%)']
                roe_val = latest_data['ROE(%)']
                
                # 创建两个并排的扇形图
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
                
                # ROA扇形图
                if roa_val >= 0:
                    labels = ['ROA', '其他资产回报']
                    sizes = [roa_val, max(0, 100 - roa_val)]  # 确保不会有负值
                    colors = ['skyblue', 'lightgray']
                    
                    ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
                    ax1.axis('equal')
                    ax1.set_title(f"{latest_date} 总资产收益率 (ROA: {roa_val:.2f}%)")
                else:
                    ax1.text(0.5, 0.5, f'ROA为负值 ({roa_val:.2f}%)', ha='center', va='center', fontsize=12)
                    ax1.axis('off')
                
                # ROE扇形图
                if roe_val >= 0:
                    labels = ['ROE', '其他权益回报']
                    sizes = [roe_val, max(0, 100 - roe_val)]  # 确保不会有负值
                    colors = ['salmon', 'lightgray']
                    
                    ax2.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
                    ax2.axis('equal')
                    ax2.set_title(f"{latest_date} 净资产收益率 (ROE: {roe_val:.2f}%)")
                else:
                    ax2.text(0.5, 0.5, f'ROE为负值 ({roe_val:.2f}%)', ha='center', va='center', fontsize=12)
                    ax2.axis('off')
                
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.info("最近一期的ROA或ROE数据不完整，无法创建对比图")
        else:
            st.info("无法绘制ROA和ROE趋势图，因为没有有效的数据")
    
    except Exception as e:
        st.error(f"绘制财务比率图表时出错: {e}")
        import traceback
        st.error(traceback.format_exc())

def download_financial_reports_em(stock_code):
    """从东方财富网下载更多历史财务报表数据"""
    # 显示下载进度
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 获取股票前缀
        prefix = get_stock_prefix(stock_code)
        
        try:
            # 获取股票名称
            status_text.text("正在获取股票信息...")
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            stock_name = stock_info.loc[0, "股票简称"] if not stock_info.empty else "未知"
        except Exception as e:
            st.warning(f"无法获取股票名称: {e}")
            stock_name = "未知"
        
        progress_bar.progress(10)
        status_text.text(f"开始从东方财富下载 {stock_code}({stock_name}) 的财务报表...")
        
        # 尝试使用备选方法获取财务数据
        st.info("尝试备用方法获取财务数据...")
        
        # 下载资产负债表（最近20个季度）
        status_text.text(f"正在下载 {stock_name}({stock_code}) 的资产负债表...")
        balance_sheet = None
        try:
            # 尝试第一种方法
            try:
                st.info("尝试使用stock_balance_sheet_by_report_em方法")
                balance_sheet = ak.stock_balance_sheet_by_report_em(symbol=stock_code)
                if balance_sheet is None or balance_sheet.empty:
                    raise ValueError("API返回了空数据")
            except Exception as e1:
                st.warning(f"第一种方法失败: {e1}")
                # 尝试第二种方法
                try:
                    st.info("尝试使用stock_financial_abstract方法")
                    balance_sheet = ak.stock_financial_abstract(stock=stock_code)
                    if balance_sheet is None or balance_sheet.empty:
                        raise ValueError("API返回了空数据")
                except Exception as e2:
                    st.warning(f"第二种方法也失败: {e2}")
                    # 尝试第三种方法 - 使用新浪财经的数据
                    try:
                        st.info("回退到新浪财经数据源")
                        full_code = prefix + stock_code
                        balance_sheet = ak.stock_financial_report_sina(stock=full_code, symbol="资产负债表")
                        if balance_sheet is None or balance_sheet.empty:
                            raise ValueError("新浪财经API返回了空数据")
                    except Exception as e3:
                        st.error(f"所有方法都失败: {e3}")
                        balance_sheet = None
            
            progress_bar.progress(30)
            if balance_sheet is not None and not balance_sheet.empty:
                st.success("成功获取资产负债表")
                st.write("资产负债表预览:")
                st.dataframe(balance_sheet.head())
            
        except Exception as e:
            st.error(f"下载资产负债表时出错: {e}")
            balance_sheet = None
        
        # 下载利润表
        status_text.text(f"正在下载 {stock_name}({stock_code}) 的利润表...")
        income_statement = None
        try:
            # 尝试第一种方法
            try:
                st.info("尝试使用stock_profit_sheet_by_report_em方法")
                income_statement = ak.stock_profit_sheet_by_report_em(symbol=stock_code)
                if income_statement is None or income_statement.empty:
                    raise ValueError("API返回了空数据")
            except Exception as e1:
                st.warning(f"第一种方法失败: {e1}")
                # 尝试第二种方法
                try:
                    st.info("尝试使用stock_financial_abstract方法")
                    income_statement = ak.stock_financial_abstract(stock=stock_code)
                    if income_statement is None or income_statement.empty:
                        raise ValueError("API返回了空数据")
                except Exception as e2:
                    st.warning(f"第二种方法也失败: {e2}")
                    # 尝试第三种方法 - 使用新浪财经的数据
                    try:
                        st.info("回退到新浪财经数据源")
                        full_code = prefix + stock_code
                        income_statement = ak.stock_financial_report_sina(stock=full_code, symbol="利润表")
                        if income_statement is None or income_statement.empty:
                            raise ValueError("新浪财经API返回了空数据")
                    except Exception as e3:
                        st.error(f"所有方法都失败: {e3}")
                        income_statement = None
            
            progress_bar.progress(60)
            if income_statement is not None and not income_statement.empty:
                st.success("成功获取利润表")
                st.write("利润表预览:")
                st.dataframe(income_statement.head())
            
        except Exception as e:
            st.error(f"下载利润表时出错: {e}")
            income_statement = None
        
        # 下载现金流量表
        status_text.text(f"正在下载 {stock_name}({stock_code}) 的现金流量表...")
        cash_flow = None
        try:
            # 尝试第一种方法
            try:
                st.info("尝试使用stock_cash_flow_sheet_by_report_em方法")
                cash_flow = ak.stock_cash_flow_sheet_by_report_em(symbol=stock_code)
                if cash_flow is None or cash_flow.empty:
                    raise ValueError("API返回了空数据")
            except Exception as e1:
                st.warning(f"第一种方法失败: {e1}")
                # 尝试第二种方法 - 使用新浪财经的数据
                try:
                    st.info("回退到新浪财经数据源")
                    full_code = prefix + stock_code
                    cash_flow = ak.stock_financial_report_sina(stock=full_code, symbol="现金流量表")
                    if cash_flow is None or cash_flow.empty:
                        raise ValueError("新浪财经API返回了空数据")
                except Exception as e2:
                    st.error(f"所有方法都失败: {e2}")
                    cash_flow = None
            
            progress_bar.progress(90)
            if cash_flow is not None and not cash_flow.empty:
                st.success("成功获取现金流量表")
                st.write("现金流量表预览:")
                st.dataframe(cash_flow.head())
            
        except Exception as e:
            st.error(f"下载现金流量表时出错: {e}")
            cash_flow = None
        
        successful_downloads = 0
        report_data = {}
        
        # 检查AKShare版本
        try:
            import akshare
            st.info(f"当前AKShare版本: {akshare.__version__}")
        except:
            st.warning("无法获取AKShare版本信息")
        
        # 转换和保存数据
        if balance_sheet is not None and not balance_sheet.empty:
            # 保存文件
            file_path = os.path.join(data_dir, f"{stock_code}_balance_sheet_em_{current_date}.csv")
            balance_sheet.to_csv(file_path, index=False, encoding="utf-8-sig")
            
            # 检查数据结构
            st.write("资产负债表原始列名:", balance_sheet.columns.tolist())
            
            # 根据数据结构判断是否需要转换格式
            if 'REPORT_DATE' in balance_sheet.columns or any('DATE' in col for col in balance_sheet.columns):
                # 是东方财富格式，需要转换
                bs_converted = convert_em_to_sina_format(balance_sheet)
            else:
                # 可能已经是新浪格式
                bs_converted = balance_sheet
            
            # 存储报表数据以供后续分析
            report_data["资产负债表"] = bs_converted
            successful_downloads += 1
            
        if income_statement is not None and not income_statement.empty:
            # 保存文件
            file_path = os.path.join(data_dir, f"{stock_code}_income_statement_em_{current_date}.csv")
            income_statement.to_csv(file_path, index=False, encoding="utf-8-sig")
            
            # 检查数据结构
            st.write("利润表原始列名:", income_statement.columns.tolist())
            
            # 根据数据结构判断是否需要转换格式
            if 'REPORT_DATE' in income_statement.columns or any('DATE' in col for col in income_statement.columns):
                # 是东方财富格式，需要转换
                is_converted = convert_em_to_sina_format(income_statement)
            else:
                # 可能已经是新浪格式
                is_converted = income_statement
            
            # 存储报表数据
            report_data["利润表"] = is_converted
            successful_downloads += 1
            
        if cash_flow is not None and not cash_flow.empty:
            # 保存文件
            file_path = os.path.join(data_dir, f"{stock_code}_cash_flow_em_{current_date}.csv")
            cash_flow.to_csv(file_path, index=False, encoding="utf-8-sig")
            
            # 检查数据结构
            st.write("现金流量表原始列名:", cash_flow.columns.tolist())
            
            # 根据数据结构判断是否需要转换格式
            if 'REPORT_DATE' in cash_flow.columns or any('DATE' in col for col in cash_flow.columns):
                # 是东方财富格式，需要转换
                cf_converted = convert_em_to_sina_format(cash_flow)
            else:
                # 可能已经是新浪格式
                cf_converted = cash_flow
            
            # 存储报表数据
            report_data["现金流量表"] = cf_converted
            successful_downloads += 1
        
        if successful_downloads > 0:
            status_text.text("下载完成！")
            progress_bar.progress(100)
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            st.success(f"成功下载了 {stock_code}({stock_name}) 的 {successful_downloads} 个财务报表")
            return report_data, stock_name
        else:
            status_text.empty()
            progress_bar.empty()
            st.error("未能成功下载任何财务报表。")
            st.warning("建议尝试以下解决方案：")
            st.markdown("""
            1. 检查股票代码是否正确
            2. 使用新浪财经数据源尝试下载
            3. 检查网络连接
            4. 更新AKShare库：`pip install --upgrade akshare`
            5. 查看AKShare文档了解API变化：https://www.akshare.xyz/
            """)
            return None, stock_name

    except Exception as e:
        status_text.empty()
        progress_bar.empty()
        st.error(f"程序执行出错: {e}")
        return None, "未知"

def convert_em_to_sina_format(df):
    """将东方财富的数据格式转换为类似新浪财经的格式，以便兼容已有的分析函数"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 显示原始数据结构
    st.write("原始东方财富数据结构:")
    st.dataframe(df.head())
    st.write("列名:", df.columns.tolist())
    
    # 检查数据结构类型
    # 情况1: 第一列是项目名称，其余列是日期 (标准格式，无需转换)
    # 情况2: 有REPORT_DATE列和项目列，需要重组数据
    # 情况3: 第一列是日期，其余列是项目 (需要转置)
    
    first_col = df.columns[0]
    st.write(f"第一列名称: {first_col}")
    
    # 尝试检测数据结构
    is_date_in_first_col = False
    date_pattern = r'^\d{8}$|^\d{4}-\d{2}-\d{2}$'
    
    # 检查第一列的前几个值，判断是否为日期
    sample_values = df.iloc[:5, 0].astype(str).tolist()
    st.write(f"第一列样本值: {sample_values}")
    
    # 检查是否有日期列
    date_cols = [col for col in df.columns if 'DATE' in col or '日期' in col or '报告期' in col or '报告日' in col]
    st.write(f"可能的日期列: {date_cols}")
    
    # 检查是否有明确的项目列
    item_cols = [col for col in df.columns if '项目' in col or 'ITEM' in col or '科目' in col]
    st.write(f"可能的项目列: {item_cols}")
    
    # 情况处理
    if 'REPORT_DATE' in df.columns or date_cols:
        # 情况2: 有明确的日期列
        date_col = date_cols[0] if date_cols else 'REPORT_DATE'
        st.write(f"使用日期列: {date_col}")
        
        # 找到项目列
        item_col = None
        if item_cols:
            item_col = item_cols[0]
        else:
            # 如果没有明确的项目列，查看其他列是否可能是项目列
            non_date_cols = [col for col in df.columns if col != date_col]
            if non_date_cols:
                # 检查这些列是否包含常见的财务项目名称
                for col in non_date_cols:
                    sample = df[col].astype(str).tolist()[:10]
                    if any('收入' in s or '利润' in s or '资产' in s or '负债' in s for s in sample):
                        item_col = col
                        break
                
                # 如果仍未找到，使用第一个非日期列
                if not item_col:
                    item_col = non_date_cols[0]
        
        st.write(f"使用项目列: {item_col}")
        
        # 转换为新浪格式
        pivot_df = pd.DataFrame()
        if item_col:
            pivot_df[item_col] = df[item_col].unique()
            
            # 获取唯一日期
            dates = df[date_col].unique()
            for date in dates:
                date_str = str(date).replace('-', '')
                if len(date_str) > 8:
                    date_str = date_str[:8]
                
                # 筛选该日期的数据
                date_data = df[df[date_col] == date]
                
                # 查找数值列
                value_cols = [col for col in df.columns if col not in [date_col, item_col]]
                if value_cols:
                    value_col = value_cols[0]  # 使用第一个值列
                    
                    # 为每个项目找到对应的值
                    for item in pivot_df[item_col]:
                        item_row = date_data[date_data[item_col] == item]
                        if not item_row.empty:
                            value = item_row[value_col].iloc[0]
                            # 在透视表中设置值
                            pivot_df.loc[pivot_df[item_col] == item, date_str] = value
        
        st.write("转换后的数据结构:")
        st.dataframe(pivot_df.head())
        return pivot_df
        
    elif all(re.match(date_pattern, str(val)) for val in sample_values if str(val) not in ['nan', 'None']):
        # 情况3: 第一列是日期，需要转置
        st.write("检测到第一列是日期，需要转置数据")
        
        # 创建新的DataFrame
        transposed_df = pd.DataFrame()
        
        # 将第一列设为索引
        df_indexed = df.set_index(df.columns[0])
        
        # 转置
        df_transposed = df_indexed.transpose()
        
        # 重置索引
        df_transposed.reset_index(inplace=True)
        
        # 设置第一列名称为"项目"
        df_transposed.rename(columns={'index': '项目'}, inplace=True)
        
        st.write("转置后的数据结构:")
        st.dataframe(df_transposed.head())
        return df_transposed
        
    else:
        # 情况1: 标准格式，无需转换
        st.write("数据已经是标准格式，无需转换")
        return df

def download_annual_reports_em(stock_code):
    """从东方财富下载股票的年度财务报表"""
    try:
        st.info(f"开始从东方财富下载 {stock_code} 的年度财务报表数据...")
        
        # 用于检测AKShare是否有相应函数的辅助函数
        def has_ak_function(function_name):
            return hasattr(ak, function_name)
        
        # 添加股票代码前缀
        prefix = get_stock_prefix(stock_code)
        em_stock_code = f"{prefix.upper()}{stock_code}"
        
        # 尝试获取年度资产负债表
        try:
            balance_sheet = None
            
            # 尝试使用年度报表的API
            if has_ak_function('stock_balance_sheet_by_yearly_em'):
                try:
                    balance_sheet = ak.stock_balance_sheet_by_yearly_em(symbol=em_stock_code)
                    if balance_sheet is not None and not balance_sheet.empty:
                        st.success("使用 stock_balance_sheet_by_yearly_em 下载年度资产负债表成功")
                    else:
                        st.warning(f"使用 stock_balance_sheet_by_yearly_em 下载的资产负债表数据为空")
                except Exception as e:
                    st.warning(f"使用 stock_balance_sheet_by_yearly_em 下载年度资产负债表失败: {e}")
            
            # 如果年度API失败，尝试使用季度API，然后筛选年度数据
            if balance_sheet is None or (isinstance(balance_sheet, pd.DataFrame) and balance_sheet.empty):
                try:
                    # 使用季度报表API
                    if has_ak_function('stock_balance_sheet_by_report_em'):
                        quarterly_bs = ak.stock_balance_sheet_by_report_em(symbol=em_stock_code)
                        
                        # 检查数据是否为空
                        if quarterly_bs is not None and not quarterly_bs.empty:
                            # 筛选出年度报表（通常日期是年底的12月31日）
                            if 'REPORT_DATE' in quarterly_bs.columns:
                                annual_bs = quarterly_bs[quarterly_bs['REPORT_DATE'].str.endswith('1231', na=False)]
                                if not annual_bs.empty:
                                    balance_sheet = annual_bs
                                    st.success("使用季度报表筛选得到年度资产负债表成功")
                                else:
                                    st.warning("从季度数据中未能筛选出年度资产负债表数据")
                            else:
                                st.warning("季度资产负债表数据中没有REPORT_DATE列")
                        else:
                            st.warning("下载的季度资产负债表数据为空")
                except Exception as e:
                    st.warning(f"尝试从季度报表筛选年度资产负债表失败: {e}")
            
            # 如果上述都失败，尝试使用最基本的季度API，然后筛选
            if balance_sheet is None or (isinstance(balance_sheet, pd.DataFrame) and balance_sheet.empty):
                try:
                    if has_ak_function('stock_balance_sheet_by_quarterly_em'):
                        quarterly_bs = ak.stock_balance_sheet_by_quarterly_em(symbol=em_stock_code)
                        
                        # 检查数据是否为空
                        if quarterly_bs is not None and not quarterly_bs.empty:
                            # 筛选出年度报表
                            if 'REPORT_DATE' in quarterly_bs.columns:
                                annual_bs = quarterly_bs[quarterly_bs['REPORT_DATE'].str.endswith('1231', na=False)]
                                if not annual_bs.empty:
                                    balance_sheet = annual_bs
                                    st.success("使用季度API筛选得到年度资产负债表成功")
                                else:
                                    st.warning("从季度API数据中未能筛选出年度资产负债表数据")
                            else:
                                st.warning("季度API资产负债表数据中没有REPORT_DATE列")
                        else:
                            st.warning("下载的季度API资产负债表数据为空")
                except Exception as e:
                    st.warning(f"尝试从季度API筛选年度资产负债表失败: {e}")
            
            # 尝试直接使用stock_financial_analysis_indicator函数
            if balance_sheet is None or (isinstance(balance_sheet, pd.DataFrame) and balance_sheet.empty):
                try:
                    if has_ak_function('stock_financial_analysis_indicator'):
                        indicators = ak.stock_financial_analysis_indicator(symbol=stock_code)
                        if indicators is not None and not indicators.empty:
                            st.warning("使用财务指标接口获取数据，可能不包含完整资产负债表信息")
                            # 尝试创建一个最小化的资产负债表
                            if '日期' in indicators.columns:
                                # 筛选年度数据
                                annual_indicators = indicators[indicators['日期'].str.endswith('12-31', na=False)]
                                if not annual_indicators.empty:
                                    # 创建一个基本的资产负债表DataFrame
                                    bs_data = {
                                        'REPORT_DATE': annual_indicators['日期'].apply(lambda x: x.replace('-', '')),
                                        'TOTAL_ASSETS': annual_indicators.get('总资产(元)', np.nan),
                                        'TOTAL_LIABILITIES': annual_indicators.get('总负债(元)', np.nan),
                                        'TOTAL_SHAREHOLDERS_EQUITY': annual_indicators.get('股东权益(元)', np.nan)
                                    }
                                    balance_sheet = pd.DataFrame(bs_data)
                                    st.success("使用财务指标接口创建了基本资产负债表")
                        else:
                            st.warning("财务指标接口数据为空")
                except Exception as e:
                    st.warning(f"使用财务指标接口获取资产负债表数据失败: {e}")

        except Exception as e:
            st.error(f"下载年度资产负债表时出错: {e}")
            balance_sheet = pd.DataFrame()
        
        # 尝试获取年度利润表
        try:
            income_statement = None
            
            # 尝试使用年度报表的API
            if has_ak_function('stock_profit_sheet_by_yearly_em'):
                try:
                    income_statement = ak.stock_profit_sheet_by_yearly_em(symbol=em_stock_code)
                    if income_statement is not None and not income_statement.empty:
                        st.success("使用 stock_profit_sheet_by_yearly_em 下载年度利润表成功")
                    else:
                        st.warning(f"使用 stock_profit_sheet_by_yearly_em 下载的利润表数据为空")
                except Exception as e:
                    st.warning(f"使用 stock_profit_sheet_by_yearly_em 下载年度利润表失败: {e}")
            
            # 如果年度API失败，尝试使用季度API，然后筛选年度数据
            if income_statement is None or (isinstance(income_statement, pd.DataFrame) and income_statement.empty):
                try:
                    # 使用季度报表API
                    if has_ak_function('stock_profit_sheet_by_report_em'):
                        quarterly_is = ak.stock_profit_sheet_by_report_em(symbol=em_stock_code)
                        
                        # 检查数据是否为空
                        if quarterly_is is not None and not quarterly_is.empty:
                            # 筛选出年度报表
                            if 'REPORT_DATE' in quarterly_is.columns:
                                annual_is = quarterly_is[quarterly_is['REPORT_DATE'].str.endswith('1231', na=False)]
                                if not annual_is.empty:
                                    income_statement = annual_is
                                    st.success("使用季度报表筛选得到年度利润表成功")
                                else:
                                    st.warning("从季度数据中未能筛选出年度利润表数据")
                            else:
                                st.warning("季度利润表数据中没有REPORT_DATE列")
                        else:
                            st.warning("下载的季度利润表数据为空")
                except Exception as e:
                    st.warning(f"尝试从季度报表筛选年度利润表失败: {e}")
            
            # 如果上述都失败，尝试使用最基本的季度API，然后筛选
            if income_statement is None or (isinstance(income_statement, pd.DataFrame) and income_statement.empty):
                try:
                    if has_ak_function('stock_profit_sheet_by_quarterly_em'):
                        quarterly_is = ak.stock_profit_sheet_by_quarterly_em(symbol=em_stock_code)
                        
                        # 检查数据是否为空
                        if quarterly_is is not None and not quarterly_is.empty:
                            # 筛选出年度报表
                            if 'REPORT_DATE' in quarterly_is.columns:
                                annual_is = quarterly_is[quarterly_is['REPORT_DATE'].str.endswith('1231', na=False)]
                                if not annual_is.empty:
                                    income_statement = annual_is
                                    st.success("使用季度报表API筛选得到年度利润表成功")
                                else:
                                    st.warning("从季度API数据中未能筛选出年度利润表数据")
                            else:
                                st.warning("季度API利润表数据中没有REPORT_DATE列")
                        else:
                            st.warning("下载的季度API利润表数据为空")
                except Exception as e:
                    st.warning(f"尝试从季度API筛选年度利润表失败: {e}")
            
            # 尝试直接使用stock_financial_analysis_indicator函数
            if income_statement is None or (isinstance(income_statement, pd.DataFrame) and income_statement.empty):
                try:
                    if has_ak_function('stock_financial_analysis_indicator'):
                        indicators = ak.stock_financial_analysis_indicator(symbol=stock_code)
                        if indicators is not None and not indicators.empty:
                            st.warning("使用财务指标接口获取数据，可能不包含完整利润表信息")
                            # 尝试创建一个最小化的利润表
                            if '日期' in indicators.columns:
                                # 筛选年度数据
                                annual_indicators = indicators[indicators['日期'].str.endswith('12-31', na=False)]
                                if not annual_indicators.empty:
                                    # 创建一个基本的利润表DataFrame
                                    is_data = {
                                        'REPORT_DATE': annual_indicators['日期'].apply(lambda x: x.replace('-', '')),
                                        'OPERATING_REVENUE': annual_indicators.get('营业收入(元)', np.nan),
                                        'OPERATING_PROFIT': annual_indicators.get('营业利润(元)', np.nan),
                                        'NET_PROFIT': annual_indicators.get('净利润(元)', np.nan)
                                    }
                                    income_statement = pd.DataFrame(is_data)
                                    st.success("使用财务指标接口创建了基本利润表")
                        else:
                            st.warning("财务指标接口数据为空")
                except Exception as e:
                    st.warning(f"使用财务指标接口获取利润表数据失败: {e}")
                    
        except Exception as e:
            st.error(f"下载年度利润表时出错: {e}")
            income_statement = pd.DataFrame()
        
        # 尝试获取年度现金流量表
        try:
            cash_flow = None
            
            # 尝试使用年度报表的API
            if has_ak_function('stock_cash_flow_sheet_by_yearly_em'):
                try:
                    cash_flow = ak.stock_cash_flow_sheet_by_yearly_em(symbol=em_stock_code)
                    if cash_flow is not None and not cash_flow.empty:
                        st.success("使用 stock_cash_flow_sheet_by_yearly_em 下载年度现金流量表成功")
                    else:
                        st.warning(f"使用 stock_cash_flow_sheet_by_yearly_em 下载的现金流量表数据为空")
                except Exception as e:
                    st.warning(f"使用 stock_cash_flow_sheet_by_yearly_em 下载年度现金流量表失败: {e}")
            
            # 如果年度API失败，尝试使用季度API，然后筛选年度数据
            if cash_flow is None or (isinstance(cash_flow, pd.DataFrame) and cash_flow.empty):
                try:
                    # 使用季度报表API
                    if has_ak_function('stock_cash_flow_sheet_by_report_em'):
                        quarterly_cf = ak.stock_cash_flow_sheet_by_report_em(symbol=em_stock_code)
                        
                        # 检查数据是否为空
                        if quarterly_cf is not None and not quarterly_cf.empty:
                            # 筛选出年度报表
                            if 'REPORT_DATE' in quarterly_cf.columns:
                                annual_cf = quarterly_cf[quarterly_cf['REPORT_DATE'].str.endswith('1231', na=False)]
                                if not annual_cf.empty:
                                    cash_flow = annual_cf
                                    st.success("使用季度报表API筛选得到年度现金流量表成功")
                                else:
                                    st.warning("从季度数据中未能筛选出年度现金流量表数据")
                            else:
                                st.warning("季度现金流量表数据中没有REPORT_DATE列")
                        else:
                            st.warning("下载的季度现金流量表数据为空")
                except Exception as e:
                    st.warning(f"尝试从季度报表筛选年度现金流量表失败: {e}")
            
            # 如果上述都失败，尝试使用最基本的季度API，然后筛选
            if cash_flow is None or (isinstance(cash_flow, pd.DataFrame) and cash_flow.empty):
                try:
                    if has_ak_function('stock_cash_flow_sheet_by_quarterly_em'):
                        quarterly_cf = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=em_stock_code)
                        
                        # 检查数据是否为空
                        if quarterly_cf is not None and not quarterly_cf.empty:
                            # 筛选出年度报表
                            if 'REPORT_DATE' in quarterly_cf.columns:
                                annual_cf = quarterly_cf[quarterly_cf['REPORT_DATE'].str.endswith('1231', na=False)]
                                if not annual_cf.empty:
                                    cash_flow = annual_cf
                                    st.success("使用季度报表API筛选得到年度现金流量表成功")
                                else:
                                    st.warning("从季度API数据中未能筛选出年度现金流量表数据")
                            else:
                                st.warning("季度API现金流量表数据中没有REPORT_DATE列")
                        else:
                            st.warning("下载的季度API现金流量表数据为空")
                except Exception as e:
                    st.warning(f"尝试从季度API筛选年度现金流量表失败: {e}")
                    
            # 尝试直接使用stock_financial_analysis_indicator函数
            if cash_flow is None or (isinstance(cash_flow, pd.DataFrame) and cash_flow.empty):
                try:
                    if has_ak_function('stock_financial_analysis_indicator'):
                        indicators = ak.stock_financial_analysis_indicator(symbol=stock_code)
                        if indicators is not None and not indicators.empty:
                            st.warning("使用财务指标接口获取数据，可能不包含完整现金流量表信息")
                            # 尝试创建一个最小化的现金流量表
                            if '日期' in indicators.columns:
                                # 筛选年度数据
                                annual_indicators = indicators[indicators['日期'].str.endswith('12-31', na=False)]
                                if not annual_indicators.empty:
                                    # 创建一个基本的现金流量表DataFrame
                                    cf_data = {
                                        'REPORT_DATE': annual_indicators['日期'].apply(lambda x: x.replace('-', '')),
                                        'NET_OPERATE_CASH_FLOW': annual_indicators.get('经营活动产生的现金流量净额(元)', np.nan),
                                        'NET_INVEST_CASH_FLOW': annual_indicators.get('投资活动产生的现金流量净额(元)', np.nan),
                                        'NET_FINANCE_CASH_FLOW': annual_indicators.get('筹资活动产生的现金流量净额(元)', np.nan)
                                    }
                                    cash_flow = pd.DataFrame(cf_data)
                                    st.success("使用财务指标接口创建了基本现金流量表")
                        else:
                            st.warning("财务指标接口数据为空")
                except Exception as e:
                    st.warning(f"使用财务指标接口获取现金流量表数据失败: {e}")
                    
        except Exception as e:
            st.error(f"下载年度现金流量表时出错: {e}")
            cash_flow = pd.DataFrame()
        
        # 确保报表目录存在
        reports_dir = f"reports/{stock_code}"
        os.makedirs(reports_dir, exist_ok=True)
        
        # 检查是否至少有一个报表不为空
        has_valid_data = False
        
        # 保存资产负债表
        if balance_sheet is not None and isinstance(balance_sheet, pd.DataFrame) and not balance_sheet.empty:
            has_valid_data = True
            try:
                # 确保列名为字符串
                balance_sheet.columns = balance_sheet.columns.astype(str)
                
                # 确保REPORT_DATE列存在
                if "REPORT_DATE" in balance_sheet.columns:
                    # 保存原始数据
                    balance_sheet.to_csv(f"{reports_dir}/balance_sheet_raw.csv", index=False)
                    
                    # 设置REPORT_DATE为索引
                    balance_sheet_processed = balance_sheet.set_index("REPORT_DATE")
                    
                    # 转置数据使报告日期成为列
                    balance_sheet_processed = balance_sheet_processed.T
                    
                    # 保存处理后的数据
                    balance_sheet_processed.to_csv(f"{reports_dir}/balance_sheet.csv")
                    st.success(f"已保存年度资产负债表，共 {len(balance_sheet)} 行数据")
                else:
                    st.warning("资产负债表没有REPORT_DATE列，无法转换为正确格式")
                    # 尝试保存原始数据
                    balance_sheet.to_csv(f"{reports_dir}/balance_sheet_raw.csv", index=False)
                    st.info("已保存原始资产负债表数据，请手动检查格式")
            except Exception as e:
                st.error(f"处理资产负债表时出错: {e}")
                # 尝试保存原始数据作为备份
                try:
                    balance_sheet.to_csv(f"{reports_dir}/balance_sheet_raw.csv", index=False)
                    st.warning("保存了原始资产负债表数据，处理过程失败")
                except:
                    st.error("无法保存资产负债表数据")
        else:
            st.warning("获取的年度资产负债表为空或无效")
        
        # 保存利润表
        if income_statement is not None and isinstance(income_statement, pd.DataFrame) and not income_statement.empty:
            has_valid_data = True
            try:
                # 确保列名为字符串
                income_statement.columns = income_statement.columns.astype(str)
                
                # 确保REPORT_DATE列存在
                if "REPORT_DATE" in income_statement.columns:
                    # 保存原始数据
                    income_statement.to_csv(f"{reports_dir}/income_statement_raw.csv", index=False)
                    
                    # 设置REPORT_DATE为索引
                    income_statement_processed = income_statement.set_index("REPORT_DATE")
                    
                    # 转置数据使报告日期成为列
                    income_statement_processed = income_statement_processed.T
                    
                    # 保存处理后的数据
                    income_statement_processed.to_csv(f"{reports_dir}/income_statement.csv")
                    st.success(f"已保存年度利润表，共 {len(income_statement)} 行数据")
                else:
                    st.warning("利润表没有REPORT_DATE列，无法转换为正确格式")
                    # 尝试保存原始数据
                    income_statement.to_csv(f"{reports_dir}/income_statement_raw.csv", index=False)
                    st.info("已保存原始利润表数据，请手动检查格式")
            except Exception as e:
                st.error(f"处理利润表时出错: {e}")
                # 尝试保存原始数据作为备份
                try:
                    income_statement.to_csv(f"{reports_dir}/income_statement_raw.csv", index=False)
                    st.warning("保存了原始利润表数据，处理过程失败")
                except:
                    st.error("无法保存利润表数据")
        else:
            st.warning("获取的年度利润表为空或无效")
        
        # 保存现金流量表
        if cash_flow is not None and isinstance(cash_flow, pd.DataFrame) and not cash_flow.empty:
            has_valid_data = True
            try:
                # 确保列名为字符串
                cash_flow.columns = cash_flow.columns.astype(str)
                
                # 确保REPORT_DATE列存在
                if "REPORT_DATE" in cash_flow.columns:
                    # 保存原始数据
                    cash_flow.to_csv(f"{reports_dir}/cash_flow_raw.csv", index=False)
                    
                    # 设置REPORT_DATE为索引
                    cash_flow_processed = cash_flow.set_index("REPORT_DATE")
                    
                    # 转置数据使报告日期成为列
                    cash_flow_processed = cash_flow_processed.T
                    
                    # 保存处理后的数据
                    cash_flow_processed.to_csv(f"{reports_dir}/cash_flow.csv")
                    st.success(f"已保存年度现金流量表，共 {len(cash_flow)} 行数据")
                else:
                    st.warning("现金流量表没有REPORT_DATE列，无法转换为正确格式")
                    # 尝试保存原始数据
                    cash_flow.to_csv(f"{reports_dir}/cash_flow_raw.csv", index=False)
                    st.info("已保存原始现金流量表数据，请手动检查格式")
            except Exception as e:
                st.error(f"处理现金流量表时出错: {e}")
                # 尝试保存原始数据作为备份
                try:
                    cash_flow.to_csv(f"{reports_dir}/cash_flow_raw.csv", index=False)
                    st.warning("保存了原始现金流量表数据，处理过程失败")
                except:
                    st.error("无法保存现金流量表数据")
        else:
            st.warning("获取的年度现金流量表为空或无效")
        
        # 尝试从新浪财经API下载 - 作为备选方案
        if not has_valid_data:
            st.info("东方财富数据下载失败，尝试从新浪财经下载...")
            try:
                # 尝试从新浪财经API下载
                prefix = get_stock_prefix(stock_code)
                full_code = prefix + stock_code
                report_types = ["资产负债表", "利润表", "现金流量表"]
                
                for report_type in report_types:
                    try:
                        df = ak.stock_financial_report_sina(stock=full_code, symbol=report_type)
                        
                        # 检查数据是否为空
                        if df is not None and not df.empty:
                            # 根据报表类型生成不同的文件名
                            file_type = ""
                            if report_type == "资产负债表":
                                file_type = "balance_sheet"
                            elif report_type == "利润表":
                                file_type = "income_statement"
                            elif report_type == "现金流量表":
                                file_type = "cash_flow"
                            
                            # 保存文件
                            file_path = os.path.join(reports_dir, f"{file_type}.csv")
                            df.to_csv(file_path, encoding="utf-8-sig")
                            st.success(f"成功从新浪财经下载并保存 {report_type}")
                            has_valid_data = True
                    except Exception as e:
                        st.warning(f"从新浪财经下载 {report_type} 失败: {e}")
            except Exception as e:
                st.error(f"尝试从新浪财经下载数据出错: {e}")
        
        # 根据是否有有效数据返回结果
        if has_valid_data:
            st.success("财务报表下载完成！")
            return True
        else:
            st.error("所有下载方法都失败，无法获取财务报表数据")
            return False
            
    except Exception as e:
        st.error(f"下载年度财务报表时出错: {e}")
        return False

def app():
    """主应用程序函数"""
    # 设置页面标题
    st.title("股票财务分析工具")
    
    # 创建必要的目录
    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(chart_dir, exist_ok=True)
    
    # 侧边栏 - 输入区域
    with st.sidebar:
        st.header("输入参数")
        
        # 股票代码输入
        stock_code = st.text_input("输入股票代码", "600519")
        
        # 设置默认显示名称，可以在加载数据后更新
        stock_name = "未知"
        
        # 数据来源选择
        data_source = st.radio(
            "选择数据来源",
            ["新浪财经", "东方财富季度数据", "东方财富年度数据"]
        )
        
        # 调试模式开关
        debug_mode = st.checkbox("调试模式", value=False, help="显示详细的数据处理信息")
        
        # 提取财务数据按钮
        if st.button("下载财务报表"):
            # 检查输入的股票代码是否有效
            if not stock_code or not re.match(r'^\d{6}$', stock_code):
                st.error("请输入有效的6位股票代码")
                return
            
            try:
                # 根据选择的数据来源下载不同的财务报表
                with st.spinner(f"正在下载 {stock_code} 的财务报表..."):
                    if data_source == "新浪财经":
                        download_financial_reports(stock_code)
                    elif data_source == "东方财富季度数据":
                        download_financial_reports_em(stock_code)
                    else:  # 东方财富年度数据
                        download_annual_reports_em(stock_code)
                
                st.success(f"财务报表下载完成，已保存到 {download_dir}/{stock_code} 目录")
            except Exception as e:
                st.error(f"下载财务报表时出错: {e}")
                if debug_mode:
                    st.error(traceback.format_exc())
    
    # 主要内容区域
    st.header("财务分析结果")
    
    # 检查是否有输入股票代码
    if not stock_code:
        st.info("请在侧边栏输入股票代码并下载财务报表")
        return
    
    # 显示股票基本信息
    st.subheader(f"股票代码: {stock_code}")
    
    # 加载已下载的财务报表
    try:
        with st.spinner("加载财务报表..."):
            balance_sheet, income_statement = load_existing_reports(stock_code)
        
        if balance_sheet is None or income_statement is None:
            st.warning("未找到已下载的财务报表，请先点击'下载财务报表'按钮")
            return
        
        # 如果成功加载，提取股票名称
        try:
            # 尝试从资产负债表中提取股票名称
            try_name = balance_sheet.iloc[0, 0]
            # 检查是否是日期格式，如果是则不使用
            if isinstance(try_name, str) and "资产负债表" in try_name:
                stock_name = try_name.split("资产负债表")[0].strip()
            elif not isinstance(try_name, (datetime, pd.Timestamp)) and not re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', str(try_name)):
                stock_name = try_name
        except:
            try:
                try_name = balance_sheet.columns[0]
                if isinstance(try_name, str) and "资产负债表" in try_name:
                    stock_name = try_name.split("资产负债表")[0].strip()
                elif not isinstance(try_name, (datetime, pd.Timestamp)) and not re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', str(try_name)):
                    stock_name = try_name
            except:
                # 尝试通过API获取股票名称
                try:
                    stock_info = ak.stock_individual_info_em(symbol=stock_code)
                    if not stock_info.empty:
                        stock_name = stock_info.loc[0, "股票简称"]
                except:
                    stock_name = "未知公司"
                    if debug_mode:
                        st.warning("无法确定股票名称，使用默认值")
        
        # 检查股票名称是否看起来像日期
        if isinstance(stock_name, (datetime, pd.Timestamp)) or re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', str(stock_name)):
            # 如果名称是日期格式，则使用代码作为名称
            stock_name = f"股票 {stock_code}"
        
        # 更新标题显示股票名称
        if stock_name and stock_name != "未知":
            st.subheader(f"股票名称: {stock_name}")
        
        # 提取财务指标
        with st.spinner("提取财务指标..."):
            revenue, profit, dates = get_financial_metrics(income_statement, stock_code)
            
        # 始终显示原始数据，帮助用户理解数据结构
        with st.expander("查看原始财务数据"):
            st.subheader("资产负债表原始数据")
            st.dataframe(balance_sheet)
            
            st.subheader("利润表原始数据")
            st.dataframe(income_statement)
            
            # 显示数据结构信息
            st.subheader("数据结构信息")
            st.write(f"资产负债表形状: {balance_sheet.shape}")
            st.write(f"资产负债表列名: {balance_sheet.columns.tolist()}")
            st.write(f"利润表形状: {income_statement.shape}")
            st.write(f"利润表列名: {income_statement.columns.tolist()}")
            
            # 如果第一列存在，显示其内容
            if not income_statement.empty and len(income_statement.columns) > 0:
                first_col = income_statement.columns[0]
                st.write(f"利润表第一列内容 ({first_col}):")
                st.write(income_statement[first_col].tolist())
        
        # 如果成功提取财务指标，则绘制图表
        if revenue and profit and dates and len(revenue) > 0 and len(profit) > 0 and len(dates) > 0:
            with st.spinner("生成财务图表..."):
                growth_metrics = plot_financial_metrics(revenue, profit, dates, stock_code, stock_name)
                
            # 提取财务比率
            with st.spinner("计算财务比率..."):
                ratios_df = get_financial_ratios(balance_sheet, income_statement)
                
            if ratios_df is not None:
                st.subheader("财务比率分析")
                st.dataframe(ratios_df)
                
                # 绘制财务比率趋势图
                with st.spinner("生成财务比率趋势图..."):
                    plot_financial_ratios(ratios_df, stock_code, stock_name)
            else:
                st.warning("无法计算财务比率，请检查财务报表格式")
        else:
            st.warning("无法提取营业收入和净利润数据，请检查上面展示的利润表格式")
            
            # 添加一个辅助功能，尝试查找关键词
            st.subheader("数据分析辅助")
            keyword = st.text_input("输入关键词以在利润表中查找", "营业收入")
            
            if keyword and not income_statement.empty:
                try:
                    # 在所有列中查找关键词
                    for col in income_statement.columns:
                        matches = income_statement[income_statement[col].astype(str).str.contains(keyword, na=False)]
                        if not matches.empty:
                            st.success(f"在列 '{col}' 中找到了包含 '{keyword}' 的 {len(matches)} 行")
                            st.dataframe(matches)
                except Exception as e:
                    st.error(f"搜索时出错: {e}")
    except Exception as e:
        st.error(f"分析财务数据时出错: {e}")
        if debug_mode:
            st.error(traceback.format_exc())


if __name__ == "__main__":
    app()