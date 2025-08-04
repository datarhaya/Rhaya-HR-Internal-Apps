import streamlit as st
from st_pages import add_page_title, get_nav_from_toml, hide_pages
import pathlib
import pandas as pd

st.set_page_config(initial_sidebar_state="collapsed", layout="wide", page_icon="🎬", page_title="Rhaya HR Internal App")

# Initialize authentication check early
from utils.auth import check_authentication
check_authentication()

with open( pathlib.Path("app/styles.css") ) as f:
    st.markdown(f'<style>{f.read()}</style>' , unsafe_allow_html= True)

st.markdown("""
<style>
    [data-testid=stSidebar] {
        background-color: #0D2A52;
    }
    /* Change the text color inside sidebar selectbox */
    [data-testid=stSidebar] .stSelectbox label {
        color: white;
    }
    [data-testid=stSidebar] .stSelectbox div[data-baseweb="select"] {
        color: white;
    }
</style>
""", unsafe_allow_html=True)

nav = get_nav_from_toml(".streamlit/pages.toml")

pg = st.navigation(nav)

add_page_title(pg)

pg.run()