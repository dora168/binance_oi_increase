import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from io import StringIO

# ================= 核心配置区 =================
DATA_SOURCE = "http://43.156.132.4:8080/oi_analysis.csv"
ITEMS_PER_PAGE = 20  
MAX_TOTAL_ITEMS = 100 
# ============================================

def format_money(num):
    try:
        num = float(num)
        if num >= 1_000_000_000: return f"{num/1_000_000_000:.2f}B"
        if num >= 1_000_000: return f"{num/1_000_000:.2f}M"
        if num >= 1_000: return f"{num/1_000:.1f}K"
        return f"{num:.1f}"
    except:
        return str(num)

def load_data(url):
    try:
        # 增加超时容错
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return pd.DataFrame()
        content = response.content.decode('utf-8-sig')
        return pd.read_csv(StringIO(content))
    except:
        return pd.DataFrame()

def render_tradingview_widget(symbol, height=500):
    clean_symbol = symbol.upper().strip()
    tv_symbol = f"BINANCE:{clean_symbol}.P"
    container_id = f"tv_{clean_symbol}"
    html_code = f"""
    <div class="tradingview-widget-container" style="height: {height}px; width: 100%;">
      <div id="{container_id}" style="height: 100%; width: 100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true, "symbol": "{tv_symbol}", "interval": "60",
        "timezone": "Asia/Shanghai", "theme": "light", "style": "1",
        "locale": "zh_CN", "enable_publishing": false, "hide_top_toolbar": true,
        "container_id": "{container_id}",
        "studies": ["MASimple@tv-basicstudies", "STD;Fund_crypto_open_interest"],
        "disabled_features": ["header_symbol_search", "header_compare", "use_localstorage_for_settings", "timeframes_toolbar", "volume_force_overlay"]
      }});
      </script>
    </div>
    """
    components.html(html_code, height=height, scrolling=False)

def main():
    st.set_page_config(layout="wide", page_title="全市场持仓增量榜单")
    st.title("🚀 全市场持仓增量市值排名 (Top 100)")

    with st.spinner("正在获取全市场数据..."):
        df = load_data(DATA_SOURCE)
    
    if df.empty:
        st.error("无法加载数据，请检查服务器连接或日志。")
        return

    try:
        # 1. 计算排序指标：(最新OI - 三天最小OI) * 价格
        if 'open_interest' in df.columns and 'oi_min_3d' in df.columns:
            df['oi_delta_value'] = (df['open_interest'] - df['oi_min_3d']) * df['price']
        else:
            # 容错：如果缺少列则使用预设增量列
            df['oi_delta_value'] = df.get('increase_amount_usdt', 0)

        # 2. 全市场排序（移除 > 0.03 的筛选条件）
        # 我们保留一份副本以便操作
        full_market_df = df.copy()
        
        # 3. 按增量市值降序排列并取前 100
        sorted_df = full_market_df.sort_values(by='oi_delta_value', ascending=False).head(MAX_TOTAL_ITEMS)
        
        # 计算流通市值
        if 'circ_supply' in sorted_df.columns:
            sorted_df['market_cap'] = sorted_df['circ_supply'] * sorted_df['price']
        else:
            sorted_df['market_cap'] = 0

    except Exception as e:
        st.error(f"排序处理错误: {e}")
        return

    actual_total = len(sorted_df)
    total_pages = max(1, (actual_total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if 'page' not in st.session_state:
        st.session_state.page = 1

    start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, actual_total)
    current_batch = sorted_df.iloc[start_idx:end_idx]

    # --- 顶栏统计 ---
    st.info(f"💡 当前已按全市场持仓增量市值降序排列。已加载前 {actual_total} 名标的。")

    cols = st.columns(2)
    for i, (_, row) in enumerate(current_batch.iterrows()):
        with cols[i % 2]:
            symbol = row['symbol']
            rank = start_idx + i + 1
            oi_change_pct = row.get('increase_ratio', 0) * 100
            
            # 动态颜色：增量为正则红，负则绿（针对全市场排名可能出现负值的情况）
            delta_color = "#d32f2f" if row['oi_delta_value'] >= 0 else "#2e7d32"
            bg_color = "#ffebee" if row['oi_delta_value'] >= 0 else "#e8f5e9"

            st.markdown(f"""
            <div style="background-color:#ffffff; padding:15px; border-radius:10px; border:1px solid #e0e0e0; margin-bottom:10px;">
                <div style="display:flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size:1.4em; font-weight:bold; color:{delta_color};">#{rank}</span>
                        <span style="font-size:1.4em; font-weight:bold; margin-left:10px;">{symbol}</span>
                    </div>
                    <span style="font-size:1.1em; font-weight:900; color:{delta_color}; background-color:{bg_color}; padding:3px 12px; border-radius:6px;">
                        OI {oi_change_pct:+.2f}%
                    </span>
                </div>
                <div style="margin-top:10px; display:flex; gap:30px; font-size:0.95em; color:#444;">
                    <span>🔥 <b>持仓增量市值:</b> <span style="color:{delta_color}; font-weight:bold;">${format_money(row['oi_delta_value'])}</span></span>
                    <span>🌍 <b>流通市值:</b> ${format_money(row.get('market_cap', 0))}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            render_tradingview_widget(symbol)

    # --- 底部翻页 ---
    st.markdown("---")
    _, footer_col, _ = st.columns([2, 1, 2])
    with footer_col:
        if total_pages > 1:
            new_page = st.number_input(f"页码 (共 {total_pages} 页)", 1, total_pages, st.session_state.page)
            if new_page != st.session_state.page:
                st.session_state.page = new_page
                st.rerun()

if __name__ == "__main__":
    main()
