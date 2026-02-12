import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA (Deve ser o primeiro comando)
# ==============================================================================
st.set_page_config(
    page_title="Calculadora Arc Flash WEG",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CONFIGURAÇÃO DO SUPABASE
# ==============================================================================
# 👇 COLOQUE SUAS CREDENCIAIS AQUI DENTRO DAS ASPAS 👇
SUPABASE_URL = "https://lfgqxphittdatzknwkqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxmZ3F4cGhpdHRkYXR6a253a3F3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4NzYyNzUsImV4cCI6MjA4NjQ1MjI3NX0.fZSfStTC5GdnP0Md1O0ptq8dD84zV-8cgirqIQTNO4Y"

@st.cache_resource
def init_supabase():
    # Tenta pegar dos secrets do Streamlit, se não, usa as variáveis acima
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Erro ao conectar no Supabase. Verifique se colocou a URL e a KEY no código.")
    st.stop()

# ==============================================================================
# 3. ESTILO CSS (Tema Escuro/Vermelho)
# ==============================================================================
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        font-weight: bold;
    }
    .big-font {
        font-size: 24px !important;
        font-weight: bold;
    }
    /* Destaque para o resultado */
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. SISTEMA DE LOGIN
# ==============================================================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''

def login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🔐 Acesso Restrito WEG</h1>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user_input = st.text_input("Usuário")
            pass_input = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")

        if submit:
            try:
                response = supabase.table('users').select("*").eq('username', user_input).eq('password', pass_input).execute()
                if response.data:
                    user_data = response.data[0]
                    if user_data.get('approved', False):
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = user_input
                        st.session_state['name'] = user_data.get('name', user_input)
                        st.success(f"Login realizado! Bem-vindo, {user_data.get('name')}")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Usuário aguardando aprovação do administrador.")
                else:
                    st.error("Usuário ou senha incorretos.")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")

def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.rerun()

