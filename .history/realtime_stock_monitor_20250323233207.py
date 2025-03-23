import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import akshare as ak

# 设置页面
st.set_page_config(page_title="股票实时监控", page_icon="📈", layout="wide")

# 页面标题
st.title("股票实时行情与资金流向监控")

# 侧边栏配置
with st.sidebar:
    st.header("设置")
    stock_code = st.text_input("股票代码", "600519")
    
    # 添加市场选择
    market = st.selectbox("选择市场", ["上海", "深圳"], index=0)
    
    # 更新频率设置
    update_interval = st.slider("更新频率(秒)", min_value=6, max_value=60, value=6, step=1)
    
    # 数据展示时长设置
    display_minutes = st.slider("图表显示时长(分钟)", min_value=10, max_value=120, value=30, step=5)
    
    # 运行控制
    is_running = st.checkbox("开始监控", value=True)
    clear_data = st.button("清空历史数据")

# 检查股票代码格式并标准化
def normalize_stock_code(code, market="上海"):
    code = code.strip()
    
    # 如果只有数字，添加市场前缀
    if code.isdigit():
        if market == "上海":
            if code.startswith("6"):
                return f"sh{code}"
            else:
                return f"sh{code}"  # 默认使用上海
        else:  # 深圳
            if code.startswith(("0", "3")):
                return f"sz{code}"
            else:
                return f"sz{code}"  # 默认使用深圳
    
    # 如果已经有前缀，标准化格式
    if code.lower().startswith(("sh", "sz", "bj")):
        return code.lower()
    
    return f"sh{code}"  # 默认返回上海市场

