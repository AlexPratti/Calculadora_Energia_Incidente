import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="WEG Arc Flash",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CONEXÃO SUPABASE
# ==============================================================================
SUPABASE_URL = "https://lfgqxphittdatzknwkqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxmZ3F4cGhpdHRkYXR6a253a3F3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4NzYyNzUsImV4cCI6MjA4NjQ1MjI3NX0.fZSfStTC5GdnP0Md1O0ptq8dD84zV-8cgirqIQTNO4Y"

@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Erro de conexão com Supabase: {e}")
    st.stop()

# ==============================================================================
# 3. ESTILO CSS (Tema Escuro/WEG)
# ==============================================================================
st.markdown("""
<style>
    /* Botão Principal Vermelho */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #FF4B4B; 
        color: white; 
        border: none;
        height: 50px;
        font-size: 18px;
    }
    /* Cards de Resultado */
    .result-card {
        padding: 20px;
        border-radius: 8px;
        color: white;
        text-align: center;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. LOGIN
# ==============================================================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''

def login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("### ⚡ Acesso Calculadora Arc Flash")
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
# 5. APLICAÇÃO PRINCIPAL
# ==============================================================================
if not st.session_state['logged_in']:
    login_screen()
else:
    # Sidebar
    with st.sidebar:
        st.success(f"Olá, {st.session_state.get('name')}")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()

    # Título e Abas
    st.title("⚡ Calculadora de Energia Incidente (Arc Flash)")
    tab_calc, tab_hist = st.tabs(["🧮 Simulação", "📂 Histórico de Cálculos"])

    # --------------------------------------------------------------------------
    # ABA 1: CALCULADORA
    # --------------------------------------------------------------------------
    with tab_calc:
        # Inputs Iniciais
        c_eq1, c_eq2 = st.columns(2)
        tag_equip = c_eq1.text_input("Tag do Equipamento", "QGBT Geral")
        detalhe_desc = c_eq2.text_input("Detalhe", "Disjuntor de Entrada")

        st.info("Parâmetros do Arco:")
        
        # Inputs Numéricos
        c1, c2, c3 = st.columns(3)
        tensao = c1.number_input("Tensão (kV)", value=13.8, format="%.3f")
        corrente = c2.number_input("Corrente (kA)", value=17.0, format="%.3f")
        tempo = c3.number_input("Tempo (s)", value=0.5, format="%.4f")
        
        c4, c5 = st.columns(2)
        gap = c4.number_input("Gap (mm)", value=32.0)
        distancia = c5.number_input("Distância (mm)", value=450.0)

        # Estado para guardar resultado entre interações
        if 'resultado_af' not in st.session_state:
            st.session_state['resultado_af'] = None

        # --- BOTÃO DE CALCULAR ---
        if st.button("CALCULAR ENERGIA", type="primary"):
            # Fórmula Simplificada (exemplo)
            energia = (tensao * corrente * tempo * 0.165) * 8 
            
            # Categorização (Exemplo IEEE)
            cat_txt = "Cat 3 / 4"
            bg_color = "#D50000" # Vermelho
            if energia < 1.2: 
                cat_txt = "Isento"
                bg_color = "#2E7D32" # Verde
            elif energia < 8:
                cat_txt = "Cat 1 / 2"
                bg_color = "#FF6D00" # Laranja
            
            # Salva no Session State para não perder ao clicar em outro botão
            st.session_state['resultado_af'] = {
                "energia": energia,
                "cat_txt": cat_txt,
                "bg_color": bg_color,
                "tag": tag_equip,
                "vals": [tensao, corrente, tempo, distancia, gap]
            }

        # Exibir Resultados (se houver cálculo feito)
        if st.session_state['resultado_af']:
            res = st.session_state['resultado_af']
            
            st.divider()
            st.write(f"**Resultado:** {res['tag']}")
            
            # Mostrador Visual
            c_res1, c_res2 = st.columns([1, 2])
            with c_res1:
                st.metric("Energia Incidente", f"{res['energia']:.2f} cal/cm²")
            with c_res2:
                st.markdown(f"""
                <div style="background-color: {res['bg_color']}; padding: 15px; border-radius: 10px; text-align: center; color: white;">
                    <h2 style="margin:0;">{res['cat_txt']}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            # --- BOTÃO DE SALVAR NO SUPABASE ---
            # Mapeando para as colunas exatas da sua tabela: arc_flash_history
            if st.button("💾 GRAVAR NO HISTÓRICO"):
                payload = {
                    "username": st.session_state['username'],  # Coluna: username
                    "tag_equipamento": res['tag'],             # Coluna: tag_equipamento
                    "tensao_kv": res['vals'][0],               # Coluna: tensao_kv
                    "corrente_ka": res['vals'][1],             # Coluna: corrente_ka
                    "tempo_s": res['vals'][2],                 # Coluna: tempo_s
                    "distancia_mm": res['vals'][3],            # Coluna: distancia_mm
                    "energia_cal": float(f"{res['energia']:.2f}") # Coluna: energia_cal
                }
                
                try:
                    # Insere na tabela arc_flash_history
                    response = supabase.table("arc_flash_history").insert(payload).execute()
                    
                    if response.data:
                        st.toast("✅ Simulação salva com sucesso!", icon="⚡")
                        st.balloons()
                    else:
                        st.warning("Salvo, mas sem confirmação de dados retornados.")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

            # Botões decorativos de download
            cd1, cd2 = st.columns(2)
            with cd1: st.button("📄 Relatório PDF")
            with cd2: st.button("📝 Relatório Word")

    # --------------------------------------------------------------------------
    # ABA 2: HISTÓRICO
    # --------------------------------------------------------------------------
    with tab_hist:
        st.header("Histórico de Simulações de Arco")
        
        if st.button("🔄 Atualizar Tabela"):
            st.rerun()
            
        try:
            # Busca na tabela correta: arc_flash_history
            response = supabase.table("arc_flash_history").select("*").order("created_at", desc=True).execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                
                # Selecionar colunas para exibir
                colunas_visiveis = [
                    'created_at', 'username', 'tag_equipamento', 
                    'energia_cal', 'tensao_kv'
                ]
                
                # Filtra apenas o que existe no dataframe para evitar erro
                cols_finais = [c for c in colunas_visiveis if c in df.columns]
                df_show = df[cols_finais].copy()
                
                # Renomeia para ficar bonito
                rename_map = {
                    'created_at': 'Data',
                    'username': 'Engenheiro',
                    'tag_equipamento': 'Tag',
                    'energia_cal': 'Energia (cal/cm²)',
                    'tensao_kv': 'Tensão (kV)'
                }
                df_show.rename(columns=rename_map, inplace=True)
                
                # Formata Data
                if 'Data' in df_show.columns:
                    df_show['Data'] = pd.to_datetime(df_show['Data']).dt.strftime('%d/%m/%Y %H:%M')

                st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma simulação salva ainda.")
                
        except Exception as e:
            st.error(f"Erro ao carregar banco de dados: {e}")
