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

# 设置matplotlib支持中文
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 定义数据目录
data_dir = "financial_data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

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
    """加载已存在的财务报表"""
    try:
        # 先尝试查找新浪财经的文件
        bs_files = glob.glob(os.path.join(data_dir, f"{stock_code}_balance_sheet_*.csv"))
        is_files = glob.glob(os.path.join(data_dir, f"{stock_code}_income_statement_*.csv"))
        cf_files = glob.glob(os.path.join(data_dir, f"{stock_code}_cash_flow_*.csv"))
        
        # 再查找东方财富的文件
        bs_files_em = glob.glob(os.path.join(data_dir, f"{stock_code}_balance_sheet_em_*.csv"))
        is_files_em = glob.glob(os.path.join(data_dir, f"{stock_code}_income_statement_em_*.csv"))
        cf_files_em = glob.glob(os.path.join(data_dir, f"{stock_code}_cash_flow_em_*.csv"))
        
        # 合并文件列表
        bs_files = bs_files + bs_files_em
        is_files = is_files + is_files_em
        cf_files = cf_files + cf_files_em
        
        # 检查是否存在所有三种报表
        if not bs_files or not is_files:  # 至少需要资产负债表和利润表
            return None, "未知"
        
        # 获取最新的文件
        bs_file = sorted(bs_files)[-1]
        is_file = sorted(is_files)[-1]
        
        # 读取数据
        balance_sheet = pd.read_csv(bs_file, encoding="utf-8-sig")
        income_statement = pd.read_csv(is_file, encoding="utf-8-sig")
        
        # 如果有现金流量表，也读取
        if cf_files:
            cf_file = sorted(cf_files)[-1]
            cash_flow = pd.read_csv(cf_file, encoding="utf-8-sig")
        else:
            cash_flow = pd.DataFrame()
        
        # 检查是否是东方财富格式的数据，如果是，需要转换
        is_em_format = False
        if '_em_' in bs_file or '_em_' in is_file:
            is_em_format = True
            st.info("检测到东方财富格式的数据文件，将进行格式转换")
            
            # 如果是东方财富的原始数据，需要转换
            if 'REPORT_DATE' in balance_sheet.columns or any('DATE' in col for col in balance_sheet.columns):
                balance_sheet = convert_em_to_sina_format(balance_sheet)
            
            if 'REPORT_DATE' in income_statement.columns or any('DATE' in col for col in income_statement.columns):
                income_statement = convert_em_to_sina_format(income_statement)
            
            if not cash_flow.empty and ('REPORT_DATE' in cash_flow.columns or any('DATE' in col for col in cash_flow.columns)):
                cash_flow = convert_em_to_sina_format(cash_flow)
        
        # 尝试获取股票名称
        try:
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            stock_name = stock_info.loc[0, "股票简称"] if not stock_info.empty else "未知"
        except:
            stock_name = "未知"
        
        report_data = {
            "资产负债表": balance_sheet,
            "利润表": income_statement
        }
        
        if not cash_flow.empty:
            report_data["现金流量表"] = cash_flow
            
        st.success(f"成功加载 {('东方财富' if is_em_format else '新浪财经')} 格式的财务数据")
        return report_data, stock_name
        
    except Exception as e:
        st.error(f"加载现有报表出错: {e}")
        return None, "未知"