# 获取东方财富实时股票数据
def get_eastmoney_realtime_quote(stock_code):
    normalized_code = normalize_stock_code(stock_code, market)
    
    # 构建东方财富实时行情API的URL
    url = f"http://push2.eastmoney.com/api/qt/stock/get"
    
    params = {
        "secid": normalized_code,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f59,f60,f107,f111,f60,f46,f45,f47,f168,f169,f170,f85,f84",
        "invt": "2",
        "fltt": "2",
        "_": int(time.time() * 1000)
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        
        if 'data' in data:
            return data['data']
        else:
            st.error(f"获取行情数据失败: {data.get('message', '未知错误')}")
            return None
    except Exception as e:
        st.error(f"请求行情数据时出错: {str(e)}")
        return None

# 获取东方财富资金流向数据
def get_eastmoney_capital_flow(stock_code):
    normalized_code = normalize_stock_code(stock_code, market)
    st.info(f"正在获取 {normalized_code} 的资金流向数据...")
    
    # 尝试使用akshare获取资金流向数据
    try:
        # 使用akshare获取资金流向
        if market == "上海" and stock_code.startswith("6"):
            full_code = f"sh{stock_code}"
        elif market == "深圳" and (stock_code.startswith("0") or stock_code.startswith("3")):
            full_code = f"sz{stock_code}"
        else:
            full_code = normalized_code
            
        # 尝试从akshare获取资金流向数据
        try:
            stock_flow_data = ak.stock_individual_fund_flow(stock=stock_code)
            if stock_flow_data is not None and not stock_flow_data.empty:
                st.success("使用akshare成功获取资金流向数据")
                # 转换为与东方财富API兼容的格式
                flow_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 检查列名并提取数据
                main_net = 0
                retail_net = 0
                super_large = 0
                large = 0
                medium = 0
                small = 0
                
                # 尝试从不同可能的列名中获取数据
                for col in stock_flow_data.columns:
                    # 主力资金
                    if '主力' in col and '净' in col and '流入' in col:
                        try:
                            main_net = float(stock_flow_data.iloc[0][col].replace(',', ''))
                        except:
                            pass
                    # 散户资金 (通常是中小单之和)
                    if '散户' in col and '净' in col:
                        try:
                            retail_net = float(stock_flow_data.iloc[0][col].replace(',', ''))
                        except:
                            pass
                    # 超大单
                    if '超大单' in col and '净' in col:
                        try:
                            super_large = float(stock_flow_data.iloc[0][col].replace(',', ''))
                        except:
                            pass
                    # 大单
                    if '大单' in col and '净' in col and '超' not in col:
                        try:
                            large = float(stock_flow_data.iloc[0][col].replace(',', ''))
                        except:
                            pass
                    # 中单
                    if '中单' in col and '净' in col:
                        try:
                            medium = float(stock_flow_data.iloc[0][col].replace(',', ''))
                        except:
                            pass
                    # 小单
                    if '小单' in col and '净' in col:
                        try:
                            small = float(stock_flow_data.iloc[0][col].replace(',', ''))
                        except:
                            pass
                
                # 如果散户数据为0，尝试计算
                if retail_net == 0:
                    retail_net = medium + small
                
                # 创建兼容格式的数据
                synthesized_data = {
                    'klines': [f"{flow_time},{main_net},{retail_net},{super_large},{large},{medium},{small}"]
                }
                return synthesized_data
        except Exception as e:
            st.warning(f"使用akshare获取资金流向失败: {e}, 尝试使用东方财富API...")
    
    # 构建东方财富资金流向API的URL (第一种尝试 - 分钟级数据)
    url = f"http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    
    params = {
        "secid": normalized_code,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63",
        "klt": "1",  # 1分钟
        "fqt": "0",
        "lmt": "60",  # 最近60条数据
        "_": int(time.time() * 1000)
    }
    
    try:
        st.info(f"请求URL: {url}?secid={normalized_code}&...")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and data['data'] is not None:
            st.success("成功获取分钟级资金流向数据")
            return data['data']
        else:
            st.warning(f"分钟级资金流向获取失败: {data.get('message', '未知错误')}, 尝试获取日级数据...")
            
            # 使用备用方法获取日级资金流向
            try:
                backup_url = f"http://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
                backup_params = {
                    "secid": normalized_code,
                    "fields1": "f1,f2,f3,f7",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": "101",  # 日K
                    "lmt": "10",  # 最近10个交易日
                    "_": int(time.time() * 1000)
                }
                
                st.info(f"请求URL: {backup_url}?secid={normalized_code}&...")
                backup_response = requests.get(backup_url, params=backup_params)
                backup_response.raise_for_status()
                backup_data = backup_response.json()
                
                if 'data' in backup_data and backup_data['data'] is not None:
                    st.success("成功获取日级别资金流向数据")
                    return backup_data['data']
                else:
                    st.warning(f"日级别资金流向数据获取失败, 尝试其他接口...")
                    
                    # 尝试第三种接口 - 历史资金流向接口
                    try:
                        third_url = f"http://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
                        third_params = {
                            "lmt": "0",
                            "klt": "101",
                            "secid": normalized_code,
                            "fields1": "f1,f2,f3,f7",
                            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                            "_": int(time.time() * 1000)
                        }
                        
                        st.info(f"请求URL: {third_url}?secid={normalized_code}&...")
                        third_response = requests.get(third_url, params=third_params)
                        third_response.raise_for_status()
                        third_data = third_response.json()
                        
                        if 'data' in third_data and third_data['data'] is not None:
                            st.success("成功获取历史资金流向数据")
                            return third_data['data']
                    except Exception as e:
                        st.error(f"尝试第三种接口获取资金流向失败: {str(e)}")
            except Exception as e:
                st.error(f"获取日级别资金流向数据失败: {str(e)}")
    except Exception as e:
        st.error(f"请求资金流向数据时出错: {str(e)}")
    
    # 如果所有方法都失败，使用模拟数据
    st.warning("所有资金流向数据获取方法都失败，使用模拟数据...")
    return generate_mock_flow_data(stock_code)

# 生成模拟资金流向数据
def generate_mock_flow_data(stock_code):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 获取随机但合理的资金流向数据
    main_net_inflow = np.random.normal(0, 100)
    retail_net_inflow = -main_net_inflow * 0.9 + np.random.normal(0, 10)  # 与主力相反
    super_large_net_inflow = main_net_inflow * 0.6 + np.random.normal(0, 20)
    large_net_inflow = main_net_inflow * 0.4 + np.random.normal(0, 15)
    medium_net_inflow = retail_net_inflow * 0.4 + np.random.normal(0, 10)
    small_net_inflow = retail_net_inflow * 0.6 + np.random.normal(0, 5)
    
    # 创建一个形似东方财富API返回的数据结构
    mock_data = {
        'klines': [
            f"{current_time},{main_net_inflow:.2f},{retail_net_inflow:.2f},{super_large_net_inflow:.2f},{large_net_inflow:.2f},{medium_net_inflow:.2f},{small_net_inflow:.2f}"
        ]
    }
    
    return mock_data

# 使用akshare获取股票名称
@st.cache_data(ttl=3600)  # 缓存1小时
def get_stock_name(stock_code):
    try:
        # 尝试使用akshare获取股票基本信息
        stock_info = ak.stock_individual_info_em(symbol=stock_code)
        if stock_info is not None and not stock_info.empty:
            for index, row in stock_info.iterrows():
                if '股票简称' in row['item']:
                    return row['value']
        
        # 如果上面的方法失败，尝试从股票列表中获取
        stock_list = ak.stock_zh_a_spot_em()
        if stock_list is not None and not stock_list.empty:
            filtered = stock_list[stock_list['代码'] == stock_code]
            if not filtered.empty:
                return filtered.iloc[0]['名称']
        
        return stock_code  # 如果找不到名称，返回代码作为名称
    except Exception as e:
        st.warning(f"获取股票名称失败: {e}")
        return stock_code

# 处理实时行情数据
def process_quote_data(quote_data):
    if not quote_data:
        return None
    
    # 提取所需的字段
    processed_data = {
        'timestamp': datetime.now(),
        'price': quote_data.get('f43', 0) / 100 if quote_data.get('f43') else 0,  # 当前价格
        'change': quote_data.get('f169', 0) / 100 if quote_data.get('f169') else 0,  # 涨跌额
        'change_percent': quote_data.get('f170', 0) / 100 if quote_data.get('f170') else 0,  # 涨跌幅
        'volume': quote_data.get('f47', 0) / 100 if quote_data.get('f47') else 0,  # 成交量
        'amount': quote_data.get('f48', 0) / 10000 if quote_data.get('f48') else 0,  # 成交额(万元)
        'open': quote_data.get('f46', 0) / 100 if quote_data.get('f46') else 0,  # 开盘价
        'high': quote_data.get('f44', 0) / 100 if quote_data.get('f44') else 0,  # 最高价
        'low': quote_data.get('f45', 0) / 100 if quote_data.get('f45') else 0,  # 最低价
    }
    
    return processed_data

# 处理资金流向数据
def process_flow_data(flow_data):
    if not flow_data or 'klines' not in flow_data:
        # 尝试处理备用格式
        if flow_data and 'klines' not in flow_data and 'kline' in flow_data:
            flow_data['klines'] = flow_data['kline']
        else:
            return None
    
    if not flow_data['klines'] or len(flow_data['klines']) == 0:
        return None
    
    # 获取最新的资金流向数据
    latest_data = flow_data['klines'][-1].split(',')
    
    try:
        # 显示原始数据以便调试
        st.info(f"资金流向数据: {latest_data}")
        
        # 确保至少有时间戳和主力净流入两个数据点
        if len(latest_data) >= 2:
            # 创建基本数据结构
            processed_data = {
                'timestamp': datetime.now(),
                'main_net_inflow': 0,
                'retail_net_inflow': 0,
                'super_large_net_inflow': 0,
                'large_net_inflow': 0,
                'medium_net_inflow': 0,
                'small_net_inflow': 0,
            }
            
            # 根据数据长度填充不同的字段
            if len(latest_data) >= 2 and latest_data[1] != '-':
                processed_data['main_net_inflow'] = float(latest_data[1])
            
            if len(latest_data) >= 3 and latest_data[2] != '-':
                processed_data['retail_net_inflow'] = float(latest_data[2])
            
            if len(latest_data) >= 4 and latest_data[3] != '-':
                processed_data['super_large_net_inflow'] = float(latest_data[3])
            
            if len(latest_data) >= 5 and latest_data[4] != '-':
                processed_data['large_net_inflow'] = float(latest_data[4])
            
            if len(latest_data) >= 6 and latest_data[5] != '-':
                processed_data['medium_net_inflow'] = float(latest_data[5])
            
            if len(latest_data) >= 7 and latest_data[6] != '-':
                processed_data['small_net_inflow'] = float(latest_data[6])
            
            # 如果散户数据为0但有中小单数据，计算散户资金
            if processed_data['retail_net_inflow'] == 0 and (processed_data['medium_net_inflow'] != 0 or processed_data['small_net_inflow'] != 0):
                processed_data['retail_net_inflow'] = processed_data['medium_net_inflow'] + processed_data['small_net_inflow']
            
            return processed_data
    except Exception as e:
        st.warning(f"处理资金流向数据出错: {str(e)}")
        # 返回零值数据而不是None，确保图表能够显示
        return {
            'timestamp': datetime.now(),
            'main_net_inflow': 0,
            'retail_net_inflow': 0,
            'super_large_net_inflow': 0,
            'large_net_inflow': 0,
            'medium_net_inflow': 0,
            'small_net_inflow': 0,
        }
    
    return None

# 初始化或获取历史数据
def get_historical_data():
    if 'price_history' not in st.session_state or clear_data:
        st.session_state.price_history = pd.DataFrame(columns=[
            'timestamp', 'price', 'change', 'change_percent', 'volume', 'amount', 'open', 'high', 'low'
        ])
    
    if 'flow_history' not in st.session_state or clear_data:
        st.session_state.flow_history = pd.DataFrame(columns=[
            'timestamp', 'main_net_inflow', 'retail_net_inflow', 'super_large_net_inflow', 
            'large_net_inflow', 'medium_net_inflow', 'small_net_inflow'
        ])
    
    return st.session_state.price_history, st.session_state.flow_history

# 更新历史数据
def update_historical_data(price_data, flow_data):
    # 获取现有历史数据
    price_history, flow_history = get_historical_data()
    
    # 添加新的价格数据
    if price_data:
        price_history = pd.concat([
            price_history, 
            pd.DataFrame([price_data])
        ], ignore_index=True)
    
    # 添加新的资金流向数据
    if flow_data:
        flow_history = pd.concat([
            flow_history, 
            pd.DataFrame([flow_data])
        ], ignore_index=True)
    
    # 清理过旧的数据
    now = datetime.now()
    cutoff_time = now - timedelta(minutes=display_minutes)
    
    price_history = price_history[price_history['timestamp'] >= cutoff_time]
    flow_history = flow_history[flow_history['timestamp'] >= cutoff_time]
    
    # 更新会话状态
    st.session_state.price_history = price_history
    st.session_state.flow_history = flow_history
    
    return price_history, flow_history

# 创建股价走势图表
def create_price_chart(price_history):
    if price_history.empty:
        return go.Figure()
    
    # 创建包含两个子图的组合图表(股价和成交量)
    fig = make_subplots(rows=2, cols=1, 
                         shared_xaxes=True, 
                         vertical_spacing=0.1, 
                         row_heights=[0.7, 0.3],
                         subplot_titles=("股价走势", "成交量"))
    
    # 添加蜡烛图
    fig.add_trace(
        go.Candlestick(
            x=price_history['timestamp'],
            open=price_history['open'],
            high=price_history['high'],
            low=price_history['low'],
            close=price_history['price'],
            name="股价"
        ),
        row=1, col=1
    )
    
    # 添加成交量柱状图
    colors = ['red' if x >= 0 else 'green' for x in price_history['change']]
    fig.add_trace(
        go.Bar(
            x=price_history['timestamp'],
            y=price_history['volume'],
            name="成交量",
            marker_color=colors
        ),
        row=2, col=1
    )
    
    # 更新布局
    fig.update_layout(
        title="实时股价走势图",
        height=600,
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # 隐藏周末
                dict(bounds=[16, 9], pattern="hour")  # 隐藏非交易时间
            ]
        )
    )
    
    # 更新y轴标题
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    
    return fig

