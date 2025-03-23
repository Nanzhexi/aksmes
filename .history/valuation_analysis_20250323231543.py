import streamlit as st
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import time

# 设置页面
st.set_page_config(page_title="贵州茅台估值分析", page_icon="📊", layout="wide")

# 配置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

def get_stock_valuation_data(stock_code="600519", years=5):
    """获取股票估值数据"""
    st.write(f"正在获取 {stock_code} 近{years}年的估值数据...")
    
    try:
        # 计算开始日期（5年前的今天）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y%m%d')
        
        # 使用akshare获取估值数据
        valuation_data = ak.stock_a_lg_indicator(symbol=stock_code)
        
        # 如果数据为空，尝试其他接口
        if valuation_data is None or valuation_data.empty:
            st.warning("主接口未返回数据，尝试备用接口...")
            valuation_data = ak.stock_a_pe(symbol=stock_code, start_date=start_date, end_date=end_date)
        
        # 确保日期列格式正确
        if 'trade_date' in valuation_data.columns:
            date_col = 'trade_date'
        elif 'date' in valuation_data.columns:
            date_col = 'date'
        else:
            # 查找可能的日期列
            for col in valuation_data.columns:
                if 'date' in col.lower() or 'time' in col.lower():
                    date_col = col
                    break
            else:
                # 如果找不到日期列，使用第一列作为索引
                date_col = valuation_data.columns[0]
        
        # 设置日期列为datetime格式
        valuation_data[date_col] = pd.to_datetime(valuation_data[date_col])
        
        # 设置日期为索引
        valuation_data.set_index(date_col, inplace=True)
        
        # 过滤近5年的数据
        cutoff_date = datetime.now() - timedelta(days=years*365)
        valuation_data = valuation_data[valuation_data.index >= cutoff_date]
        
        # 检查是否有必要的列
        required_indicators = ['pe', 'pb', 'ps']
        available_indicators = []
        
        # 识别包含PE/PB/PS的列
        for col in valuation_data.columns:
            col_lower = col.lower()
            if 'pe' in col_lower or '市盈率' in col_lower:
                valuation_data['pe'] = valuation_data[col]
                available_indicators.append('pe')
            elif 'pb' in col_lower or '市净率' in col_lower:
                valuation_data['pb'] = valuation_data[col]
                available_indicators.append('pb')
            elif 'ps' in col_lower or '市销率' in col_lower:
                valuation_data['ps'] = valuation_data[col]
                available_indicators.append('ps')
        
        # 如果缺少任何指标，提示用户
        missing_indicators = [ind for ind in required_indicators if ind not in available_indicators]
        if missing_indicators:
            st.warning(f"数据中缺少以下指标: {', '.join(missing_indicators)}")
        
        # 确保数据是浮点型
        for ind in available_indicators:
            valuation_data[ind] = pd.to_numeric(valuation_data[ind], errors='coerce')
        
        return valuation_data, available_indicators
    
    except Exception as e:
        st.error(f"获取数据时出错: {e}")
        return None, []

def calculate_statistics(data, indicator, periods):
    """计算不同周期的统计值"""
    results = {}
    
    for period_name, days in periods.items():
        # 获取指定周期的数据
        cutoff_date = datetime.now() - timedelta(days=days)
        period_data = data[data.index >= cutoff_date][indicator].dropna()
        
        if len(period_data) < 10:  # 至少需要10个数据点
            results[period_name] = {
                'mean': None, 
                'max': None, 
                'min': None,
                'top_10_pct_mean': None,
                'bottom_10_pct_mean': None,
                'current_percentile': None
            }
            continue
        
        # 排序数据用于百分位计算
        sorted_data = period_data.sort_values()
        
        # 计算统计值
        mean_value = period_data.mean()
        max_value = period_data.max()
        min_value = period_data.min()
        
        # 计算前10%和后10%的均值
        n = len(sorted_data)
        bottom_10_pct = sorted_data.iloc[:int(n*0.1)].mean()
        top_10_pct = sorted_data.iloc[int(n*0.9):].mean()
        
        # 获取最新值
        current_value = period_data.iloc[-1] if not period_data.empty else None
        
        # 计算当前值在历史分位
        if current_value is not None:
            # 计算百分位
            percentile = (sorted_data < current_value).mean() * 100
        else:
            percentile = None
        
        results[period_name] = {
            'mean': mean_value, 
            'max': max_value, 
            'min': min_value,
            'top_10_pct_mean': top_10_pct,
            'bottom_10_pct_mean': bottom_10_pct,
            'current': current_value,
            'current_percentile': percentile
        }
    
    return results

def plot_valuation_trends(data, indicator, indicator_name):
    """绘制估值指标的趋势图"""
    # 提取指标数据
    indicator_data = data[indicator].dropna()
    
    # 创建plotly图表
    fig = go.Figure()
    
    # 添加指标线
    fig.add_trace(
        go.Scatter(
            x=indicator_data.index, 
            y=indicator_data.values,
            mode='lines',
            name=indicator_name
        )
    )
    
    # 添加平均线
    mean_value = indicator_data.mean()
    fig.add_trace(
        go.Scatter(
            x=[indicator_data.index.min(), indicator_data.index.max()],
            y=[mean_value, mean_value],
            mode='lines',
            name=f'平均值: {mean_value:.2f}',
            line=dict(color='red', dash='dash')
        )
    )
    
    # 获取最新值
    latest_value = indicator_data.iloc[-1] if not indicator_data.empty else None
    if latest_value is not None:
        fig.add_annotation(
            x=indicator_data.index[-1],
            y=latest_value,
            text=f"当前: {latest_value:.2f}",
            showarrow=True,
            arrowhead=1
        )
    
    # 设置图表布局
    fig.update_layout(
        title=f"{indicator_name}趋势图",
        xaxis_title="日期",
        yaxis_title=indicator_name,
        hovermode="x unified",
        height=500
    )
    
    return fig

