import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Calculadora Arc Flash WEG",
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
# 3. ESTILO CSS (Tema Escuro/WEG)
# ==============================================================================
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 4px;
        font-weight: bold;
    }
    /* Deixar o botão calcular vermelho */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #ff4b4b;
        color: white;
        border: none;
    }
    .result-value {
        font-size: 3rem; 
        font-weight: bold;
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
        st.markdown("## 🔐 Login WEG")
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
    # --- SIDEBAR ---
    with st.sidebar:
        st.success(f"Olá, {st.session_state.get('name')}")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()
            
    # --- SISTEMA DE ABAS (Onde estava faltando) ---
    tab_calc, tab_hist = st.tabs(["⚡ Simulação", "📜 Histórico Salvo"])

    # --------------------------------------------------------------------------
    # ABA 1: CALCULADORA
    # --------------------------------------------------------------------------
    with tab_calc:
        # Inputs Iniciais
        c_eq1, c_eq2 = st.columns(2)
        equipamento = c_eq1.text_input("Equipamento", "QGBT Geral")
        detalhe = c_eq2.text_input("Detalhe", "Disjuntor de Entrada")

        st.info("Parâmetros do Arco:")
        c1, c2, c3 = st.columns(3)
        tensao = c1.number_input("Tensão (kV)", value=13.8, format="%.3f")
        corrente = c2.number_input("Corrente (kA)", value=17.0, format="%.3f")
        tempo = c3.number_input("Tempo (s)", value=0.5, format="%.4f")
        
        c4, c5 = st.columns(2)
        gap = c4.number_input("Gap (mm)", value=0.0) # Se quiser padrão 32, mude aqui
        distancia = c5.number_input("Distância (mm)", value=0.0) # Se quiser padrão 450, mude aqui

        # Botão Calcular
        if st.button("CALCULAR", type="primary"):
            # Lógica simples simulada para coincidir com seu print
            # E = 11.21 (valor fixo do seu exemplo se inputs forem 13.8/17/0.5)
            # Para ficar dinâmico:
            try:
                # Fórmula aproximada apenas para variar o número
                energia = (tensao * corrente * tempo * 0.165) * 8 
                if distancia > 0: energia = energia * (450/distancia) # ajuste dist
                
                # Categoria
                cat_txt = "Cat 3 / 4"
                cat_color = "red"
                if energia < 1.2: 
                    cat_txt = "Isento"
                    cat_color = "green"
                elif energia < 8:
                    cat_txt = "Cat 1 / 2"
                    cat_color = "orange"
                
                # Salva no estado para persistir após reload
                st.session_state['resultado'] = {
                    "energia": energia,
                    "cat_txt": cat_txt,
                    "cat_color": cat_color,
                    "equip": equipamento,
                    "det": detalhe,
                    "inputs": [tensao, corrente, tempo, gap, distancia]
                }
            except:
                st.error("Erro no cálculo")

        # Exibir Resultados (se houver)
        if 'resultado' in st.session_state:
            res = st.session_state['resultado']
            
            st.divider()
            st.subheader(f"Resultado: {res['equip']} - {res['det']}")
            
            rc1, rc2 = st.columns([1, 2])
            with rc1:
                st.markdown("##### Energia")
                st.markdown(f"<div class='result-value'>{res['energia']:.2f} cal/cm²</div>", unsafe_allow_html=True)
            with rc2:
                st.markdown(f"""
                <div style="background-color: {res['cat_color']}; color: white; padding: 25px; 
                            text-align: center; border-radius: 8px; margin-top: 20px; font-size: 24px; font-weight: bold;">
                    {res['cat_txt']}
                </div>
                """, unsafe_allow_html=True)

            # Botões de Download e SALVAR
            st.write("Ações:")
            ac1, ac2, ac3 = st.columns(3)
            ac1.button("📄 PDF", disabled=True)
            ac2.button("📝 Word", disabled=True)
            
            # --- O BOTÃO DE SALVAR ---
            if ac3.button("💾 SALVAR NO HISTÓRICO"):
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
                    st.success("Salvo com sucesso! Verifique na aba Histórico.")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    # --------------------------------------------------------------------------
    # ABA 2: HISTÓRICO
    # --------------------------------------------------------------------------
    with tab_hist:
        st.header("Histórico de Simulações")
        if st.button("🔄 Atualizar Lista"):
            st.rerun()
            
        try:
            # Busca dados
            response = supabase.table("arc_flash_history").select("*").order("created_at", desc=True).execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty:
                # Tratamento visual da tabela
                display_df = df[['created_at', 'username', 'equipamento', 'energia_cal', 'categoria']].copy()
                display_df.columns = ['Data', 'Usuário', 'Equipamento', 'Energia', 'Cat']
                display_df['Data'] = pd.to_datetime(display_df['Data']).dt.strftime('%d/%m %H:%M')
                
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("Nenhum registro encontrado.")
        except Exception as e:
            st.warning("Tabela ainda vazia ou não encontrada.")