# 创建资金流向图表
def create_flow_chart(flow_history):
    if flow_history.empty:
        return go.Figure()
    
    # 创建包含两个子图的组合图表
    fig = make_subplots(rows=2, cols=1, 
                        shared_xaxes=True, 
                        vertical_spacing=0.1,
                        row_heights=[0.5, 0.5],
                        subplot_titles=("主力vs散户资金净流入", "大中小单资金流向"))
    
    # 添加主力和散户净流入折线图
    fig.add_trace(
        go.Scatter(
            x=flow_history['timestamp'],
            y=flow_history['main_net_inflow'],
            mode='lines',
            name="主力净流入",
            line=dict(color='red')
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=flow_history['timestamp'],
            y=flow_history['retail_net_inflow'],
            mode='lines',
            name="散户净流入",
            line=dict(color='blue')
        ),
        row=1, col=1
    )
    
    # 添加零线
    fig.add_trace(
        go.Scatter(
            x=[flow_history['timestamp'].min(), flow_history['timestamp'].max()],
            y=[0, 0],
            mode='lines',
            line=dict(color='black', dash='dash'),
            name="零线",
            showlegend=False
        ),
        row=1, col=1
    )
    
    # 添加大中小单资金流向
    fig.add_trace(
        go.Scatter(
            x=flow_history['timestamp'],
            y=flow_history['super_large_net_inflow'],
            mode='lines',
            name="超大单",
            line=dict(color='darkred')
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=flow_history['timestamp'],
            y=flow_history['large_net_inflow'],
            mode='lines',
            name="大单",
            line=dict(color='red')
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=flow_history['timestamp'],
            y=flow_history['medium_net_inflow'],
            mode='lines',
            name="中单",
            line=dict(color='purple')
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=flow_history['timestamp'],
            y=flow_history['small_net_inflow'],
            mode='lines',
            name="小单",
            line=dict(color='blue')
        ),
        row=2, col=1
    )
    
    # 添加零线
    fig.add_trace(
        go.Scatter(
            x=[flow_history['timestamp'].min(), flow_history['timestamp'].max()],
            y=[0, 0],
            mode='lines',
            line=dict(color='black', dash='dash'),
            showlegend=False
        ),
        row=2, col=1
    )
    
    # 更新布局
    fig.update_layout(
        title="实时资金流向分析",
        height=600,
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # 隐藏周末
                dict(bounds=[16, 9], pattern="hour")  # 隐藏非交易时间
            ]
        )
    )
    
    # 更新y轴标题
    fig.update_yaxes(title_text="净流入(万元)", row=1, col=1)
    fig.update_yaxes(title_text="净流入(万元)", row=2, col=1)
    
    return fig