def get_financial_metrics(income_statement):
    """从利润表中提取营业收入和净利润数据"""
    if income_statement is None or income_statement.empty:
        st.warning("利润表数据为空")
        return None, None
    
    # 打印利润表前5行供调试
    st.write("利润表结构预览:")
    st.dataframe(income_statement.head())
    st.write("列名:", income_statement.columns.tolist())
    
    # 检查数据结构，确定哪一列是项目名称
    first_col = income_statement.columns[0]
    st.write(f"第一列名称: {first_col}")
    
    # 检查第一列是否包含常见的财务项目关键词
    sample_values = income_statement.iloc[:10, 0].astype(str).tolist()
    st.write(f"第一列样本值: {sample_values}")
    
    has_financial_terms = any('收入' in s or '利润' in s or '成本' in s or '费用' in s for s in sample_values)
    
    if not has_financial_terms:
        st.warning("第一列可能不是项目名称列，尝试识别正确的项目列")
        
        # 尝试查找可能的项目列
        for i, col in enumerate(income_statement.columns):
            sample_values = income_statement[col].astype(str).tolist()[:10]
            if any('收入' in s or '利润' in s or '成本' in s or '费用' in s for s in sample_values):
                st.success(f"找到可能的项目列: {col}")
                
                # 重组数据，使项目列成为第一列
                new_cols = [col] + [c for c in income_statement.columns if c != col]
                income_statement = income_statement[new_cols]
                break
        
        # 如果仍未找到项目列，尝试转置数据
        if not has_financial_terms:
            st.warning("未找到明确的项目列，尝试转置数据")
            
            # 检查第一列是否是日期
            date_pattern = r'^\d{8}$|^\d{4}-\d{2}-\d{2}$'
            first_col_values = income_statement.iloc[:5, 0].astype(str).tolist()
            
            if all(re.match(date_pattern, str(val)) for val in first_col_values if str(val) not in ['nan', 'None']):
                st.info("检测到第一列可能是日期，进行数据转置")
                
                # 转置数据
                income_statement_indexed = income_statement.set_index(income_statement.columns[0])
                income_statement = income_statement_indexed.transpose().reset_index()
                income_statement.rename(columns={'index': '项目'}, inplace=True)
                
                st.write("转置后的数据结构:")
                st.dataframe(income_statement.head())
    
    # 获取日期列
    if len(income_statement.columns) <= 1:
        st.error("数据结构有问题，至少需要一个项目列和多个日期列")
        return None, None
        
    # 确保日期列是字符串类型
    dates = [str(date) for date in income_statement.columns[1:]]
    st.write(f"检测到的日期列: {', '.join(dates)}")
    st.write(f"总计 {len(dates)} 个日期")
    
    # 确保第一列是字符串类型，使用copy避免警告
    income_statement = income_statement.copy()
    
    # 检查第一列的数据类型
    st.write(f"第一列的数据类型: {income_statement.iloc[:, 0].dtype}")
    
    # 安全地转换为字符串
    try:
        # 首先转换为列表，然后再转换为字符串
        item_values = income_statement.iloc[:, 0].tolist()
        
        # 创建新的DataFrame而不是直接修改
        new_df = pd.DataFrame()
        new_df[income_statement.columns[0]] = [str(x) for x in item_values]
        
        # 复制其他列
        for col in income_statement.columns[1:]:
            new_df[col] = income_statement[col]
        
        income_statement = new_df
    except Exception as e:
        st.error(f"转换第一列为字符串时出错: {e}")
    
    # 打印第一列的所有值，帮助确定匹配关键词
    st.write("第一列的所有值:")
    st.write(income_statement.iloc[:, 0].tolist())
    
    # 使用更多的匹配模式来查找营业收入和净利润行
    revenue_patterns = ['营业收入', '营业总收入', '主营业务收入', '总收入', '收入总计', '营业额']
    profit_patterns = ['净利润', '归属于母公司股东的净利润', '归属于上市公司股东的净利润', '利润总额', '净利', '利润']
    
    # 使用"或"条件连接所有模式
    revenue_pattern = '|'.join(revenue_patterns)
    profit_pattern = '|'.join(profit_patterns)
    
    # 查找匹配行
    revenue_rows = income_statement[income_statement.iloc[:, 0].str.contains(revenue_pattern, na=False)]
    profit_rows = income_statement[income_statement.iloc[:, 0].str.contains(profit_pattern, na=False)]
    
    # 如果找不到匹配行，尝试更模糊的匹配
    if revenue_rows.empty:
        st.warning("未找到营业收入行，尝试更模糊的匹配")
        revenue_rows = income_statement[income_statement.iloc[:, 0].str.contains('收入', na=False)]
    
    if profit_rows.empty:
        st.warning("未找到净利润行，尝试更模糊的匹配")
        profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('利润', na=False)]
    
    # 仍然找不到，返回None
    if revenue_rows.empty or profit_rows.empty:
        st.error(f"无法在利润表中找到营业收入或净利润行。找到的营业收入行数: {len(revenue_rows)}，净利润行数: {len(profit_rows)}")
        # 显示找到的行以供参考
        if not revenue_rows.empty:
            st.write("找到的可能的营业收入行:")
            st.dataframe(revenue_rows)
        if not profit_rows.empty:
            st.write("找到的可能的净利润行:")
            st.dataframe(profit_rows)
        return None, None
    
    # 显示找到的行以确认
    st.success(f"找到了营业收入行 ({len(revenue_rows)}) 和净利润行 ({len(profit_rows)})")
    
    # 如果找到多行，取第一行
    revenue_row = revenue_rows.iloc[0]
    profit_row = profit_rows.iloc[0]
    
    st.write(f"使用的营业收入行: {revenue_row.iloc[0]}")
    st.write(f"使用的净利润行: {profit_row.iloc[0]}")
    
    # 提取数据
    revenue_data = {}
    profit_data = {}
    
    # 修复：使用列的原始名称，而不是转换后的日期列表
    col_dates = income_statement.columns[1:]
    
    for i, date in enumerate(col_dates):
        try:
            if i+1 < len(revenue_row) and pd.notna(revenue_row.iloc[i+1]) and revenue_row.iloc[i+1]:
                try:
                    # 尝试将值转换为浮点数
                    revenue_data[str(date)] = float(revenue_row.iloc[i+1])
                except (ValueError, TypeError):
                    st.warning(f"无法将营业收入值转换为数字: {revenue_row.iloc[i+1]} (日期: {date})")
            
            if i+1 < len(profit_row) and pd.notna(profit_row.iloc[i+1]) and profit_row.iloc[i+1]:
                try:
                    # 尝试将值转换为浮点数
                    profit_data[str(date)] = float(profit_row.iloc[i+1])
                except (ValueError, TypeError):
                    st.warning(f"无法将净利润值转换为数字: {profit_row.iloc[i+1]} (日期: {date})")
        except Exception as e:
            st.warning(f"处理日期 {date} 时出错: {e}")
    
    # 检查是否成功提取数据
    if not revenue_data or not profit_data:
        st.error("无法提取有效的财务数据")
        return None, None
    
    # 转换为DataFrame
    data = {
        '日期': [],
        '营业收入': [],
        '净利润': []
    }
    
    # 获取两者共有的日期
    common_dates = sorted(set(revenue_data.keys()) & set(profit_data.keys()), reverse=True)
    
    if not common_dates:
        st.error("没有找到营业收入和净利润共同的日期")
        return None, None
    
    # 取最近10年的数据（如果有）
    common_dates = common_dates[:min(10, len(common_dates))]
    st.write(f"将使用以下 {len(common_dates)} 个日期的数据: {', '.join(common_dates)}")
    
    for date in common_dates:
        data['日期'].append(date)
        data['营业收入'].append(revenue_data[date])
        data['净利润'].append(profit_data[date])
    
    # 创建DataFrame
    df = pd.DataFrame(data)
    
    # 显示提取的数据
    st.write("提取的财务数据:")
    st.dataframe(df)
    
    # 计算同比增长率
    try:
        df['营业收入_同比增长'] = [None] + [
            (df.loc[i, '营业收入'] / df.loc[i+1, '营业收入'] - 1) * 100 
            if df.loc[i+1, '营业收入'] != 0 else None 
            for i in range(len(df)-1)
        ]
        
        df['净利润_同比增长'] = [None] + [
            (df.loc[i, '净利润'] / df.loc[i+1, '净利润'] - 1) * 100 
            if df.loc[i+1, '净利润'] != 0 else None 
            for i in range(len(df)-1)
        ]
    except Exception as e:
        st.error(f"计算同比增长率时出错: {e}")
        # 即使计算增长率出错，仍然返回基础数据
    
    st.success("成功提取财务指标数据")
    return df, common_dates