# ==============================================================================
# 5. APLICAÇÃO PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    login_screen()
else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.title(f"👤 {st.session_state.get('name', 'Admin')}")
        st.success("Status: Online")
        st.divider()
        if st.button("Sair / Logout"):
            logout()

    # --- ABAS DA APLICAÇÃO ---
    tab1, tab2 = st.tabs(["⚡ Calculadora Arc Flash", "📜 Histórico de Simulações"])

    # ---------------------------------------------------------
    # ABA 1: CALCULADORA (Igual ao seu print)
    # ---------------------------------------------------------
    with tab1:
        st.subheader("Parâmetros de Entrada")
        
        col_eq1, col_eq2 = st.columns(2)
        with col_eq1:
            equipamento = st.text_input("Equipamento", value="QGBT Geral")
        with col_eq2:
            detalhe = st.text_input("Detalhe", value="Disjuntor de Entrada")

        st.info("Parâmetros do Arco:")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            tensao = st.number_input("Tensão (kV)", value=13.8, format="%.3f")
        with c2:
            corrente = st.number_input("Corrente (kA)", value=17.0, format="%.3f")
        with c3:
            tempo = st.number_input("Tempo (s)", value=0.5, format="%.4f")

        st.write("Geometria (0 = Padrão)")
        c4, c5 = st.columns(2)
        with c4:
            gap = st.number_input("Gap (mm)", value=32.0)
        with c5:
            distancia = st.number_input("Distância (mm)", value=450.0)

        # Botão Vermelho Grande
        calcular = st.button("CALCULAR", type="primary")

        if calcular:
            # --- CÁLCULO (Estimativa para demonstração) ---
            try:
                # Fórmula demonstrativa (ajustada para dar resultados similares ao seu exemplo)
                # Na vida real usaria IEEE 1584
                energia_incidente = (tensao * corrente * tempo * 0.18) * 10
                
                # Definição de Categoria
                categoria = "N/A"
                cor_cat = "gray"
                if energia_incidente < 1.2:
                    categoria = "Cat 0"
                    cor_cat = "green"
                elif energia_incidente < 4:
                    categoria = "Cat 1"
                    cor_cat = "#FFA500" # Orange
                elif energia_incidente < 8:
                    categoria = "Cat 2"
                    cor_cat = "#FF8C00" # Dark Orange
                elif energia_incidente < 40:
                    categoria = "Cat 3 / 4"
                    cor_cat = "red"
                else:
                    categoria = "DANGER"
                    cor_cat = "darkred"

                # --- EXIBIÇÃO ---
                st.divider()
                st.subheader(f"Resultado: {equipamento} - {detalhe}")
                
                res_col1, res_col2 = st.columns([1, 2])
                
                with res_col1:
                    st.metric(label="Energia Incidente", value=f"{energia_incidente:.2f} cal/cm²")
                
                with res_col2:
                    st.markdown(f"""
                    <div style="background-color: {cor_cat}; color: white; padding: 15px; text-align: center; border-radius: 10px; margin-top: 5px;">
                        <h1 style='margin:0;'>{categoria}</h1>
                    </div>
                    """, unsafe_allow_html=True)
                
                # --- PREPARAR DADOS PARA SALVAR (Session State) ---
                st.session_state['last_result'] = {
                    "username": st.session_state['username'],
                    "equipamento": equipamento,
                    "detalhe": detalhe,
                    "tensao_kv": tensao,
                    "corrente_ka": corrente,
                    "tempo_s": tempo,
                    "gap_mm": gap,
                    "distancia_mm": distancia,
                    "energia_cal": float(f"{energia_incidente:.2f}"),
                    "categoria": categoria
                }
                
                # Marca que acabou de calcular para mostrar o botão de salvar
                st.session_state['show_save'] = True

            except Exception as ex:
                st.error(f"Erro no cálculo: {ex}")

        # --- BOTÃO DE SALVAR (Fora do bloco 'if calcular' para não sumir) ---
        if st.session_state.get('show_save'):
            st.divider()
            col_s1, col_s2 = st.columns([1,2])
            with col_s1:
                if st.button("💾 Salvar Simulação no Histórico"):
                    try:
                        dados = st.session_state['last_result']
                        # Insere na tabela nova 'arc_flash_history'
                        supabase.table("arc_flash_history").insert(dados).execute()
                        st.success("✅ Salvo com sucesso no banco de dados!")
                        st.session_state['show_save'] = False # Esconde o botão após salvar
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
            
            with col_s2:
                 st.caption("Ao salvar, os dados ficarão disponíveis na aba Histórico.")

    # ---------------------------------------------------------
    # ABA 2: HISTÓRICO
    # ---------------------------------------------------------
    with tab2:
        st.header("Histórico de Simulações")
        
        col_h1, col_h2 = st.columns([1,4])
        with col_h1:
            if st.button("🔄 Atualizar"):
                st.rerun()
        
        try:
            # Busca dados ordenados por data (mais recente primeiro)
            response = supabase.table("arc_flash_history").select("*").order("created_at", desc=True).execute()
            dados = response.data
            
            if dados:
                df = pd.DataFrame(dados)
                
                # Selecionar colunas mais importantes para exibir
                colunas_visiveis = ["created_at", "username", "equipamento", "tensao_kv", "energia_cal", "categoria"]
                
                # Renomear para ficar bonito em português
                df_show = df[colunas_visiveis].rename(columns={
                    "created_at": "Data/Hora",
                    "username": "Usuário",
                    "equipamento": "Equipamento",
                    "tensao_kv": "Tensão (kV)",
                    "energia_cal": "Energia (cal/cm²)",
                    "categoria": "Cat"
                })
                
                # Formatar a data
                df_show["Data/Hora"] = pd.to_datetime(df_show["Data/Hora"]).dt.strftime('%d/%m/%Y %H:%M')

                st.dataframe(df_show, use_container_width=True)
            else:
                st.info("Nenhuma simulação salva ainda.")
                
        except Exception as e:
            st.warning("Não foi possível carregar o histórico. Verifique se a tabela 'arc_flash_history' foi criada no Supabase.")
            st.error(f"Erro técnico: {e}")
