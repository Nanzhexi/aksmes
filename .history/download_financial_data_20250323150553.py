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

# 请输入股票代码（例如：000001表示平安银行）
stock_code = input("请输入股票代码（例如：000001）：")

# 下载资产负债表
try:
    print(f"正在下载 {stock_code} 的资产负债表...")
    balance_sheet = ak.stock_financial_report_sina(stock="sz" + stock_code, symbol="资产负债表")
    balance_sheet_file = os.path.join(data_dir, f"{stock_code}_balance_sheet_{current_date}.csv")
    balance_sheet.to_csv(balance_sheet_file, index=False, encoding="utf-8-sig")
    print(f"资产负债表已保存至: {balance_sheet_file}")
except Exception as e:
    print(f"下载资产负债表时出错: {e}")

# 下载利润表
try:
    print(f"正在下载 {stock_code} 的利润表...")
    income_statement = ak.stock_financial_report_sina(stock="sz" + stock_code, symbol="利润表")
    income_statement_file = os.path.join(data_dir, f"{stock_code}_income_statement_{current_date}.csv")
    income_statement.to_csv(income_statement_file, index=False, encoding="utf-8-sig")
    print(f"利润表已保存至: {income_statement_file}")
except Exception as e:
    print(f"下载利润表时出错: {e}")

# 下载现金流量表
try:
    print(f"正在下载 {stock_code} 的现金流量表...")
    cash_flow = ak.stock_financial_report_sina(stock="sz" + stock_code, symbol="现金流量表")
    cash_flow_file = os.path.join(data_dir, f"{stock_code}_cash_flow_{current_date}.csv")
    cash_flow.to_csv(cash_flow_file, index=False, encoding="utf-8-sig")
    print(f"现金流量表已保存至: {cash_flow_file}")
except Exception as e:
    print(f"下载现金流量表时出错: {e}")

print("\n所有财务报表下载完成！") 