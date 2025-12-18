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
        response = requests.get(url, timeout=5)
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
        "studies": ["MASimple@tv-basicstudies", "STD;Fund_crypto_open_interest"],   #, "STD;Fund_long_short_ratio"
        "disabled_features": ["header_symbol_search", "header_compare", "use_localstorage_for_settings", "timeframes_toolbar", "volume_force_overlay"]
      }});
      </script>
    </div>
    """
    components.html(html_code, height=height, scrolling=False)

def main():
    st.set_page_config(layout="wide", page_title="主力建仓前100榜单")
    st.title("🚀 主力建仓监控 Top 100")

    with st.spinner("正在获取最新数据..."):
        df = load_data(DATA_SOURCE)
    
    if df.empty:
        st.error("数据加载失败。")
        return

    try:
        # 计算逻辑：(最新OI - 三天最小OI) * 价格
        if 'open_interest' in df.columns and 'oi_min_3d' in df.columns:
            df['oi_delta_value'] = (df['open_interest'] - df['oi_min_3d']) * df['price']
        else:
            df['oi_delta_value'] = df.get('increase_amount_usdt', 0)

        filtered_df = df[df['increase_ratio'] > 0.03].copy()
        filtered_df = filtered_df.sort_values(by='oi_delta_value', ascending=False).head(MAX_TOTAL_ITEMS)
        
        if 'circ_supply' in filtered_df.columns:
            filtered_df['market_cap'] = filtered_df['circ_supply'] * filtered_df['price']
    except Exception as e:
        st.error(f"处理错误: {e}")
        return

    actual_total = len(filtered_df)
    total_pages = max(1, (actual_total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if 'page' not in st.session_state:
        st.session_state.page = 1

    start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, actual_total)
    current_batch = filtered_df.iloc[start_idx:end_idx]

    cols = st.columns(2)
    for i, (_, row) in enumerate(current_batch.iterrows()):
        with cols[i % 2]:
            symbol = row['symbol']
            rank = start_idx + i + 1
            st.markdown(f"""
            <div style="background-color:#ffffff; padding:15px; border-radius:10px; border:1px solid #e0e0e0; margin-bottom:10px;">
                <div style="display:flex; justify-content: space-between; align-items: center;">
                    <div><span style="font-size:1.4em; font-weight:bold; color:#d32f2f;">#{rank}</span>
                    <span style="font-size:1.4em; font-weight:bold; margin-left:10px;">{symbol}</span></div>
                    <span style="font-size:1.1em; font-weight:900; color:#d32f2f; background-color:#ffebee; padding:3px 12px; border-radius:6px;">OI +{row['increase_ratio']*100:.2f}%</span>
                </div>
                <div style="margin-top:10px; display:flex; gap:30px; font-size:0.95em; color:#444;">
                    <span>🔥 <b>3日增量市值:</b> <span style="color:#d32f2f;">${format_money(row['oi_delta_value'])}</span></span>
                    <span>🌍 <b>流通市值:</b> ${format_money(row.get('market_cap', 0))}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            render_tradingview_widget(symbol)

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


