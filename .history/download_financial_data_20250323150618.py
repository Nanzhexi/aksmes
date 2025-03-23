import akshare as ak
import pandas as pd
import os
from datetime import datetime

# 创建保存数据的文件夹
data_dir = "financial_data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# 获取当前日期作为文件名一部分
current_date = datetime.now().strftime("%Y%m%d")

def get_stock_prefix(code):
    """根据股票代码判断其所属交易所"""
    code = str(code)
    if code.startswith(('0', '3')):
        return "sz"  # 深交所
    elif code.startswith(('6', '9')):
        return "sh"  # 上交所
    else:
        raise ValueError(f"无法识别的股票代码格式: {code}")

# 请输入股票代码
stock_code = input("请输入股票代码（例如：000001 或 600000）：")
stock_code = stock_code.strip()

try:
    # 获取股票前缀
    prefix = get_stock_prefix(stock_code)
    full_code = prefix + stock_code
    
    # 获取股票名称，以便在输出中显示
    stock_info = ak.stock_individual_info_em(symbol=stock_code)
    stock_name = stock_info.loc[0, "股票简称"] if not stock_info.empty else "未知"
    
    print(f"\n开始下载 {stock_code}({stock_name}) 的财务报表...\n")
    
    # 定义要下载的报表类型
    report_types = ["资产负债表", "利润表", "现金流量表"]
    
    for report_type in report_types:
        try:
            print(f"正在下载 {stock_name}({stock_code}) 的{report_type}...")
            df = ak.stock_financial_report_sina(stock=full_code, symbol=report_type)
            
            # 转换报表为最近10年的数据
            if not df.empty:
                # 如果数据量超过10年，只保留最近10年的数据
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
                print(f"{report_type}已保存至: {file_path}")
                
                # 打印数据统计信息
                print(f"  - 行数: {df.shape[0]}")
                print(f"  - 列数: {df.shape[1]}")
                print(f"  - 时间范围: {df.columns[-1]} 至 {df.columns[1]}")
            else:
                print(f"警告: {report_type}没有数据")
                
        except Exception as e:
            print(f"下载{report_type}时出错: {e}")
    
    print("\n所有财务报表下载完成！")
    print(f"文件保存在 {os.path.abspath(data_dir)} 目录下")

except Exception as e:
    print(f"程序执行出错: {e}") 