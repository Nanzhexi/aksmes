import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import akshare as ak
import os
import time
import numpy as np
from datetime import datetime
import glob

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
        bs_files = glob.glob(os.path.join(data_dir, f"{stock_code}_balance_sheet_*.csv"))
        is_files = glob.glob(os.path.join(data_dir, f"{stock_code}_income_statement_*.csv"))
        cf_files = glob.glob(os.path.join(data_dir, f"{stock_code}_cash_flow_*.csv"))
        
        # 检查是否存在所有三种报表
        if not bs_files or not is_files or not cf_files:
            return None
        
        # 获取最新的文件
        bs_file = sorted(bs_files)[-1]
        is_file = sorted(is_files)[-1]
        cf_file = sorted(cf_files)[-1]
        
        # 读取数据
        balance_sheet = pd.read_csv(bs_file, encoding="utf-8-sig")
        income_statement = pd.read_csv(is_file, encoding="utf-8-sig")
        cash_flow = pd.read_csv(cf_file, encoding="utf-8-sig")
        
        # 尝试获取股票名称
        try:
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            stock_name = stock_info.loc[0, "股票简称"] if not stock_info.empty else "未知"
        except:
            stock_name = "未知"
        
        report_data = {
            "资产负债表": balance_sheet,
            "利润表": income_statement,
            "现金流量表": cash_flow
        }
        
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
    
    # 检查第一列的名称
    first_col_name = income_statement.columns[0]
    st.write(f"第一列名称: {first_col_name}")
    
    # 获取日期列
    dates = income_statement.columns[1:]
    st.write(f"检测到的日期列: {', '.join(dates)}")
    
    # 确保第一列是字符串类型，使用copy避免警告
    income_statement = income_statement.copy()
    income_statement.iloc[:, 0] = income_statement.iloc[:, 0].astype(str)
    
    # 打印第一列的所有值，帮助确定匹配关键词
    st.write("第一列的所有值:")
    st.write(income_statement.iloc[:, 0].tolist())
    
    # 使用更多的匹配模式来查找营业收入和净利润行
    revenue_patterns = ['营业收入', '营业总收入', '主营业务收入', '总收入', '收入总计']
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
    
    for i, date in enumerate(dates):
        if i+1 < len(revenue_row) and pd.notna(revenue_row.iloc[i+1]) and revenue_row.iloc[i+1]:
            try:
                # 尝试将值转换为浮点数
                revenue_data[date] = float(revenue_row.iloc[i+1])
            except (ValueError, TypeError):
                st.warning(f"无法将营业收入值转换为数字: {revenue_row.iloc[i+1]} (日期: {date})")
        
        if i+1 < len(profit_row) and pd.notna(profit_row.iloc[i+1]) and profit_row.iloc[i+1]:
            try:
                # 尝试将值转换为浮点数
                profit_data[date] = float(profit_row.iloc[i+1])
            except (ValueError, TypeError):
                st.warning(f"无法将净利润值转换为数字: {profit_row.iloc[i+1]} (日期: {date})")
    
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
    
    # 取最近5年的数据（如果有）
    common_dates = common_dates[:min(5, len(common_dates))]
    
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
    if df is None or df.empty:
        st.warning("没有足够的数据来绘制图表")
        return
    
    st.subheader("财务指标分析")
    
    # 显示基本财务指标数据
    st.write("#### 近五年主要财务指标")
    
    # 格式化数据以便更好地显示
    display_df = df.copy()
    display_df['营业收入'] = display_df['营业收入'].apply(lambda x: f"{x/100000000:.2f} 亿元")
    display_df['净利润'] = display_df['净利润'].apply(lambda x: f"{x/100000000:.2f} 亿元")
    display_df['营业收入_同比增长'] = display_df['营业收入_同比增长'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
    display_df['净利润_同比增长'] = display_df['净利润_同比增长'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
    
    st.dataframe(display_df, hide_index=True)
    
    # 创建图表
    st.write("#### 营业收入与净利润趋势")
    
    # 反转日期顺序以便按时间顺序显示
    df = df.iloc[::-1].reset_index(drop=True)
    dates = df['日期'].tolist()
    
    # 绘制营业收入和净利润趋势图
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 营业收入（左Y轴）
    revenue_data = df['营业收入'].values / 100000000  # 转换为亿元
    ax1.bar(dates, revenue_data, alpha=0.7, color='steelblue', label='营业收入')
    ax1.set_xlabel('报告期')
    ax1.set_ylabel('营业收入（亿元）', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')
    
    # 在柱子上显示数值
    for i, v in enumerate(revenue_data):
        ax1.text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=9)
    
    # 净利润（右Y轴）
    ax2 = ax1.twinx()
    profit_data = df['净利润'].values / 100000000  # 转换为亿元
    ax2.plot(dates, profit_data, color='red', marker='o', label='净利润')
    ax2.set_ylabel('净利润（亿元）', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    
    # 在点上显示数值
    for i, v in enumerate(profit_data):
        ax2.annotate(f'{v:.1f}', (i, v), xytext=(0, 5), textcoords='offset points', 
                    ha='center', va='bottom', fontsize=9, color='red')
    
    # 添加标题和网格
    plt.title(f'{stock_code} ({stock_name}) 营业收入与净利润趋势')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # 显示图表
    st.pyplot(fig)
    
    # 绘制同比增长率趋势图
    st.write("#### 同比增长率趋势")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 排除第一行（没有增长率数据）
    growth_df = df.iloc[1:].reset_index(drop=True)
    growth_dates = growth_df['日期'].tolist()
    
    revenue_growth = growth_df['营业收入_同比增长'].values
    profit_growth = growth_df['净利润_同比增长'].values
    
    ax.bar(growth_dates, revenue_growth, alpha=0.7, color='steelblue', label='营业收入同比增长率')
    ax.plot(growth_dates, profit_growth, color='red', marker='o', label='净利润同比增长率')
    
    # 在柱子上显示数值
    for i, v in enumerate(revenue_growth):
        ax.text(i, v, f'{v:.1f}%', ha='center', va='bottom' if v >= 0 else 'top', fontsize=9)
    
    # 在点上显示数值
    for i, v in enumerate(profit_growth):
        ax.annotate(f'{v:.1f}%', (i, v), xytext=(0, 5), textcoords='offset points', 
                   ha='center', va='bottom' if v >= 0 else 'top', fontsize=9, color='red')
    
    # 添加标题和标签
    plt.title(f'{stock_code} ({stock_name}) 同比增长率趋势')
    plt.xlabel('报告期')
    plt.ylabel('同比增长率 (%)')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    
    # 显示图表
    st.pyplot(fig)

def get_financial_ratios(balance_sheet, income_statement):
    """计算财务比率"""
    if balance_sheet is None or income_statement is None or balance_sheet.empty or income_statement.empty:
        st.warning("资产负债表或利润表数据为空")
        return None
    
    # 打印资产负债表前5行供调试
    st.write("资产负债表结构预览:")
    st.dataframe(balance_sheet.head())
    
    # 获取共同的日期列（第一列是项目名，从第二列开始是日期数据）
    bs_dates = balance_sheet.columns[1:]
    is_dates = income_statement.columns[1:]
    
    st.write(f"资产负债表日期列: {', '.join(bs_dates)}")
    st.write(f"利润表日期列: {', '.join(is_dates)}")
    
    common_dates = sorted(set(bs_dates) & set(is_dates), reverse=True)
    st.write(f"共同日期列: {', '.join(common_dates)}")
    
    common_dates = common_dates[:min(5, len(common_dates))]
    
    if not common_dates:
        st.error("资产负债表和利润表没有共同的日期")
        return None
    
    # 确保第一列是字符串类型，使用copy避免警告
    balance_sheet = balance_sheet.copy()
    income_statement = income_statement.copy()
    balance_sheet.iloc[:, 0] = balance_sheet.iloc[:, 0].astype(str)
    income_statement.iloc[:, 0] = income_statement.iloc[:, 0].astype(str)
    
    # 打印第一列的所有值，帮助确定匹配关键词
    st.write("资产负债表第一列的所有值:")
    st.write(balance_sheet.iloc[:, 0].tolist())
    
    # 使用更多的匹配模式
    asset_patterns = ['总资产', '资产总计', '资产总额', '资产负债表']
    equity_patterns = ['所有者权益', '股东权益', '净资产', '所有者权益合计', '股东权益合计']
    profit_patterns = ['净利润', '归属于母公司股东的净利润', '归属于上市公司股东的净利润', '利润总额', '净利', '利润']
    
    # 使用"或"条件连接所有模式
    asset_pattern = '|'.join(asset_patterns)
    equity_pattern = '|'.join(equity_patterns)
    profit_pattern = '|'.join(profit_patterns)
    
    # 查找资产负债表中的总资产和净资产行
    asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains(asset_pattern, na=False)]
    equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains(equity_pattern, na=False)]
    
    # 如果找不到匹配行，尝试更模糊的匹配
    if asset_rows.empty:
        st.warning("未找到总资产行，尝试更模糊的匹配")
        asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('资产', na=False)]
    
    if equity_rows.empty:
        st.warning("未找到净资产行，尝试更模糊的匹配")
        equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('权益', na=False)]
    
    # 查找利润表中的净利润行
    profit_rows = income_statement[income_statement.iloc[:, 0].str.contains(profit_pattern, na=False)]
    
    if profit_rows.empty:
        st.warning("未找到净利润行，尝试更模糊的匹配")
        profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('利润', na=False)]
    
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
    
    for date in common_dates:
        try:
            bs_idx = list(bs_dates).index(date) + 1  # +1 因为第一列是项目名
            is_idx = list(is_dates).index(date) + 1
            
            if (pd.notna(asset_row.iloc[bs_idx]) and pd.notna(equity_row.iloc[bs_idx]) and 
                pd.notna(profit_row.iloc[is_idx])):
                
                try:
                    total_asset = float(asset_row.iloc[bs_idx])
                    net_equity = float(equity_row.iloc[bs_idx])
                    net_profit = float(profit_row.iloc[is_idx])
                    
                    # 计算比率
                    roa = (net_profit / total_asset) * 100 if total_asset != 0 else None
                    roe = (net_profit / net_equity) * 100 if net_equity != 0 else None
                    
                    ratio_data['日期'].append(date)
                    ratio_data['总资产(亿元)'].append(total_asset / 100000000)
                    ratio_data['净资产(亿元)'].append(net_equity / 100000000)
                    ratio_data['净利润(亿元)'].append(net_profit / 100000000)
                    ratio_data['ROA(%)'].append(roa)
                    ratio_data['ROE(%)'].append(roe)
                except (ValueError, TypeError) as e:
                    st.warning(f"日期 {date} 的数据转换出错: {e}")
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
    if ratio_df is None or ratio_df.empty:
        st.warning("没有足够的数据来计算财务比率")
        return
    
    st.subheader("财务比率分析")
    
    # 显示财务比率数据
    st.write("#### 近五年财务比率")
    
    # 格式化数据
    display_df = ratio_df.copy()
    for col in ['总资产(亿元)', '净资产(亿元)', '净利润(亿元)']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}")
    
    for col in ['ROA(%)', 'ROE(%)']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
    
    st.dataframe(display_df, hide_index=True)
    
    # 反转日期顺序以便按时间顺序显示
    ratio_df = ratio_df.iloc[::-1].reset_index(drop=True)
    dates = ratio_df['日期'].tolist()
    
    # 绘制ROA和ROE趋势图
    st.write("#### ROA与ROE趋势")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    roa_data = ratio_df['ROA(%)'].values
    roe_data = ratio_df['ROE(%)'].values
    
    ax.plot(dates, roa_data, color='blue', marker='o', label='ROA(%)')
    ax.plot(dates, roe_data, color='green', marker='s', label='ROE(%)')
    
    # 显示数值
    for i, v in enumerate(roa_data):
        if pd.notna(v):
            ax.annotate(f'{v:.1f}%', (i, v), xytext=(0, 5), textcoords='offset points', 
                       ha='center', va='bottom', fontsize=9, color='blue')
    
    for i, v in enumerate(roe_data):
        if pd.notna(v):
            ax.annotate(f'{v:.1f}%', (i, v), xytext=(0, -15), textcoords='offset points', 
                       ha='center', va='bottom', fontsize=9, color='green')
    
    # 添加标题和标签
    plt.title(f'{stock_code} ({stock_name}) ROA与ROE趋势')
    plt.xlabel('报告期')
    plt.ylabel('百分比 (%)')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    
    # 显示图表
    st.pyplot(fig)

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
        
        # 添加调试模式选项
        debug_mode = st.checkbox("调试模式", value=False, help="开启以显示详细的数据处理过程和调试信息")
        
        if stock_code:
            download_btn = st.button("下载财务数据")
            analyze_btn = st.button("分析现有数据")
        
    if stock_code:
        # 当用户点击下载按钮时
        if download_btn:
            report_data, stock_name = download_financial_reports(stock_code)
            
            if report_data:
                # 自动进行分析
                with st.spinner("正在分析财务数据..."):
                    # 创建一个新的容器用于显示调试信息
                    debug_container = st.container()
                    
                    # 根据是否开启调试模式，决定是否显示调试容器内容
                    with st.expander("数据处理详情", expanded=debug_mode):
                        # 提取近五年的营业收入和净利润数据
                        metrics_df, _ = get_financial_metrics(report_data["利润表"])
                    
                    if metrics_df is not None:
                        # 绘制财务指标图表
                        plot_financial_metrics(metrics_df, stock_code, stock_name)
                        
                        # 计算并绘制财务比率
                        with st.expander("财务比率计算详情", expanded=debug_mode):
                            ratio_df = get_financial_ratios(report_data["资产负债表"], report_data["利润表"])
                        
                        if ratio_df is not None:
                            plot_financial_ratios(ratio_df, stock_code, stock_name)
                        else:
                            st.warning("无法计算财务比率，可能是由于数据格式问题")
                    else:
                        st.warning("无法提取足够的财务指标数据进行分析，请尝试开启调试模式查看详细信息")
            
        # 当用户点击分析按钮时
        elif analyze_btn:
            # 查找是否有现有数据
            report_data, stock_name = load_existing_reports(stock_code)
            
            if report_data:
                st.success(f"已加载 {stock_code} ({stock_name}) 的财务数据")
                
                with st.spinner("正在分析财务数据..."):
                    # 根据是否开启调试模式，决定是否显示调试容器内容
                    with st.expander("数据处理详情", expanded=debug_mode):
                        # 提取近五年的营业收入和净利润数据
                        metrics_df, _ = get_financial_metrics(report_data["利润表"])
                    
                    if metrics_df is not None:
                        # 绘制财务指标图表
                        plot_financial_metrics(metrics_df, stock_code, stock_name)
                        
                        # 计算并绘制财务比率
                        with st.expander("财务比率计算详情", expanded=debug_mode):
                            ratio_df = get_financial_ratios(report_data["资产负债表"], report_data["利润表"])
                        
                        if ratio_df is not None:
                            plot_financial_ratios(ratio_df, stock_code, stock_name)
                        else:
                            st.warning("无法计算财务比率，可能是由于数据格式问题")
                    else:
                        st.warning("无法提取足够的财务指标数据进行分析，请尝试开启调试模式查看详细信息")
            else:
                st.warning(f"未找到 {stock_code} 的现有财务数据，请先下载")
    
    # 页脚信息
    st.markdown("---")
    st.markdown("**注意:** 本应用数据来源于AKShare，仅供参考，不构成投资建议。")
    st.markdown("数据源: 新浪财经")

if __name__ == "__main__":
    app() 