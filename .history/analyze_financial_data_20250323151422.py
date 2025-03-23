import pandas as pd
import os
import glob
import matplotlib.pyplot as plt
from datetime import datetime

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 定义数据目录
data_dir = "financial_data"

def list_available_stocks():
    """列出已下载的股票代码"""
    files = glob.glob(os.path.join(data_dir, "*_balance_sheet_*.csv"))
    stocks = {}
    
    for file in files:
        # 从文件名中提取股票代码
        basename = os.path.basename(file)
        parts = basename.split('_')
        if len(parts) >= 3:
            stock_code = parts[0]
            date_str = parts[2].replace('.csv', '')
            if stock_code not in stocks or stocks[stock_code] < date_str:
                stocks[stock_code] = date_str
    
    return stocks

def load_financial_statements(stock_code, date_str=None):
    """加载指定股票的财务报表"""
    if date_str is None:
        # 如果没有指定日期，查找最新的文件
        bs_files = glob.glob(os.path.join(data_dir, f"{stock_code}_balance_sheet_*.csv"))
        is_files = glob.glob(os.path.join(data_dir, f"{stock_code}_income_statement_*.csv"))
        cf_files = glob.glob(os.path.join(data_dir, f"{stock_code}_cash_flow_*.csv"))
        
        if not bs_files or not is_files or not cf_files:
            print(f"错误: 未找到股票 {stock_code} 的完整财务报表数据")
            return None, None, None
        
        # 按日期排序并获取最新的文件
        bs_file = sorted(bs_files)[-1]
        is_file = sorted(is_files)[-1]
        cf_file = sorted(cf_files)[-1]
    else:
        # 使用指定的日期
        bs_file = os.path.join(data_dir, f"{stock_code}_balance_sheet_{date_str}.csv")
        is_file = os.path.join(data_dir, f"{stock_code}_income_statement_{date_str}.csv")
        cf_file = os.path.join(data_dir, f"{stock_code}_cash_flow_{date_str}.csv")
    
    # 检查文件是否存在
    if not os.path.exists(bs_file) or not os.path.exists(is_file) or not os.path.exists(cf_file):
        print(f"错误: 未找到股票 {stock_code} 的完整财务报表数据")
        return None, None, None
    
    # 读取数据
    try:
        balance_sheet = pd.read_csv(bs_file, encoding="utf-8-sig")
        income_statement = pd.read_csv(is_file, encoding="utf-8-sig")
        cash_flow = pd.read_csv(cf_file, encoding="utf-8-sig")
        
        print(f"已加载 {stock_code} 的财务报表数据:")
        print(f"  - 资产负债表: {os.path.basename(bs_file)}")
        print(f"  - 利润表: {os.path.basename(is_file)}")
        print(f"  - 现金流量表: {os.path.basename(cf_file)}")
        
        return balance_sheet, income_statement, cash_flow
    except Exception as e:
        print(f"加载数据时出错: {e}")
        return None, None, None

