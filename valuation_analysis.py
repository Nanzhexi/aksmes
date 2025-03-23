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
        
        # 使用akshare获取市盈率数据
        pe_data = None
        try:
            pe_data = ak.stock_a_pe(symbol=stock_code, start_date=start_date, end_date=end_date)
            st.success("成功获取市盈率(PE)数据")
        except Exception as e:
            st.warning(f"获取市盈率数据出错: {e}")
        
        # 尝试获取市净率数据
        pb_data = None
        try:
            pb_data = ak.stock_a_pb(symbol=stock_code, start_date=start_date, end_date=end_date)
            st.success("成功获取市净率(PB)数据")
        except Exception as e:
            st.warning(f"获取市净率数据出错: {e}")
            # 如果函数不存在，尝试其他方法获取PB
            try:
                # 尝试从估值指标中获取
                indicator_data = ak.stock_a_indicator_lg(symbol=stock_code)
                if indicator_data is not None and not indicator_data.empty and 'pb' in indicator_data.columns:
                    pb_data = indicator_data[['trade_date', 'pb']]
                    st.success("通过估值指标成功获取市净率(PB)数据")
            except Exception as e:
                st.warning(f"尝试通过估值指标获取PB出错: {e}")
        
        # 尝试获取市销率数据
        ps_data = None
        try:
            ps_data = ak.stock_a_ps(symbol=stock_code, start_date=start_date, end_date=end_date)
            st.success("成功获取市销率(PS)数据")
        except Exception as e:
            st.warning(f"获取市销率数据出错: {e}")
            # 尝试从其他接口获取
            try:
                # 尝试从估值指标中获取
                indicator_data = ak.stock_a_indicator_lg(symbol=stock_code)
                if indicator_data is not None and not indicator_data.empty and 'ps' in indicator_data.columns:
                    ps_data = indicator_data[['trade_date', 'ps']]
                    st.success("通过估值指标成功获取市销率(PS)数据")
            except Exception as e:
                st.warning(f"尝试通过估值指标获取PS出错: {e}")
        
        # 如果所有方法都失败，尝试使用股票基本面指标获取数据
        if (pe_data is None or pe_data.empty) and (pb_data is None or pb_data.empty) and (ps_data is None or ps_data.empty):
            st.warning("常规方法获取估值数据失败，尝试获取股票基本面指标...")
            try:
                # 获取股票所有指标
                stock_indicator = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="qfq")
                if stock_indicator is not None and not stock_indicator.empty:
                    st.success("成功获取股票历史数据")
                    # 计算估值指标
                    if 'close' in stock_indicator.columns:
                        # 1. 尝试获取每股收益和每股净资产
                        try:
                            finance_indicator = ak.stock_financial_report_sina(stock=stock_code, symbol="资产负债表")
                            if finance_indicator is not None and not finance_indicator.empty:
                                # 这里需要更复杂的处理来计算PE、PB、PS...
                                pass
                        except:
                            pass
            except Exception as e:
                st.error(f"获取股票基本面数据失败: {e}")
        
        # 合并数据
        valuation_data = None
        available_indicators = []
        
        # 准备处理PE数据
        if pe_data is not None and not pe_data.empty:
            # 识别日期列
            date_col = None
            for col in pe_data.columns:
                if 'date' in col.lower() or 'time' in col.lower() or 'trade' in col.lower():
                    date_col = col
                    break
            
            if date_col is not None:
                # 设置索引
                pe_temp = pe_data.copy()
                pe_temp[date_col] = pd.to_datetime(pe_temp[date_col])
                pe_temp.set_index(date_col, inplace=True)
                
                # 识别PE列
                pe_col = None
                for col in pe_temp.columns:
                    if 'pe' in col.lower() or '市盈率' in col.lower():
                        pe_col = col
                        break
                
                if pe_col is not None:
                    # 重命名列
                    pe_temp.rename(columns={pe_col: 'pe'}, inplace=True)
                    
                    # 如果valuation_data为空，初始化
                    if valuation_data is None:
                        valuation_data = pd.DataFrame(index=pe_temp.index)
                    
                    # 添加PE列
                    valuation_data['pe'] = pe_temp['pe']
                    available_indicators.append('pe')
        
        # 准备处理PB数据
        if pb_data is not None and not pb_data.empty:
            # 识别日期列
            date_col = None
            for col in pb_data.columns:
                if 'date' in col.lower() or 'time' in col.lower() or 'trade' in col.lower():
                    date_col = col
                    break
            
            if date_col is not None:
                # 设置索引
                pb_temp = pb_data.copy()
                pb_temp[date_col] = pd.to_datetime(pb_temp[date_col])
                pb_temp.set_index(date_col, inplace=True)
                
                # 识别PB列
                pb_col = None
                for col in pb_temp.columns:
                    if 'pb' in col.lower() or '市净率' in col.lower():
                        pb_col = col
                        break
                
                if pb_col is not None:
                    # 重命名列
                    pb_temp.rename(columns={pb_col: 'pb'}, inplace=True)
                    
                    # 如果valuation_data为空，初始化
                    if valuation_data is None:
                        valuation_data = pd.DataFrame(index=pb_temp.index)
                    else:
                        # 确保索引一致
                        pb_temp = pb_temp.reindex(valuation_data.index)
                    
                    # 添加PB列
                    valuation_data['pb'] = pb_temp['pb']
                    available_indicators.append('pb')
        
        # 准备处理PS数据
        if ps_data is not None and not ps_data.empty:
            # 识别日期列
            date_col = None
            for col in ps_data.columns:
                if 'date' in col.lower() or 'time' in col.lower() or 'trade' in col.lower():
                    date_col = col
                    break
            
            if date_col is not None:
                # 设置索引
                ps_temp = ps_data.copy()
                ps_temp[date_col] = pd.to_datetime(ps_temp[date_col])
                ps_temp.set_index(date_col, inplace=True)
                
                # 识别PS列
                ps_col = None
                for col in ps_temp.columns:
                    if 'ps' in col.lower() or '市销率' in col.lower():
                        ps_col = col
                        break
                
                if ps_col is not None:
                    # 重命名列
                    ps_temp.rename(columns={ps_col: 'ps'}, inplace=True)
                    
                    # 如果valuation_data为空，初始化
                    if valuation_data is None:
                        valuation_data = pd.DataFrame(index=ps_temp.index)
                    else:
                        # 确保索引一致
                        ps_temp = ps_temp.reindex(valuation_data.index)
                    
                    # 添加PS列
                    valuation_data['ps'] = ps_temp['ps']
                    available_indicators.append('ps')
        
        # 如果valuation_data仍然为空，则尝试使用其他接口
        if valuation_data is None or valuation_data.empty:
            st.warning("所有方法都无法获取估值数据，尝试最后的备用方案...")
            
            # 尝试获取个股资金流向数据，其中可能包含最新估值
            try:
                stock_fund_flow = ak.stock_individual_fund_flow(stock=stock_code)
                if stock_fund_flow is not None and not stock_fund_flow.empty:
                    # 可能需要提取其中的估值数据
                    pass
            except Exception as e:
                st.error(f"尝试获取资金流向数据失败: {e}")
        
        # 如果仍然没有数据，返回错误
        if valuation_data is None or valuation_data.empty or len(available_indicators) == 0:
            st.error("无法获取任何估值数据，请检查网络连接或股票代码")
            return None, []
        
        # 确保数据是浮点型
        for ind in available_indicators:
            valuation_data[ind] = pd.to_numeric(valuation_data[ind], errors='coerce')
        
        # 过滤近n年的数据
        cutoff_date = datetime.now() - timedelta(days=years*365)
        valuation_data = valuation_data[valuation_data.index >= cutoff_date]
        
        # 检查数据是否足够
        if valuation_data.empty:
            st.error(f"过滤后没有{years}年内的估值数据")
            return None, []
            
        # 显示获取的数据
        st.write(f"成功获取以下估值指标: {', '.join(available_indicators)}")
        
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