def plot_financial_metrics(df, stock_code, stock_name):
    """绘制财务指标图表"""
    if df is None or df.empty or len(df) < 1:
        st.warning("没有足够的数据来绘制财务指标图表")
        return
    
    # 检查必要的列是否存在
    required_cols = ['日期', '营业收入', '净利润']
    if not all(col in df.columns for col in required_cols):
        st.warning(f"财务指标数据缺少必要的列：{', '.join([col for col in required_cols if col not in df.columns])}")
        return
    
    st.subheader("财务指标分析")
    
    # 显示基本财务指标数据
    st.write("#### 主要财务指标")
    
    # 格式化数据以便更好地显示
    display_df = df.copy()
    display_df['营业收入'] = display_df['营业收入'].apply(lambda x: f"{x/100000000:.2f} 亿元")
    display_df['净利润'] = display_df['净利润'].apply(lambda x: f"{x/100000000:.2f} 亿元")
    
    # 检查是否有同比增长率列
    if '营业收入_同比增长' in df.columns:
        display_df['营业收入_同比增长'] = display_df['营业收入_同比增长'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
    if '净利润_同比增长' in df.columns:
        display_df['净利润_同比增长'] = display_df['净利润_同比增长'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
    
    st.dataframe(display_df, hide_index=True)
    
    # 检查是否有足够的数据点绘制图表
    if len(df) < 2:
        st.warning("数据点太少，无法绘制有意义的趋势图")
        return
    
    # 创建图表
    st.write("#### 营业收入与净利润趋势")
    
    try:
        # 反转日期顺序以便按时间顺序显示
        df = df.iloc[::-1].reset_index(drop=True)
        dates = df['日期'].tolist()
        
        # 绘制营业收入和净利润趋势图
        fig, ax1 = plt.subplots(figsize=(12, 7))
        
        # 营业收入（左Y轴）
        revenue_data = df['营业收入'].values / 100000000  # 转换为亿元
        ax1.bar(dates, revenue_data, alpha=0.7, color='steelblue', label='营业收入')
        ax1.set_xlabel('报告期')
        ax1.set_ylabel('营业收入（亿元）', color='steelblue')
        ax1.tick_params(axis='y', labelcolor='steelblue')
        
        # 调整x轴标签的显示
        if len(dates) > 5:
            plt.xticks(rotation=90)  # 垂直显示日期
        else:
            plt.xticks(rotation=45)
        
        # 在柱子上显示数值（如果数据点不多于7个）
        if len(revenue_data) <= 7:
            for i, v in enumerate(revenue_data):
                ax1.text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=9)
        
        # 净利润（右Y轴）
        ax2 = ax1.twinx()
        profit_data = df['净利润'].values / 100000000  # 转换为亿元
        ax2.plot(dates, profit_data, color='red', marker='o', label='净利润')
        ax2.set_ylabel('净利润（亿元）', color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        
        # 在点上显示数值（如果数据点不多于7个）
        if len(profit_data) <= 7:
            for i, v in enumerate(profit_data):
                ax2.annotate(f'{v:.1f}', (i, v), xytext=(0, 5), textcoords='offset points', 
                            ha='center', va='bottom', fontsize=9, color='red')
        
        # 添加标题和网格
        plt.title(f'{stock_code} ({stock_name}) 营业收入与净利润趋势')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # 合并图例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        # 显示图表
        st.pyplot(fig)
        
        # 检查是否有同比增长率数据
        has_growth_data = '营业收入_同比增长' in df.columns and '净利润_同比增长' in df.columns
        
        if has_growth_data and len(df) >= 3:  # 至少需要3个数据点才能显示同比增长率
            # 绘制同比增长率趋势图
            st.write("#### 同比增长率趋势")
            
            fig, ax = plt.subplots(figsize=(12, 7))
            
            # 排除第一行（没有增长率数据）
            growth_df = df.iloc[1:].reset_index(drop=True)
            growth_dates = growth_df['日期'].tolist()
            
            # 检查是否有空值
            if growth_df['营业收入_同比增长'].notna().any() and growth_df['净利润_同比增长'].notna().any():
                revenue_growth = growth_df['营业收入_同比增长'].values
                profit_growth = growth_df['净利润_同比增长'].values
                
                ax.bar(growth_dates, revenue_growth, alpha=0.7, color='steelblue', label='营业收入同比增长率')
                ax.plot(growth_dates, profit_growth, color='red', marker='o', label='净利润同比增长率')
                
                # 调整x轴标签的显示
                if len(growth_dates) > 5:
                    plt.xticks(rotation=90)  # 垂直显示日期
                else:
                    plt.xticks(rotation=45)
                
                # 在柱子上显示数值（如果数据点不多于7个）
                if len(revenue_growth) <= 7:
                    for i, v in enumerate(revenue_growth):
                        if pd.notna(v):
                            ax.text(i, v, f'{v:.1f}%', ha='center', va='bottom' if v >= 0 else 'top', fontsize=9)
                
                # 在点上显示数值（如果数据点不多于7个）
                if len(profit_growth) <= 7:
                    for i, v in enumerate(profit_growth):
                        if pd.notna(v):
                            ax.annotate(f'{v:.1f}%', (i, v), xytext=(0, 5), textcoords='offset points', 
                                      ha='center', va='bottom' if v >= 0 else 'top', fontsize=9, color='red')
                
                # 添加标题和标签
                plt.title(f'{stock_code} ({stock_name}) 同比增长率趋势')
                plt.xlabel('报告期')
                plt.ylabel('同比增长率 (%)')
                plt.grid(True, alpha=0.3)
                plt.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
                plt.legend()
                plt.tight_layout()
                
                # 显示图表
                st.pyplot(fig)
            else:
                st.info("无法绘制同比增长率趋势图，因为数据中有空值")
        else:
            st.info("数据点太少，无法计算有意义的同比增长率")
            
    except Exception as e:
        st.error(f"绘制图表时出错: {e}")

def get_financial_ratios(balance_sheet, income_statement):
    """计算财务比率"""
    if balance_sheet is None or income_statement is None or balance_sheet.empty or income_statement.empty:
        st.warning("资产负债表或利润表数据为空")
        return None
    
    # 打印资产负债表前5行供调试
    st.write("资产负债表结构预览:")
    st.dataframe(balance_sheet.head())
    
    # 在处理之前，创建数据的深拷贝，避免修改原始数据
    balance_sheet = balance_sheet.copy(deep=True)
    income_statement = income_statement.copy(deep=True)
    
    # 确保所有列名都是字符串类型
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
    
    # 取最近10年的数据（如果有）
    common_dates = common_dates[:min(10, len(common_dates))]
    st.write(f"将使用以下 {len(common_dates)} 个日期的数据: {', '.join(common_dates)}")
    
    if not common_dates:
        st.error("资产负债表和利润表没有共同的日期")
        return None
    
    # 检查数据类型
    st.write(f"资产负债表第一列的数据类型: {balance_sheet.iloc[:, 0].dtype}")
    st.write(f"利润表第一列的数据类型: {income_statement.iloc[:, 0].dtype}")
    
    # 使用更安全的方式转换第一列为字符串类型
    try:
        # 创建新的DataFrame代替直接修改
        new_bs = pd.DataFrame()
        new_is = pd.DataFrame()
        
        # 第一列转换为字符串
        new_bs[balance_sheet.columns[0]] = balance_sheet.iloc[:, 0].astype(str)
        new_is[income_statement.columns[0]] = income_statement.iloc[:, 0].astype(str)
        
        # 复制其他列
        for col in balance_sheet.columns[1:]:
            new_bs[col] = balance_sheet[col]
        
        for col in income_statement.columns[1:]:
            new_is[col] = income_statement[col]
        
        balance_sheet = new_bs
        income_statement = new_is
        
    except Exception as e:
        st.error(f"转换列为字符串时出错: {e}")
        # 如果转换失败，尝试其他方法
        try:
            # 将整个DataFrame转换为字符串，然后再尝试提取数值
            st.warning("使用备用方法处理数据类型")
            
            # 打印一些样例值，帮助诊断
            st.write("资产负债表第一列样例值:")
            st.write(balance_sheet.iloc[:5, 0].tolist())
            
            st.write("利润表第一列样例值:")
            st.write(income_statement.iloc[:5, 0].tolist())
        except Exception as e2:
            st.error(f"备用方法也失败: {e2}")
    
    # 打印第一列的所有值，帮助确定匹配关键词
    st.write("资产负债表第一列的所有值:")
    st.write(balance_sheet.iloc[:, 0].tolist())
    
    # 使用更多的匹配模式
    asset_patterns = ['总资产', '资产总计', '资产总额', '资产负债表', '资产合计']
    equity_patterns = ['所有者权益', '股东权益', '净资产', '所有者权益合计', '股东权益合计', '权益合计']
    profit_patterns = ['净利润', '归属于母公司股东的净利润', '归属于上市公司股东的净利润', '利润总额', '净利', '利润', '净利润(含少数股东损益)']
    
    # 使用"或"条件连接所有模式
    asset_pattern = '|'.join(asset_patterns)
    equity_pattern = '|'.join(equity_patterns)
    profit_pattern = '|'.join(profit_patterns)
    
    # 查找资产负债表中的总资产和净资产行
    try:
        asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains(asset_pattern, na=False)]
    except Exception as e:
        st.error(f"查找总资产行时出错: {e}")
        asset_rows = pd.DataFrame()  # 创建空DataFrame
    
    try:
        equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains(equity_pattern, na=False)]
    except Exception as e:
        st.error(f"查找净资产行时出错: {e}")
        equity_rows = pd.DataFrame()
    
    # 如果找不到匹配行，尝试更模糊的匹配
    if asset_rows.empty:
        st.warning("未找到总资产行，尝试更模糊的匹配")
        try:
            asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('资产', na=False)]
        except Exception as e:
            st.error(f"模糊匹配总资产行时出错: {e}")
    
    if equity_rows.empty:
        st.warning("未找到净资产行，尝试更模糊的匹配")
        try:
            equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('权益', na=False)]
        except Exception as e:
            st.error(f"模糊匹配净资产行时出错: {e}")
    
    # 查找利润表中的净利润行
    try:
        profit_rows = income_statement[income_statement.iloc[:, 0].str.contains(profit_pattern, na=False)]
    except Exception as e:
        st.error(f"查找净利润行时出错: {e}")
        profit_rows = pd.DataFrame()
    
    if profit_rows.empty:
        st.warning("未找到净利润行，尝试更模糊的匹配")
        try:
            profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('利润', na=False)]
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
        st.warning("没有足够的数据来计算财务比率")
        return
    
    # 检查必要的列是否存在
    required_cols = ['日期', '总资产(亿元)', '净资产(亿元)', '净利润(亿元)', 'ROA(%)', 'ROE(%)']
    if not all(col in ratio_df.columns for col in required_cols):
        st.warning(f"财务比率数据缺少必要的列：{', '.join([col for col in required_cols if col not in ratio_df.columns])}")
        return
    
    st.subheader("财务比率分析")
    
    # 显示财务比率数据
    st.write("#### 财务比率")
    
    # 格式化数据
    display_df = ratio_df.copy()
    for col in ['总资产(亿元)', '净资产(亿元)', '净利润(亿元)']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}")
    
    for col in ['ROA(%)', 'ROE(%)']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
    
    st.dataframe(display_df, hide_index=True)
    
    # 检查是否有足够的数据点绘制图表
    if len(ratio_df) < 2:
        st.warning("数据点太少，无法绘制有意义的趋势图")
        return
    
    try:
        # 反转日期顺序以便按时间顺序显示
        ratio_df = ratio_df.iloc[::-1].reset_index(drop=True)
        dates = ratio_df['日期'].tolist()
        
        # 检查ROA和ROE是否有有效数据
        has_roa_data = ratio_df['ROA(%)'].notna().any()
        has_roe_data = ratio_df['ROE(%)'].notna().any()
        
        if has_roa_data or has_roe_data:
            # 绘制ROA和ROE趋势图
            st.write("#### ROA与ROE趋势")
            
            fig, ax = plt.subplots(figsize=(12, 7))
            
            roa_data = ratio_df['ROA(%)'].values
            roe_data = ratio_df['ROE(%)'].values
            
            if has_roa_data:
                ax.plot(dates, roa_data, color='blue', marker='o', label='ROA(%)')
            
            if has_roe_data:
                ax.plot(dates, roe_data, color='green', marker='s', label='ROE(%)')
            
            # 调整x轴标签的显示
            if len(dates) > 5:
                plt.xticks(rotation=90)  # 垂直显示日期
            else:
                plt.xticks(rotation=45)
            
            # 显示数值（如果数据点不多于7个）
            if len(roa_data) <= 7 and has_roa_data:
                for i, v in enumerate(roa_data):
                    if pd.notna(v):
                        ax.annotate(f'{v:.1f}%', (i, v), xytext=(0, 5), textcoords='offset points', 
                                  ha='center', va='bottom', fontsize=9, color='blue')
            
            if len(roe_data) <= 7 and has_roe_data:
                for i, v in enumerate(roe_data):
                    if pd.notna(v):
                        ax.annotate(f'{v:.1f}%', (i, v), xytext=(0, -15), textcoords='offset points', 
                                  ha='center', va='bottom', fontsize=9, color='green')
            
            # 添加标题和标签
            plt.title(f'{stock_code} ({stock_name}) ROA与ROE趋势')
            plt.xlabel('报告期')
            plt.ylabel('百分比 (%)')
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.tight_layout()
            
            # 显示图表
            st.pyplot(fig)
        else:
            st.info("无法绘制ROA与ROE趋势图，因为没有有效数据")
        
        # 检查是否有资产和净利润数据
        has_asset_data = ratio_df['总资产(亿元)'].notna().any() and ratio_df['净资产(亿元)'].notna().any()
        has_profit_data = ratio_df['净利润(亿元)'].notna().any()
        
        if has_asset_data or has_profit_data:
            # 绘制资产和净利润趋势图
            st.write("#### 资产与净利润趋势")
            
            fig, ax1 = plt.subplots(figsize=(12, 7))
            
            # 总资产和净资产（左Y轴）
            if has_asset_data:
                total_asset_data = ratio_df['总资产(亿元)'].values
                net_equity_data = ratio_df['净资产(亿元)'].values
                
                ax1.bar(dates, total_asset_data, alpha=0.6, color='lightblue', label='总资产(亿元)')
                ax1.bar(dates, net_equity_data, alpha=0.7, color='darkblue', label='净资产(亿元)')
                
                ax1.set_xlabel('报告期')
                ax1.set_ylabel('资产(亿元)', color='blue')
                ax1.tick_params(axis='y', labelcolor='blue')
            
            # 调整x轴标签的显示
            if len(dates) > 5:
                plt.xticks(rotation=90)  # 垂直显示日期
            else:
                plt.xticks(rotation=45)
            
            # 净利润（右Y轴）如果有数据
            if has_profit_data:
                ax2 = ax1.twinx()
                net_profit_data = ratio_df['净利润(亿元)'].values
                ax2.plot(dates, net_profit_data, color='red', marker='o', linewidth=2, label='净利润(亿元)')
                ax2.set_ylabel('净利润(亿元)', color='red')
                ax2.tick_params(axis='y', labelcolor='red')
            
            # 添加标题和网格
            plt.title(f'{stock_code} ({stock_name}) 资产与净利润趋势')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # 合并图例
            if has_asset_data and has_profit_data:
                lines1, labels1 = ax1.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            elif has_asset_data:
                ax1.legend(loc='upper left')
            elif has_profit_data:
                ax2.legend(loc='upper left')
            
            # 显示图表
            st.pyplot(fig)
        else:
            st.info("无法绘制资产与净利润趋势图，因为没有有效数据")
        
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
    """尝试从东方财富网下载年度报告数据"""
    # 显示下载进度
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 获取股票名称
        try:
            status_text.text("正在获取股票信息...")
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            stock_name = stock_info.loc[0, "股票简称"] if not stock_info.empty else "未知"
        except Exception as e:
            st.warning(f"无法获取股票名称: {e}")
            stock_name = "未知"
        
        progress_bar.progress(10)
        status_text.text(f"开始从东方财富下载 {stock_code}({stock_name}) 的年度财务报表...")
        
        # 检查AKShare版本
        try:
            import akshare
            ak_version = akshare.__version__
            st.info(f"当前AKShare版本: {ak_version}")
        except:
            st.warning("无法获取AKShare版本信息")
            ak_version = "未知"
        
        try:
            # 尝试使用不同的API获取年度财务数据
            st.info("尝试获取年度财务数据...")
            
            # 1. 尝试使用stock_financial_report_sina获取资产负债表
            status_text.text(f"正在下载 {stock_name}({stock_code}) 的资产负债表...")
            prefix = get_stock_prefix(stock_code)
            full_code = prefix + stock_code
            
            try:
                balance_sheet = ak.stock_financial_report_sina(stock=full_code, symbol="资产负债表")
                if balance_sheet is None or balance_sheet.empty:
                    st.warning("未能从新浪获取资产负债表，尝试其他方法")
                    balance_sheet = None
                else:
                    st.success("成功从新浪获取资产负债表")
            except Exception as e:
                st.warning(f"从新浪获取资产负债表失败: {e}")
                balance_sheet = None
            
            # 如果新浪API失败，尝试使用东方财富API
            if balance_sheet is None:
                try:
                    # 尝试使用stock_balance_sheet_by_yearly_em获取年报资产负债表
                    st.info("尝试使用stock_balance_sheet_by_yearly_em方法")
                    # 查看ak中是否有这个函数
                    if hasattr(ak, 'stock_balance_sheet_by_yearly_em'):
                        balance_sheet = ak.stock_balance_sheet_by_yearly_em(symbol=stock_code)
                    else:
                        st.warning("AKShare库中没有stock_balance_sheet_by_yearly_em函数")
                        # 尝试使用季度报表替代
                        st.info("尝试使用季度报表数据替代")
                        balance_sheet = ak.stock_balance_sheet_by_report_em(symbol=stock_code)
                    
                    if balance_sheet is None or balance_sheet.empty:
                        st.warning("未能从东方财富获取资产负债表")
                        balance_sheet = None
                except Exception as e:
                    st.warning(f"从东方财富获取资产负债表失败: {e}")
                    balance_sheet = None
            
            progress_bar.progress(40)
            if balance_sheet is not None and not balance_sheet.empty:
                st.success("成功获取资产负债表数据")
                st.write("资产负债表预览:")
                st.dataframe(balance_sheet.head())
            
            # 2. 尝试获取利润表
            status_text.text(f"正在下载 {stock_name}({stock_code}) 的利润表...")
            try:
                income_statement = ak.stock_financial_report_sina(stock=full_code, symbol="利润表")
                if income_statement is None or income_statement.empty:
                    st.warning("未能从新浪获取利润表，尝试其他方法")
                    income_statement = None
                else:
                    st.success("成功从新浪获取利润表")
            except Exception as e:
                st.warning(f"从新浪获取利润表失败: {e}")
                income_statement = None
            
            # 如果新浪API失败，尝试使用东方财富API
            if income_statement is None:
                try:
                    # 尝试使用stock_profit_sheet_by_yearly_em获取年报利润表
                    st.info("尝试使用stock_profit_sheet_by_yearly_em方法")
                    # 查看ak中是否有这个函数
                    if hasattr(ak, 'stock_profit_sheet_by_yearly_em'):
                        income_statement = ak.stock_profit_sheet_by_yearly_em(symbol=stock_code)
                    else:
                        st.warning("AKShare库中没有stock_profit_sheet_by_yearly_em函数")
                        # 尝试使用季度报表替代
                        st.info("尝试使用季度报表数据替代")
                        income_statement = ak.stock_profit_sheet_by_report_em(symbol=stock_code)
                    
                    if income_statement is None or income_statement.empty:
                        st.warning("未能从东方财富获取利润表")
                        income_statement = None
                except Exception as e:
                    st.warning(f"从东方财富获取利润表失败: {e}")
                    income_statement = None
            
            progress_bar.progress(70)
            if income_statement is not None and not income_statement.empty:
                st.success("成功获取利润表数据")
                st.write("利润表预览:")
                st.dataframe(income_statement.head())
            
            # 3. 尝试获取现金流量表
            status_text.text(f"正在下载 {stock_name}({stock_code}) 的现金流量表...")
            try:
                cash_flow = ak.stock_financial_report_sina(stock=full_code, symbol="现金流量表")
                if cash_flow is None or cash_flow.empty:
                    st.warning("未能从新浪获取现金流量表，尝试其他方法")
                    cash_flow = None
                else:
                    st.success("成功从新浪获取现金流量表")
            except Exception as e:
                st.warning(f"从新浪获取现金流量表失败: {e}")
                cash_flow = None
            
            # 如果新浪API失败，尝试使用东方财富API
            if cash_flow is None:
                try:
                    # 尝试使用stock_cash_flow_sheet_by_yearly_em获取年报现金流量表
                    st.info("尝试使用stock_cash_flow_sheet_by_yearly_em方法")
                    # 查看ak中是否有这个函数
                    if hasattr(ak, 'stock_cash_flow_sheet_by_yearly_em'):
                        cash_flow = ak.stock_cash_flow_sheet_by_yearly_em(symbol=stock_code)
                    else:
                        st.warning("AKShare库中没有stock_cash_flow_sheet_by_yearly_em函数")
                        # 尝试使用季度报表替代
                        st.info("尝试使用季度报表数据替代")
                        cash_flow = ak.stock_cash_flow_sheet_by_report_em(symbol=stock_code)
                    
                    if cash_flow is None or cash_flow.empty:
                        st.warning("未能从东方财富获取现金流量表")
                        cash_flow = None
                except Exception as e:
                    st.warning(f"从东方财富获取现金流量表失败: {e}")
                    cash_flow = None
            
            progress_bar.progress(90)
            if cash_flow is not None and not cash_flow.empty:
                st.success("成功获取现金流量表数据")
                st.write("现金流量表预览:")
                st.dataframe(cash_flow.head())
            
            # 4. 处理和保存数据
            successful_downloads = 0
            report_data = {}
            
            # 过滤数据，只保留年度报表数据（如果是从季度数据中提取）
            # 通常年报日期格式为YYYYMMDD，且月日为1231，即年末日期
            if balance_sheet is not None and not balance_sheet.empty:
                # 保存原始数据
                file_path = os.path.join(data_dir, f"{stock_code}_balance_sheet_annual_{current_date}.csv")
                balance_sheet.to_csv(file_path, index=False, encoding="utf-8-sig")
                
                # 检查数据格式，如果是东方财富的格式，需要转换
                if 'REPORT_DATE' in balance_sheet.columns or any('DATE' in col for col in balance_sheet.columns):
                    bs_converted = convert_em_to_sina_format(balance_sheet)
                    # 尝试筛选年报数据
                    date_cols = bs_converted.columns[1:]  # 第一列是项目名
                    # 只保留年末日期（通常是YYYYMMDD格式，且MM=12, DD=31）
                    annual_cols = [col for col in date_cols if col.endswith('1231') or col.endswith('12-31')]
                    if annual_cols:
                        st.info(f"筛选出 {len(annual_cols)} 个年报日期")
                        # 构建新的DataFrame，只包含项目列和年报列
                        bs_annual = bs_converted[[bs_converted.columns[0]] + annual_cols]
                        report_data["资产负债表"] = bs_annual
                    else:
                        # 如果没有找到年报日期，使用原数据
                        report_data["资产负债表"] = bs_converted
                else:
                    # 可能已经是新浪格式，直接使用
                    report_data["资产负债表"] = balance_sheet
                
                successful_downloads += 1
            
            if income_statement is not None and not income_statement.empty:
                # 保存原始数据
                file_path = os.path.join(data_dir, f"{stock_code}_income_statement_annual_{current_date}.csv")
                income_statement.to_csv(file_path, index=False, encoding="utf-8-sig")
                
                # 检查数据格式，如果是东方财富的格式，需要转换
                if 'REPORT_DATE' in income_statement.columns or any('DATE' in col for col in income_statement.columns):
                    is_converted = convert_em_to_sina_format(income_statement)
                    # 尝试筛选年报数据
                    date_cols = is_converted.columns[1:]  # 第一列是项目名
                    # 只保留年末日期
                    annual_cols = [col for col in date_cols if col.endswith('1231') or col.endswith('12-31')]
                    if annual_cols:
                        st.info(f"筛选出 {len(annual_cols)} 个年报日期")
                        # 构建新的DataFrame，只包含项目列和年报列
                        is_annual = is_converted[[is_converted.columns[0]] + annual_cols]
                        report_data["利润表"] = is_annual
                    else:
                        # 如果没有找到年报日期，使用原数据
                        report_data["利润表"] = is_converted
                else:
                    # 可能已经是新浪格式，直接使用
                    report_data["利润表"] = income_statement
                
                successful_downloads += 1
            
            if cash_flow is not None and not cash_flow.empty:
                # 保存原始数据
                file_path = os.path.join(data_dir, f"{stock_code}_cash_flow_annual_{current_date}.csv")
                cash_flow.to_csv(file_path, index=False, encoding="utf-8-sig")
                
                # 检查数据格式，如果是东方财富的格式，需要转换
                if 'REPORT_DATE' in cash_flow.columns or any('DATE' in col for col in cash_flow.columns):
                    cf_converted = convert_em_to_sina_format(cash_flow)
                    # 尝试筛选年报数据
                    date_cols = cf_converted.columns[1:]  # 第一列是项目名
                    # 只保留年末日期
                    annual_cols = [col for col in date_cols if col.endswith('1231') or col.endswith('12-31')]
                    if annual_cols:
                        st.info(f"筛选出 {len(annual_cols)} 个年报日期")
                        # 构建新的DataFrame，只包含项目列和年报列
                        cf_annual = cf_converted[[cf_converted.columns[0]] + annual_cols]
                        report_data["现金流量表"] = cf_annual
                    else:
                        # 如果没有找到年报日期，使用原数据
                        report_data["现金流量表"] = cf_converted
                else:
                    # 可能已经是新浪格式，直接使用
                    report_data["现金流量表"] = cash_flow
                
                successful_downloads += 1
            
            if successful_downloads > 0:
                status_text.text("下载完成！")
                progress_bar.progress(100)
                time.sleep(1)
                progress_bar.empty()
                status_text.empty()
                st.success(f"成功下载了 {stock_code}({stock_name}) 的 {successful_downloads} 个财务报表")
                st.info("注意：已尝试筛选出年度报表数据进行分析")
                return report_data, stock_name
            else:
                progress_bar.empty()
                status_text.empty()
                st.error("未能成功下载任何财务报表")
                st.warning("建议尝试以下解决方案：")
                st.markdown("""
                1. 使用"新浪财经 (基础数据)"或"东方财富 (季度数据)"数据源
                2. 检查股票代码是否正确
                3. 更新AKShare库：`pip install --upgrade akshare`
                4. 查看AKShare文档了解最新API：https://www.akshare.xyz/
                """)
                return None, stock_name
        
        except Exception as e:
            st.error(f"下载年度报表时出错: {e}")
            progress_bar.empty()
            status_text.empty()
            return None, stock_name
            
    except Exception as e:
        status_text.empty()
        progress_bar.empty()
        st.error(f"程序执行出错: {e}")
        return None, "未知"

