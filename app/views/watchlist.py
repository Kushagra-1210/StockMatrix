import streamlit as st
from backend.data_fetcher import get_ticker_data

# Watchlist view logic for StockMatrix
def show_watchlist(st, user_prefs):
    st.subheader("👀 Watchlist")
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []
    st.markdown("Add stocks to your watchlist for quick access and monitoring.")
    new_ticker = st.text_input("Add Ticker to Watchlist", "", key="watchlist_add_input")
    if st.button("Add to Watchlist", key="watchlist_add_btn"):
        if new_ticker and new_ticker not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_ticker.upper())
    if st.session_state.watchlist:
        st.markdown("---")
        st.markdown("### Your Watchlist:")
        for ticker in st.session_state.watchlist:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{ticker}**")
                try:
                    data = get_ticker_data(ticker)
                    info = data.get("info", {})
                    price = info.get("currentPrice", "N/A")
                    currency = info.get("currency", "")
                    st.caption(f"Price: {price} {currency}")
                except Exception as e:
                    st.caption(f"Error fetching data: {str(e)}")
            with col2:
                if st.button(f"Remove", key=f"remove_{ticker}"):
                    st.session_state.watchlist.remove(ticker)
    else:
        st.info("Your watchlist is empty. Add tickers above.")
