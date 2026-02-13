import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Calculadora de Energia WEG",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CONEXÃO SUPABASE (JÁ PREENCHIDO)
# ==============================================================================
SUPABASE_URL = "https://lfgqxphittdatzknwkqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxmZ3F4cGhpdHRkYXR6a253a3F3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4NzYyNzUsImV4cCI6MjA4NjQ1MjI3NX0.fZSfStTC5GdnP0Md1O0ptq8dD84zV-8cgirqIQTNO4Y"

@st.cache_resource
def init_supabase():
    try:
        # Tenta pegar dos secrets primeiro, se falhar usa as variaveis acima
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Erro de conexão com Supabase: {e}")
    st.stop()

# ==============================================================================
# 3. ESTILO CSS
# ==============================================================================
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 4px; font-weight: bold; }
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #0091BD; color: white; border: none; /* Azul WEG */
    }
    .big-font { font-size: 20px !important; font-weight: bold; color: #333; }
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
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/WEG_logo.svg/2560px-WEG_logo.svg.png", width=150)
        st.markdown("### 🔐 Acesso ao Sistema")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            btn = st.form_submit_button("Entrar")
            
        if btn:
            try:
                # Busca usuário no banco
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
                    st.error("Usuário ou senha incorretos.")
            except Exception as e:
                st.error(f"Erro no login: {e}")

# ==============================================================================
# 5. APP PRINCIPAL
# ==============================================================================
if not st.session_state['logged_in']:
    login_screen()
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/WEG_logo.svg/2560px-WEG_logo.svg.png", width=100)
        st.success(f"👤 Olá, {st.session_state.get('name')}")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()
            
    # --- CABEÇALHO ---
    st.title("⚡ Calculadora de Custo de Energia")
    
    # Abas
    tab_calc, tab_hist = st.tabs(["🧮 Calcular", "📂 Histórico Salvo"])

    # --------------------------------------------------------------------------
    # ABA 1: CALCULADORA (Adaptada para a tabela 'calculations')
    # --------------------------------------------------------------------------
    with tab_calc:
        st.markdown("Preencha os dados do equipamento para estimar o custo mensal.")
        
        c1, c2 = st.columns(2)
        equipamento = c1.text_input("Nome do Equipamento", "Motor WEG W22")
        
        # Inputs Numéricos
        col_a, col_b, col_c, col_d = st.columns(4)
        potencia = col_a.number_input("Potência (Watts)", min_value=1.0, value=1500.0, step=100.0)
        horas = col_b.number_input("Horas/Dia", min_value=0.1, max_value=24.0, value=8.0, step=0.5)
        dias = col_c.number_input("Dias/Mês", min_value=1, max_value=31, value=22)
        preco = col_d.number_input("Preço kWh (R$)", min_value=0.01, value=0.85, format="%.2f")

        st.divider()

        # Botão Calcular e Salvar
        if st.button("CALCULAR E SALVAR NO HISTÓRICO", type="primary"):
            if not equipamento:
                st.warning("Por favor, dê um nome ao equipamento.")
            else:
                # 1. Lógica do Cálculo
                consumo_mensal_kwh = (potencia * horas * dias) / 1000
                custo_mensal = consumo_mensal_kwh * preco
                
                # 2. Exibição
                col_res1, col_res2 = st.columns(2)
                col_res1.metric("Consumo Estimado", f"{consumo_mensal_kwh:.2f} kWh/mês")
                col_res2.metric("Custo Mensal", f"R$ {custo_mensal:.2f}")

                # 3. Preparação para o Supabase (Mapeamento Exato da Tabela 'calculations')
                dados_para_salvar = {
                    "username": st.session_state['username'],  # Coluna: username
                    "equipment_name": equipamento,             # Coluna: equipment_name
                    "power_watts": potencia,                   # Coluna: power_watts
                    "hours_per_day": horas,                    # Coluna: hours_per_day
                    "days_per_month": dias,                    # Coluna: days_per_month
                    "kwh_price": preco,                        # Coluna: kwh_price
                    "monthly_cost": custo_mensal               # Coluna: monthly_cost
                }

                # 4. Envio ao Banco
                try:
                    # Inserção
                    response = supabase.table("calculations").insert(dados_para_salvar).execute()
                    
                    # Verificação se deu certo
                    if response.data:
                        st.toast("✅ Dados salvos com sucesso!", icon="💾")
                        st.balloons()
                    else:
                        st.error("O banco não retornou confirmação. Verifique se o RLS está desativado.")
                        
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    # --------------------------------------------------------------------------
    # ABA 2: HISTÓRICO (Lendo da tabela 'calculations')
    # --------------------------------------------------------------------------
    with tab_hist:
        st.header("Histórico de Cálculos")
        
        col_btn, _ = st.columns([1,4])
        if col_btn.button("🔄 Atualizar Lista"):
            st.rerun()
            
        try:
            # Busca dados ordenados por data (mais recente primeiro)
            response = supabase.table("calculations").select("*").order("created_at", desc=True).execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                
                # Selecionar e Renomear colunas para ficar bonito na tela
                # Ajuste conforme as colunas existam no retorno
                cols_to_show = ['created_at', 'username', 'equipment_name', 'monthly_cost', 'power_watts']
                
                # Filtra apenas colunas que realmente vieram do banco para evitar erro
                cols_existentes = [c for c in cols_to_show if c in df.columns]
                
                df_show = df[cols_existentes].copy()
                
                # Renomear para português na exibição
                mapa_nomes = {
                    'created_at': 'Data/Hora',
                    'username': 'Usuário',
                    'equipment_name': 'Equipamento',
                    'monthly_cost': 'Custo (R$)',
                    'power_watts': 'Potência (W)'
                }
                df_show.rename(columns=mapa_nomes, inplace=True)
                
                # Formatar data se existir
                if 'Data/Hora' in df_show.columns:
                    df_show['Data/Hora'] = pd.to_datetime(df_show['Data/Hora']).dt.strftime('%d/%m/%Y %H:%M')

                st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum cálculo encontrado no histórico ainda.")
                
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")