def analyze_balance_sheet(balance_sheet):
    """分析资产负债表数据"""
    if balance_sheet is None or balance_sheet.empty:
        print("无法分析资产负债表：数据为空")
        return
    
    # 转置数据，使日期成为索引
    # 第一列通常是项目名称，从第二列开始是日期数据
    dates = balance_sheet.columns[1:]
    
    # 尝试查找关键指标
    asset_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('总资产|资产总计|资产负债表', na=False)]
    liability_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('总负债|负债合计|负债总计', na=False)]
    equity_rows = balance_sheet[balance_sheet.iloc[:, 0].str.contains('所有者权益|股东权益|净资产', na=False)]
    
    # 如果没有找到，尝试按位置获取
    if asset_rows.empty and balance_sheet.shape[0] > 10:
        print("未找到标准的资产总计行，尝试按位置获取...")
        # 通常资产总计出现在前几行
        for i in range(min(10, balance_sheet.shape[0])):
            if '资产' in str(balance_sheet.iloc[i, 0]):
                asset_rows = balance_sheet.iloc[[i]]
                break
    
    if liability_rows.empty and balance_sheet.shape[0] > 20:
        print("未找到标准的负债总计行，尝试按位置获取...")
        # 通常负债总计出现在中间位置
        mid_point = balance_sheet.shape[0] // 2
        for i in range(mid_point-5, min(mid_point+5, balance_sheet.shape[0])):
            if '负债' in str(balance_sheet.iloc[i, 0]):
                liability_rows = balance_sheet.iloc[[i]]
                break
    
    if equity_rows.empty and balance_sheet.shape[0] > 20:
        print("未找到标准的股东权益行，尝试按位置获取...")
        # 通常股东权益出现在底部位置
        for i in range(balance_sheet.shape[0]-10, balance_sheet.shape[0]):
            if '权益' in str(balance_sheet.iloc[i, 0]) or '净资产' in str(balance_sheet.iloc[i, 0]):
                equity_rows = balance_sheet.iloc[[i]]
                break
    
    # 打印分析结果
    print("\n资产负债表分析:")
    
    if not asset_rows.empty:
        asset_row = asset_rows.iloc[0]
        print(f"  - 指标: {asset_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(asset_row) and pd.notna(asset_row.iloc[i+1]) and asset_row.iloc[i+1]:
                print(f"    {date}: {asset_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到资产总计数据")
    
    if not liability_rows.empty:
        liability_row = liability_rows.iloc[0]
        print(f"  - 指标: {liability_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(liability_row) and pd.notna(liability_row.iloc[i+1]) and liability_row.iloc[i+1]:
                print(f"    {date}: {liability_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到负债总计数据")
    
    if not equity_rows.empty:
        equity_row = equity_rows.iloc[0]
        print(f"  - 指标: {equity_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(equity_row) and pd.notna(equity_row.iloc[i+1]) and equity_row.iloc[i+1]:
                print(f"    {date}: {equity_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到股东权益数据")
    
    # 生成图表
    if not asset_rows.empty and not liability_rows.empty:
        try:
            plt.figure(figsize=(12, 6))
            
            # 准备数据
            asset_data = []
            liability_data = []
            equity_data = []
            plot_dates = []
            
            asset_row = asset_rows.iloc[0]
            liability_row = liability_rows.iloc[0]
            equity_row = equity_rows.iloc[0] if not equity_rows.empty else None
            
            for i, date in enumerate(dates):
                if i+1 < len(asset_row) and pd.notna(asset_row.iloc[i+1]) and asset_row.iloc[i+1]:
                    asset_val = asset_row.iloc[i+1]
                    # 检查负债和权益数据是否可用
                    if i+1 < len(liability_row) and pd.notna(liability_row.iloc[i+1]) and liability_row.iloc[i+1]:
                        liability_val = liability_row.iloc[i+1]
                        
                        # 只在两者都有值时添加
                        asset_data.append(asset_val)
                        liability_data.append(liability_val)
                        plot_dates.append(date)
                        
                        # 如果有权益数据，也添加
                        if equity_row is not None and i+1 < len(equity_row) and pd.notna(equity_row.iloc[i+1]) and equity_row.iloc[i+1]:
                            equity_data.append(equity_row.iloc[i+1])
                        elif len(asset_data) > 0 and len(liability_data) > 0:
                            # 如果没有直接的权益数据，用资产减负债
                            equity_data.append(asset_data[-1] - liability_data[-1])
            
            # 反转数据，使其按时间顺序显示
            asset_data.reverse()
            liability_data.reverse()
            equity_data.reverse()
            plot_dates.reverse()
            
            # 转换为亿元
            asset_data = [x/100000000 for x in asset_data]
            liability_data = [x/100000000 for x in liability_data]
            equity_data = [x/100000000 for x in equity_data]
            
            # 绘制图表
            plt.plot(plot_dates, asset_data, 'b-', label='总资产')
            plt.plot(plot_dates, liability_data, 'r-', label='总负债')
            plt.plot(plot_dates, equity_data, 'g-', label='股东权益')
            
            plt.title('资产负债变化趋势（单位：亿元）')
            plt.xlabel('报告期')
            plt.ylabel('金额（亿元）')
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 保存图表
            chart_dir = "financial_charts"
            if not os.path.exists(chart_dir):
                os.makedirs(chart_dir)
            
            current_date = datetime.now().strftime("%Y%m%d")
            chart_file = os.path.join(chart_dir, f"{stock_code}_balance_sheet_chart_{current_date}.png")
            plt.savefig(chart_file)
            print(f"\n资产负债趋势图已保存至: {chart_file}")
            plt.close()
        
        except Exception as e:
            print(f"生成图表时出错: {e}")

def analyze_income_statement(income_statement):
    """分析利润表数据"""
    if income_statement is None or income_statement.empty:
        print("无法分析利润表：数据为空")
        return
    
    # 转置数据，使日期成为索引
    dates = income_statement.columns[1:]
    
    # 尝试查找关键指标
    revenue_rows = income_statement[income_statement.iloc[:, 0].str.contains('营业收入|营业总收入', na=False)]
    profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('净利润|利润总额', na=False)]
    gross_profit_rows = income_statement[income_statement.iloc[:, 0].str.contains('毛利|毛利润|营业利润', na=False)]
    
    # 打印分析结果
    print("\n利润表分析:")
    
    if not revenue_rows.empty:
        revenue_row = revenue_rows.iloc[0]
        print(f"  - 指标: {revenue_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(revenue_row) and pd.notna(revenue_row.iloc[i+1]) and revenue_row.iloc[i+1]:
                print(f"    {date}: {revenue_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到营业收入数据")
    
    if not profit_rows.empty:
        profit_row = profit_rows.iloc[0]
        print(f"  - 指标: {profit_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(profit_row) and pd.notna(profit_row.iloc[i+1]) and profit_row.iloc[i+1]:
                print(f"    {date}: {profit_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到净利润数据")
    
    # 生成图表
    if not revenue_rows.empty and not profit_rows.empty:
        try:
            plt.figure(figsize=(12, 6))
            
            # 准备数据
            revenue_data = []
            profit_data = []
            gross_profit_data = []
            plot_dates = []
            
            revenue_row = revenue_rows.iloc[0]
            profit_row = profit_rows.iloc[0]
            gross_profit_row = gross_profit_rows.iloc[0] if not gross_profit_rows.empty else None
            
            for i, date in enumerate(dates):
                if i+1 < len(revenue_row) and pd.notna(revenue_row.iloc[i+1]) and revenue_row.iloc[i+1]:
                    if i+1 < len(profit_row) and pd.notna(profit_row.iloc[i+1]) and profit_row.iloc[i+1]:
                        revenue_data.append(revenue_row.iloc[i+1])
                        profit_data.append(profit_row.iloc[i+1])
                        plot_dates.append(date)
                        
                        # 如果有毛利数据，也添加
                        if gross_profit_row is not None and i+1 < len(gross_profit_row) and pd.notna(gross_profit_row.iloc[i+1]) and gross_profit_row.iloc[i+1]:
                            gross_profit_data.append(gross_profit_row.iloc[i+1])
            
            # 反转数据，使其按时间顺序显示
            revenue_data.reverse()
            profit_data.reverse()
            if gross_profit_data:
                gross_profit_data.reverse()
            plot_dates.reverse()
            
            # 转换为亿元
            revenue_data = [x/100000000 for x in revenue_data]
            profit_data = [x/100000000 for x in profit_data]
            if gross_profit_data:
                gross_profit_data = [x/100000000 for x in gross_profit_data]
            
            # 绘制图表
            plt.plot(plot_dates, revenue_data, 'b-', label='营业收入')
            plt.plot(plot_dates, profit_data, 'r-', label='净利润')
            if gross_profit_data:
                plt.plot(plot_dates, gross_profit_data, 'g-', label='毛利润')
            
            plt.title('收入利润变化趋势（单位：亿元）')
            plt.xlabel('报告期')
            plt.ylabel('金额（亿元）')
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 保存图表
            chart_dir = "financial_charts"
            if not os.path.exists(chart_dir):
                os.makedirs(chart_dir)
            
            current_date = datetime.now().strftime("%Y%m%d")
            chart_file = os.path.join(chart_dir, f"{stock_code}_income_statement_chart_{current_date}.png")
            plt.savefig(chart_file)
            print(f"\n收入利润趋势图已保存至: {chart_file}")
            plt.close()
        
        except Exception as e:
            print(f"生成图表时出错: {e}")

def analyze_cash_flow(cash_flow):
    """分析现金流量表数据"""
    if cash_flow is None or cash_flow.empty:
        print("无法分析现金流量表：数据为空")
        return
    
    # 转置数据，使日期成为索引
    dates = cash_flow.columns[1:]
    
    # 尝试查找关键指标
    operating_rows = cash_flow[cash_flow.iloc[:, 0].str.contains('经营活动.*现金流量|经营活动产生的现金流量净额', na=False)]
    investing_rows = cash_flow[cash_flow.iloc[:, 0].str.contains('投资活动.*现金流量|投资活动产生的现金流量净额', na=False)]
    financing_rows = cash_flow[cash_flow.iloc[:, 0].str.contains('筹资活动.*现金流量|筹资活动产生的现金流量净额', na=False)]
    
    # 打印分析结果
    print("\n现金流量表分析:")
    
    if not operating_rows.empty:
        operating_row = operating_rows.iloc[0]
        print(f"  - 指标: {operating_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(operating_row) and pd.notna(operating_row.iloc[i+1]) and operating_row.iloc[i+1]:
                print(f"    {date}: {operating_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到经营活动现金流量数据")
    
    if not investing_rows.empty:
        investing_row = investing_rows.iloc[0]
        print(f"  - 指标: {investing_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(investing_row) and pd.notna(investing_row.iloc[i+1]) and investing_row.iloc[i+1]:
                print(f"    {date}: {investing_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到投资活动现金流量数据")
    
    if not financing_rows.empty:
        financing_row = financing_rows.iloc[0]
        print(f"  - 指标: {financing_row.iloc[0]}")
        for i, date in enumerate(dates):
            if i+1 < len(financing_row) and pd.notna(financing_row.iloc[i+1]) and financing_row.iloc[i+1]:
                print(f"    {date}: {financing_row.iloc[i+1]:,.2f}")
    else:
        print("  - 未找到筹资活动现金流量数据")
    
    # 生成图表
    if not operating_rows.empty and not investing_rows.empty and not financing_rows.empty:
        try:
            plt.figure(figsize=(12, 6))
            
            # 准备数据
            operating_data = []
            investing_data = []
            financing_data = []
            plot_dates = []
            
            operating_row = operating_rows.iloc[0]
            investing_row = investing_rows.iloc[0]
            financing_row = financing_rows.iloc[0]
            
            for i, date in enumerate(dates):
                if (i+1 < len(operating_row) and pd.notna(operating_row.iloc[i+1]) and
                    i+1 < len(investing_row) and pd.notna(investing_row.iloc[i+1]) and
                    i+1 < len(financing_row) and pd.notna(financing_row.iloc[i+1])):
                    
                    operating_data.append(operating_row.iloc[i+1])
                    investing_data.append(investing_row.iloc[i+1])
                    financing_data.append(financing_row.iloc[i+1])
                    plot_dates.append(date)
            
            # 反转数据，使其按时间顺序显示
            operating_data.reverse()
            investing_data.reverse()
            financing_data.reverse()
            plot_dates.reverse()
            
            # 转换为亿元
            operating_data = [x/100000000 for x in operating_data]
            investing_data = [x/100000000 for x in investing_data]
            financing_data = [x/100000000 for x in financing_data]
            
            # 绘制图表
            plt.plot(plot_dates, operating_data, 'b-', label='经营活动现金流量')
            plt.plot(plot_dates, investing_data, 'r-', label='投资活动现金流量')
            plt.plot(plot_dates, financing_data, 'g-', label='筹资活动现金流量')
            
            plt.title('现金流量变化趋势（单位：亿元）')
            plt.xlabel('报告期')
            plt.ylabel('金额（亿元）')
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 保存图表
            chart_dir = "financial_charts"
            if not os.path.exists(chart_dir):
                os.makedirs(chart_dir)
            
            current_date = datetime.now().strftime("%Y%m%d")
            chart_file = os.path.join(chart_dir, f"{stock_code}_cash_flow_chart_{current_date}.png")
            plt.savefig(chart_file)
            print(f"\n现金流量趋势图已保存至: {chart_file}")
            plt.close()
        
        except Exception as e:
            print(f"生成图表时出错: {e}")

if __name__ == "__main__":
    # 列出可用的股票
    available_stocks = list_available_stocks()
    
    if not available_stocks:
        print("未找到任何已下载的财务数据。请先运行 download_financial_data.py 下载财务数据。")
        exit(1)
    
    print("已下载的股票财务数据:")
    for i, (code, date) in enumerate(available_stocks.items(), 1):
        print(f"{i}. 股票代码: {code}, 数据日期: {date}")
    
    # 让用户选择股票
    while True:
        choice = input("\n请选择要分析的股票序号（输入q退出）: ").strip()
        
        if choice.lower() == 'q':
            break
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_stocks):
                stock_code = list(available_stocks.keys())[choice_idx]
                date_str = available_stocks[stock_code]
                
                print(f"\n正在分析股票 {stock_code} 的财务数据...")
                
                # 加载财务报表
                balance_sheet, income_statement, cash_flow = load_financial_statements(stock_code, date_str)
                
                if balance_sheet is not None and income_statement is not None and cash_flow is not None:
                    # 分析数据
                    analyze_balance_sheet(balance_sheet)
                    analyze_income_statement(income_statement)
                    analyze_cash_flow(cash_flow)
                    
                    print("\n分析完成！")
                else:
                    print(f"无法加载股票 {stock_code} 的完整财务数据，请检查数据文件是否存在。")
            else:
                print("无效的选择，请重新输入。")
        except ValueError:
            print("请输入有效的数字。") 