def app():
    st.set_page_config(
        page_title="股票财务分析工具",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("股票财务报表分析工具")
    st.markdown("该应用从AKShare获取股票财务报表数据，并提供财务分析和可视化。")
    
    with st.sidebar:
        st.header("股票信息")
        stock_code = st.text_input("输入股票代码（如：000001或600000）")
        
        # 添加数据源选择
        data_source = st.radio(
            "选择数据源",
            ["新浪财经 (基础数据)", "东方财富 (季度数据)", "东方财富 (年度数据)"],
            index=0,
            help="新浪财经提供基本财务数据；东方财富季度数据更详细但格式可能不同；东方财富年度数据更全面"
        )
        
        # 添加调试模式选项
        debug_mode = st.checkbox("调试模式", value=False, help="开启以显示详细的数据处理过程和调试信息")
        
        if stock_code:
            download_btn = st.button("下载财务数据")
            analyze_btn = st.button("分析现有数据")
        
    if stock_code:
        # 当用户点击下载按钮时
        if download_btn:
            # 根据用户选择的数据源下载数据
            if data_source == "新浪财经 (基础数据)":
                report_data, stock_name = download_financial_reports(stock_code)
            elif data_source == "东方财富 (季度数据)":
                report_data, stock_name = download_financial_reports_em(stock_code)
            else:  # 东方财富年报
                report_data, stock_name = download_annual_reports_em(stock_code)
            
            if report_data:
                # 自动进行分析
                with st.spinner("正在分析财务数据..."):
                    # 创建一个新的容器用于显示调试信息
                    debug_container = st.container()
                    
                    # 提取基础财务指标数据
                    with st.expander("数据处理详情", expanded=debug_mode):
                        metrics_df = None
                        ratio_df = None
                        
                        # 检查利润表是否存在
                        if "利润表" in report_data and not report_data["利润表"].empty:
                            metrics_df, _ = get_financial_metrics(report_data["利润表"])
                        else:
                            st.warning("未找到有效的利润表数据，无法提取财务指标")
                    
                    # 有财务指标数据时绘制图表
                    if metrics_df is not None and not metrics_df.empty:
                        st.success("成功提取财务指标数据，生成图表")
                        plot_financial_metrics(metrics_df, stock_code, stock_name)
                    
                    # 计算并绘制财务比率（需要资产负债表和利润表）
                    if "资产负债表" in report_data and not report_data["资产负债表"].empty and "利润表" in report_data and not report_data["利润表"].empty:
                        with st.expander("财务比率计算详情", expanded=debug_mode):
                            ratio_df = get_financial_ratios(report_data["资产负债表"], report_data["利润表"])
                        
                        if ratio_df is not None and not ratio_df.empty:
                            st.success("成功提取财务比率数据，生成图表")
                            plot_financial_ratios(ratio_df, stock_code, stock_name)
                        else:
                            st.warning("计算财务比率失败，可能是由于数据格式不兼容")
                    else:
                        st.warning("缺少资产负债表或利润表数据，无法计算财务比率")
                    
                    # 如果两种图表都没有生成，给出总体提示
                    if (metrics_df is None or metrics_df.empty) and (ratio_df is None or ratio_df.empty):
                        st.error("无法提取足够的财务数据进行分析，请尝试其他数据源或开启调试模式查看详细信息")
                    elif metrics_df is None or metrics_df.empty:
                        st.info("提示：尽管无法提取基础财务指标，但仍成功生成了财务比率图表")
                    elif ratio_df is None or ratio_df.empty:
                        st.info("提示：尽管无法计算财务比率，但仍成功生成了基础财务指标图表")
            
        # 当用户点击分析按钮时
        elif analyze_btn:
            # 查找是否有现有数据
            report_data, stock_name = load_existing_reports(stock_code)
            
            if report_data:
                st.success(f"已加载 {stock_code} ({stock_name}) 的财务数据")
                
                with st.spinner("正在分析财务数据..."):
                    # 提取基础财务指标数据
                    with st.expander("数据处理详情", expanded=debug_mode):
                        metrics_df = None
                        ratio_df = None
                        
                        # 检查利润表是否存在
                        if "利润表" in report_data and not report_data["利润表"].empty:
                            metrics_df, _ = get_financial_metrics(report_data["利润表"])
                        else:
                            st.warning("未找到有效的利润表数据，无法提取财务指标")
                    
                    # 有财务指标数据时绘制图表
                    if metrics_df is not None and not metrics_df.empty:
                        st.success("成功提取财务指标数据，生成图表")
                        plot_financial_metrics(metrics_df, stock_code, stock_name)
                    
                    # 计算并绘制财务比率（需要资产负债表和利润表）
                    if "资产负债表" in report_data and not report_data["资产负债表"].empty and "利润表" in report_data and not report_data["利润表"].empty:
                        with st.expander("财务比率计算详情", expanded=debug_mode):
                            ratio_df = get_financial_ratios(report_data["资产负债表"], report_data["利润表"])
                        
                        if ratio_df is not None and not ratio_df.empty:
                            st.success("成功提取财务比率数据，生成图表")
                            plot_financial_ratios(ratio_df, stock_code, stock_name)
                        else:
                            st.warning("计算财务比率失败，可能是由于数据格式不兼容")
                    else:
                        st.warning("缺少资产负债表或利润表数据，无法计算财务比率")
                    
                    # 如果两种图表都没有生成，给出总体提示
                    if (metrics_df is None or metrics_df.empty) and (ratio_df is None or ratio_df.empty):
                        st.error("无法提取足够的财务数据进行分析，请尝试其他数据源或开启调试模式查看详细信息")
                    elif metrics_df is None or metrics_df.empty:
                        st.info("提示：尽管无法提取基础财务指标，但仍成功生成了财务比率图表")
                    elif ratio_df is None or ratio_df.empty:
                        st.info("提示：尽管无法计算财务比率，但仍成功生成了基础财务指标图表")
            else:
                st.warning(f"未找到 {stock_code} 的现有财务数据，请先下载")
    
    # AKShare版本信息
    with st.sidebar:
        st.markdown("---")
        try:
            import akshare
            st.info(f"AKShare版本: {akshare.__version__}")
        except:
            st.warning("无法获取AKShare版本信息")
    
    # 页脚信息
    st.markdown("---")
    st.markdown("**注意:** 本应用数据来源于AKShare，仅供参考，不构成投资建议。")
    st.markdown("数据源: 新浪财经和东方财富")

if __name__ == "__main__":
    app() 