def plot_valuation_distribution(data, indicator, indicator_name):
    """绘制估值指标的分布直方图"""
    # 提取指标数据
    indicator_data = data[indicator].dropna()
    
    # 创建plotly直方图
    fig = go.Figure()
    
    # 添加直方图
    fig.add_trace(
        go.Histogram(
            x=indicator_data.values,
            nbinsx=30,
            name=indicator_name
        )
    )
    
    # 添加均值线
    mean_value = indicator_data.mean()
    fig.add_trace(
        go.Scatter(
            x=[mean_value, mean_value],
            y=[0, indicator_data.value_counts().max()],
            mode='lines',
            name=f'平均值: {mean_value:.2f}',
            line=dict(color='red', dash='dash')
        )
    )
    
    # 获取最新值
    latest_value = indicator_data.iloc[-1] if not indicator_data.empty else None
    if latest_value is not None:
        fig.add_trace(
            go.Scatter(
                x=[latest_value, latest_value],
                y=[0, indicator_data.value_counts().max()/2],
                mode='lines',
                name=f'当前值: {latest_value:.2f}',
                line=dict(color='green')
            )
        )
    
    # 设置图表布局
    fig.update_layout(
        title=f"{indicator_name}分布直方图",
        xaxis_title=indicator_name,
        yaxis_title="频率",
        height=400
    )
    
    return fig

def main():
    st.title("贵州茅台估值分析")
    
    # 侧边栏 - 基本设置
    with st.sidebar:
        st.header("设置")
        
        # 股票代码输入
        stock_code = st.text_input("输入股票代码", "600519")
        stock_name = st.text_input("股票名称", "贵州茅台")
        
        # 年份选择
        years = st.slider("分析年数", 1, 10, 5)
        
        # 刷新数据按钮
        refresh = st.button("获取最新数据")
    
    # 获取估值数据
    data, available_indicators = get_stock_valuation_data(stock_code, years)
    
    if data is None or data.empty:
        st.error("无法获取有效的估值数据，请检查股票代码或网络连接")
        return
    
    # 数据概览
    st.header(f"{stock_name}({stock_code})估值数据概览")
    st.write(f"数据时间范围: {data.index.min().strftime('%Y-%m-%d')} 至 {data.index.max().strftime('%Y-%m-%d')}")
    st.write(f"总数据点: {len(data)}")
    
    # 定义分析周期
    periods = {
        "5年": 5*365,
        "3年": 3*365,
        "1年": 1*365
    }
    
    # 创建标签页显示不同指标
    tabs = st.tabs(["市盈率(PE)", "市净率(PB)", "市销率(PS)"])
    
    # 指标名称映射
    indicator_names = {
        'pe': '市盈率(PE)',
        'pb': '市净率(PB)',
        'ps': '市销率(PS)'
    }
    
    # 指标分析循环
    for i, indicator in enumerate(['pe', 'pb', 'ps']):
        if indicator in available_indicators:
            with tabs[i]:
                st.subheader(f"{indicator_names[indicator]}分析")
                
                # 计算统计值
                stats = calculate_statistics(data, indicator, periods)
                
                # 创建统计数据表格
                stats_df = pd.DataFrame(index=periods.keys())
                stats_df["平均值"] = [stats[period]['mean'] for period in periods.keys()]
                stats_df["最大值"] = [stats[period]['max'] for period in periods.keys()]
                stats_df["最小值"] = [stats[period]['min'] for period in periods.keys()]
                stats_df["最高10%均值"] = [stats[period]['top_10_pct_mean'] for period in periods.keys()]
                stats_df["最低10%均值"] = [stats[period]['bottom_10_pct_mean'] for period in periods.keys()]
                stats_df["当前值"] = [stats[period]['current'] for period in periods.keys()]
                stats_df["当前百分位(%)"] = [stats[period]['current_percentile'] for period in periods.keys()]
                
                # 格式化数据
                formatted_df = stats_df.applymap(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
                
                # 显示统计表格
                st.dataframe(formatted_df, use_container_width=True)
                
                # 显示趋势图和分布图
                col1, col2 = st.columns(2)
                
                with col1:
                    trend_fig = plot_valuation_trends(data, indicator, indicator_names[indicator])
                    st.plotly_chart(trend_fig, use_container_width=True)
                
                with col2:
                    dist_fig = plot_valuation_distribution(data, indicator, indicator_names[indicator])
                    st.plotly_chart(dist_fig, use_container_width=True)
                
                # 添加估值判断
                current_percentile = stats["5年"].get('current_percentile')
                if current_percentile is not None:
                    if current_percentile < 20:
                        st.success(f"🟢 当前{indicator_names[indicator]}处于近5年的**低位**区间(历史分位: {current_percentile:.1f}%)，估值相对**便宜**。")
                    elif current_percentile > 80:
                        st.error(f"🔴 当前{indicator_names[indicator]}处于近5年的**高位**区间(历史分位: {current_percentile:.1f}%)，估值相对**昂贵**。")
                    else:
                        st.info(f"🟡 当前{indicator_names[indicator]}处于近5年的**中位**区间(历史分位: {current_percentile:.1f}%)，估值相对**适中**。")
        else:
            with tabs[i]:
                st.warning(f"数据中不包含{indicator_names[indicator]}指标")

if __name__ == "__main__":
    main() 