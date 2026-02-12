import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="VERSÃO NOVA - COM HISTÓRICO",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CONEXÃO SUPABASE
# ==============================================================================
# 👇 PREENCHA AQUI COM SEUS DADOS REAIS 👇
SUPABASE_URL = "https://lfgqxphittdatzknwkqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxmZ3F4cGhpdHRkYXR6a253a3F3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4NzYyNzUsImV4cCI6MjA4NjQ1MjI3NX0.fZSfStTC5GdnP0Md1O0ptq8dD84zV-8cgirqIQTNO4Y"

@st.cache_resource
def init_supabase():
    try:
        # Tenta pegar dos secrets (se houver), senão usa as variáveis acima
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except:
    st.error("Erro de conexão com Supabase. Verifique URL e KEY no código.")
    st.stop()

# ==============================================================================
# 3. ESTILO CSS
# ==============================================================================
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 4px; font-weight: bold; }
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #ff4b4b; color: white; border: none;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. FUNÇÕES DE LOGIN
# ==============================================================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''

def login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Login Nova Versão")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            btn = st.form_submit_button("Entrar")
            
        if btn:
            try:
                res = supabase.table('users').select("*").eq('username', user).eq('password', pwd).execute()
                if res.data:
                    data = res.data[0]
                    if data.get('approved'):
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = user
                        st.session_state['name'] = data.get('name', user)
                        st.rerun()
                    else:
                        st.warning("Usuário pendente de aprovação.")
                else:
                    st.error("Dados incorretos.")
            except Exception as e:
                st.error(f"Erro: {e}")

# ==============================================================================
# 5. APP PRINCIPAL
# ==============================================================================
if not st.session_state['logged_in']:
    login_screen()
else:
    # --- SIDEBAR SIMPLIFICADA ---
    with st.sidebar:
        st.success(f"Logado como: {st.session_state.get('name')}")
        if st.button("Sair do Sistema"):
            st.session_state['logged_in'] = False
            st.rerun()
            
    # --- SISTEMA DE ABAS (ISSO TEM QUE APARECER) ---
    st.title("⚡ Calculadora WEG & Histórico")
    tab_calc, tab_hist = st.tabs(["🧮 Simulação", "📂 Ver Histórico"])

    # --------------------------------------------------------------------------
    # ABA 1: CALCULADORA
    # --------------------------------------------------------------------------
    with tab_calc:
        c_eq1, c_eq2 = st.columns(2)
        equipamento = c_eq1.text_input("Equipamento", "QGBT Geral")
        detalhe = c_eq2.text_input("Detalhe", "Disjuntor de Entrada")

        st.info("Parâmetros do Arco:")
        c1, c2, c3 = st.columns(3)
        tensao = c1.number_input("Tensão (kV)", value=13.8, format="%.3f")
        corrente = c2.number_input("Corrente (kA)", value=17.0, format="%.3f")
        tempo = c3.number_input("Tempo (s)", value=0.5, format="%.4f")
        
        c4, c5 = st.columns(2)
        gap = c4.number_input("Gap (mm)", value=32.0)
        distancia = c5.number_input("Distância (mm)", value=450.0)

        # Botão Calcular
        if st.button("CALCULAR ENERGIA", type="primary"):
            # Cálculo Simulado
            energia = (tensao * corrente * tempo * 0.165) * 8 
            
            # Categoria
            cat_txt = "Cat 3 / 4"
            cat_color = "red"
            if energia < 1.2: 
                cat_txt = "Isento"
                cat_color = "green"
            elif energia < 8:
                cat_txt = "Cat 1 / 2"
                cat_color = "orange"
            
            # Salva no estado
            st.session_state['resultado'] = {
                "energia": energia,
                "cat_txt": cat_txt,
                "cat_color": cat_color,
                "equip": equipamento,
                "det": detalhe,
                "inputs": [tensao, corrente, tempo, gap, distancia]
            }

        # Exibir Resultados e Botão de Salvar
        if 'resultado' in st.session_state:
            res = st.session_state['resultado']
            
            st.divider()
            
            rc1, rc2 = st.columns([1, 2])
            with rc1:
                st.metric("Energia Incidente", f"{res['energia']:.2f} cal/cm²")
            with rc2:
                st.markdown(f"<h2 style='color:{res['cat_color']}'>{res['cat_txt']}</h2>", unsafe_allow_html=True)

            st.divider()
            
            # --- O BOTÃO DE SALVAR ---
            if st.button("💾 GRAVAR NO BANCO DE DADOS"):
                try:
                    payload = {
                        "username": st.session_state['username'],
                        "equipamento": res['equip'],
                        "detalhe": res['det'],
                        "tensao_kv": res['inputs'][0],
                        "corrente_ka": res['inputs'][1],
                        "tempo_s": res['inputs'][2],
                        "gap_mm": res['inputs'][3],
                        "distancia_mm": res['inputs'][4],
                        "energia_cal": float(f"{res['energia']:.2f}"),
                        "categoria": res['cat_txt']
                    }
                    supabase.table("arc_flash_history").insert(payload).execute()
                    st.success("✅ Salvo com sucesso! Verifique na aba 'Ver Histórico'.")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    # --------------------------------------------------------------------------
    # ABA 2: HISTÓRICO
    # --------------------------------------------------------------------------
    with tab_hist:
        st.header("Histórico de Simulações")
        if st.button("🔄 Atualizar Tabela"):
            st.rerun()
            
        try:
            response = supabase.table("arc_flash_history").select("*").order("created_at", desc=True).execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty:
                display_df = df[['created_at', 'username', 'equipamento', 'energia_cal', 'categoria']].copy()
                display_df.columns = ['Data', 'Usuário', 'Equipamento', 'Energia', 'Cat']
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("Nenhum registro encontrado.")
        except Exception as e:
            st.warning(f"Erro ao ler banco de dados: {e}")