# 创建累计资金流向柱状图
def create_flow_summary_chart(flow_history):
    if flow_history.empty:
        return go.Figure()
    
    # 计算累计资金流入
    summary = {
        '主力资金': flow_history['main_net_inflow'].sum(),
        '散户资金': flow_history['retail_net_inflow'].sum(),
        '超大单': flow_history['super_large_net_inflow'].sum(),
        '大单': flow_history['large_net_inflow'].sum(),
        '中单': flow_history['medium_net_inflow'].sum(),
        '小单': flow_history['small_net_inflow'].sum()
    }
    
    # 创建柱状图
    categories = list(summary.keys())
    values = list(summary.values())
    colors = ['red', 'blue', 'darkred', 'red', 'purple', 'blue']
    
    # 根据正负值设置颜色
    bar_colors = ['red' if v >= 0 else 'green' for v in values]
    
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=categories,
            y=values,
            marker_color=bar_colors,
            text=[f"{v:.2f}万" for v in values],
            textposition='auto'
        )
    )
    
    fig.update_layout(
        title="累计资金流向汇总(万元)",
        height=400,
        yaxis_title="累计净流入(万元)"
    )
    
    return fig
    
# 主应用逻辑
def main():
    # 获取股票名称
    stock_name = get_stock_name(stock_code)
    
    # 创建标题
    st.header(f"{stock_name}({stock_code}) 实时行情与资金流向")
    
    # 创建容器进行实时更新
    price_container = st.container()
    col1, col2 = st.columns(2)
    flow_container = col1.container()
    summary_container = col2.container()
    
    # 显示实时数据的容器
    info_container = st.container()
    
    # 创建占位图表
    if 'chart_iteration' not in st.session_state:
        st.session_state.chart_iteration = 0
    
    # 主循环
    while is_running:
        try:
            # 增加迭代计数
            st.session_state.chart_iteration += 1
            current_iter = st.session_state.chart_iteration
            
            # 获取实时数据
            quote_data = get_eastmoney_realtime_quote(stock_code)
            flow_data = get_eastmoney_capital_flow(stock_code)
            
            # 处理数据
            price_info = process_quote_data(quote_data)
            flow_info = process_flow_data(flow_data)
            
            # 更新历史数据
            price_history, flow_history = update_historical_data(price_info, flow_info)
            
            # 实时数据展示
            with info_container:
                if price_info:
                    cols = st.columns(5)
                    cols[0].metric("当前价", f"{price_info['price']:.2f}", f"{price_info['change_percent']:.2f}%")
                    cols[1].metric("涨跌额", f"{price_info['change']:.2f}")
                    cols[2].metric("成交量", f"{price_info['volume']:.0f}手")
                    cols[3].metric("成交额", f"{price_info['amount']:.2f}万")
                    cols[4].metric("更新时间", datetime.now().strftime("%H:%M:%S"))
                
                if flow_info:
                    cols = st.columns(3)
                    cols[0].metric("主力净流入", f"{flow_info['main_net_inflow']:.2f}万")
                    cols[1].metric("散户净流入", f"{flow_info['retail_net_inflow']:.2f}万")
                    cols[2].metric("超大单净流入", f"{flow_info['super_large_net_inflow']:.2f}万")
            
            # 更新图表，为每个图表提供唯一key
            with price_container:
                price_chart = create_price_chart(price_history)
                st.plotly_chart(price_chart, use_container_width=True, key=f"price_chart_{current_iter}")
            
            with flow_container:
                flow_chart = create_flow_chart(flow_history)
                st.plotly_chart(flow_chart, use_container_width=True, key=f"flow_chart_{current_iter}")
            
            with summary_container:
                summary_chart = create_flow_summary_chart(flow_history)
                st.plotly_chart(summary_chart, use_container_width=True, key=f"summary_chart_{current_iter}")
            
            # 休眠指定时间
            time.sleep(update_interval)
            
        except Exception as e:
            st.error(f"数据更新出错: {str(e)}")
            time.sleep(update_interval)
            continue

if __name__ == "__main__":
    main() 