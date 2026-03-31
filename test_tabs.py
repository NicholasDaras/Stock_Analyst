"""Minimal test to debug blank tabs."""
import streamlit as st

st.set_page_config(page_title="Tab Test", layout="wide")

tab1, tab2, tab3 = st.tabs(["TAB A", "TAB B", "TAB C"])

with tab1:
    st.write("Tab A works")
    try:
        import pandas as pd
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        st.dataframe(df, width="stretch", hide_index=True)
        st.write("Dataframe rendered OK")
    except Exception as e:
        st.error(f"Dataframe error: {e}")

with tab2:
    st.write("Tab B works")
    try:
        st.markdown(
            '<div style="color:red; font-size:2rem;">HTML test</div>',
            unsafe_allow_html=True,
        )
        st.write("HTML rendered OK")
    except Exception as e:
        st.error(f"HTML error: {e}")

with tab3:
    st.write("Tab C works")
    try:
        from fred_data import fetch_macro_snapshot
        st.write(f"fred_data import OK")
    except Exception as e:
        st.error(f"fred_data import error: {e}")
    try:
        from edgar_data import get_insider_trading
        st.write(f"edgar_data import OK")
    except Exception as e:
        st.error(f"edgar_data import error: {e}")
    try:
        key = st.secrets.get("fred_api_key")
        st.write(f"FRED key loaded: {'yes' if key else 'no'}")
    except Exception as e:
        st.error(f"Secrets error: {e}")
