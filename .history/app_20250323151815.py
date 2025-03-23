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
                    
                # 转换报表为最近10年的数据
                if len(df.columns) > 11:  # 第一列通常是项目名称，所以是11而不是10
                    df = df.iloc[:, :11]
                
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
        return None, None
    
    dates = income_statement.columns[1:]
    
    # 查找营业收入和净利润行
    revenue_rows = income_statement[income_statement.iloc[:, 0].str.contains('营业收入|营业总收入', na=False)]
    profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('净利润|归属于母公司股东的净利润', na=False)]
    
    if revenue_rows.empty or profit_rows.empty:
        return None, None
    
    # 提取数据
    revenue_data = {}
    profit_data = {}
    
    revenue_row = revenue_rows.iloc[0]
    profit_row = profit_rows.iloc[0]
    
    for i, date in enumerate(dates):
        if i+1 < len(revenue_row) and pd.notna(revenue_row.iloc[i+1]) and revenue_row.iloc[i+1]:
            revenue_data[date] = revenue_row.iloc[i+1]
        
        if i+1 < len(profit_row) and pd.notna(profit_row.iloc[i+1]) and profit_row.iloc[i+1]:
            profit_data[date] = profit_row.iloc[i+1]
    
    # 转换为DataFrame
    data = {
        '日期': [],
        '营业收入': [],
        '净利润': []
    }
    
    # 获取两者共有的日期
    common_dates = sorted(set(revenue_data.keys()) & set(profit_data.keys()), reverse=True)
    
    # 取最近5年的数据（如果有）
    common_dates = common_dates[:min(5, len(common_dates))]
    
    for date in common_dates:
        data['日期'].append(date)
        data['营业收入'].append(revenue_data[date])
        data['净利润'].append(profit_data[date])
    
    # 创建DataFrame
    df = pd.DataFrame(data)
    
    # 计算同比增长率
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
        return None
    
    # 获取共同的日期列（第一列是项目名，从第二列开始是日期数据）
    bs_dates = balance_sheet.columns[1:]
    is_dates = income_statement.columns[1:]
    
    common_dates = sorted(set(bs_dates) & set(is_dates), reverse=True)
    common_dates = common_dates[:min(5, len(common_dates))]
    
    if not common_dates:
        return None
    
    # 查找资产负债表中的总资产和净资产行
    asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('总资产|资产总计|资产负债表', na=False)]
    equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('所有者权益|股东权益|净资产', na=False)]
    
    # 查找利润表中的净利润行
    profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('净利润|归属于母公司股东的净利润', na=False)]
    
    if asset_rows.empty or equity_rows.empty or profit_rows.empty:
        return None
    
    # 提取数据
    asset_row = asset_rows.iloc[0]
    equity_row = equity_rows.iloc[0]
    profit_row = profit_rows.iloc[0]
    
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
        bs_idx = list(bs_dates).index(date) + 1  # +1 因为第一列是项目名
        is_idx = list(is_dates).index(date) + 1
        
        if (pd.notna(asset_row.iloc[bs_idx]) and pd.notna(equity_row.iloc[bs_idx]) and 
            pd.notna(profit_row.iloc[is_idx])):
            
            total_asset = asset_row.iloc[bs_idx]
            net_equity = equity_row.iloc[bs_idx]
            net_profit = profit_row.iloc[is_idx]
            
            # 计算比率
            roa = (net_profit / total_asset) * 100 if total_asset != 0 else None
            roe = (net_profit / net_equity) * 100 if net_equity != 0 else None
            
            ratio_data['日期'].append(date)
            ratio_data['总资产(亿元)'].append(total_asset / 100000000)
            ratio_data['净资产(亿元)'].append(net_equity / 100000000)
            ratio_data['净利润(亿元)'].append(net_profit / 100000000)
            ratio_data['ROA(%)'].append(roa)
            ratio_data['ROE(%)'].append(roe)
    
    # 创建DataFrame
    ratio_df = pd.DataFrame(ratio_data)
    
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
                    # 提取近五年的营业收入和净利润数据
                    metrics_df, _ = get_financial_metrics(report_data["利润表"])
                    
                    if metrics_df is not None:
                        # 绘制财务指标图表
                        plot_financial_metrics(metrics_df, stock_code, stock_name)
                        
                        # 计算并绘制财务比率
                        ratio_df = get_financial_ratios(report_data["资产负债表"], report_data["利润表"])
                        if ratio_df is not None:
                            plot_financial_ratios(ratio_df, stock_code, stock_name)
                    else:
                        st.warning("无法提取足够的财务指标数据进行分析")
            
        # 当用户点击分析按钮时
        elif analyze_btn:
            # 查找是否有现有数据
            report_data, stock_name = load_existing_reports(stock_code)
            
            if report_data:
                st.success(f"已加载 {stock_code} ({stock_name}) 的财务数据")
                
                with st.spinner("正在分析财务数据..."):
                    # 提取近五年的营业收入和净利润数据
                    metrics_df, _ = get_financial_metrics(report_data["利润表"])
                    
                    if metrics_df is not None:
                        # 绘制财务指标图表
                        plot_financial_metrics(metrics_df, stock_code, stock_name)
                        
                        # 计算并绘制财务比率
                        ratio_df = get_financial_ratios(report_data["资产负债表"], report_data["利润表"])
                        if ratio_df is not None:
                            plot_financial_ratios(ratio_df, stock_code, stock_name)
                    else:
                        st.warning("无法提取足够的财务指标数据进行分析")
            else:
                st.warning(f"未找到 {stock_code} 的现有财务数据，请先下载")
    
    # 页脚信息
    st.markdown("---")
    st.markdown("**注意:** 本应用数据来源于AKShare，仅供参考，不构成投资建议。")
    st.markdown("数据源: 新浪财经")

if __name__ == "__main__":
    app() 