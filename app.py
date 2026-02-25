import streamlit as st
import math
from supabase import create_client

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM SUPABASE
# ==============================================================================
st.set_page_config(
    page_title="Cálculo de Energia Incidente - ABNT NBR 17227",
    page_icon="⚡",
    layout="wide",
)

SUPABASE_URL = "https://lfgqxphittdatzknwkqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxmZ3F4cGhpdHRkYXR6a253a3F3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4NzYyNzUsImV4cCI6MjA4NjQ1MjI3NX0.fZSfStTC5GdnP0Md1O0ptq8dD84zV-8cgirqIQTNO4Y"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ==============================================================================
# LOGIN E SISTEMA DE RESTRIÇÃO
# ==============================================================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔒 Sistema Arc Flash")
    login_col1, login_col2 = st.columns([1, 2])
    with login_col2:
        username = st.text_input("Usuário (admin)", placeholder="Digite seu usuário")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if username == "admin" and password == "admin":
                st.session_state['logged_in'] = True
                st.success("Login realizado com sucesso!")
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

st.sidebar.success("Bem-vindo, administrador!")
st.title("Cálculo de Energia Incidente - Conforme ABNT NBR 17227")

# ==============================================================================
# FUNÇÕES PARA CÁLCULOS
# ==============================================================================

# Função para calcular CF automaticamente
def calcular_cf(altura, largura, config_eletrodos):
    if altura is None or altura == 0:
        altura = 1143.0  # Valor típico para conjunto de manobra 15 kV
    if largura is None or largura == 0:
        largura = 762.0  # Valor típico para conjunto de manobra 15 kV
    
    ees = (altura + largura) / 2
    if config_eletrodos == "VCB":
        cf = -0.0003 * ees**2 + 0.03441 * ees + 0.4325
    elif config_eletrodos == "VCBB":
        cf = -0.0003 * ees**2 + 0.032 * ees + 0.479
    elif config_eletrodos == "HCB":
        cf = -0.0002 * ees**2 + 0.01935 * ees + 0.6899
    return cf

# Função para calcular VarCf automaticamente
def calcular_varcf(voc, config_eletrodos):
    coef = {
        "VCB": [0, -0.0000014269, 0.000083137, -0.0019382, 0.022366, -0.12645, 0.30226],
        "VCBB": [1.138E-06, -6.0287E-05, 0.0012758, -0.013778, 0.080217, -0.24066, 0.33524],
        "HCB": [0, -3.097E-06, 0.00016405, -0.0033609, 0.033308, -0.16182, 0.34627],
    }
    k = coef[config_eletrodos]
    varcf = (k[0] * voc**6 + k[1] * voc**5 + k[2] * voc**4 + k[3] * voc**3 +
             k[4] * voc**2 + k[5] * voc + k[6])
    return varcf

# Função para calcular corrente de arco
def calcular_correntes_interpoladas(voc, ibf, g, config_eletrodos):
    coef = {
        "VCB": {
            "600": [-0.04287, 1.035, -0.083, 0, 0, -4.783E-09, 1.962E-06, -0.000229, 0.003141, 1.092],
            "2700": [0.0065, 1.001, -0.024, -1.557E-12, 4.556E-10, -4.186E-08, 8.346E-07, 5.482E-05, -0.003191, 0.9729],
            "14300": [0.005795, 1.015, -0.011, -1.557E-12, 4.556E-10, -4.186E-08, 8.346E-07, 5.482E-05, -0.003191, 0.9729],
        },
    }

    def calcular_iarc(voc_level, ibf, g, coeffs):
        log_ibf = math.log10(ibf)
        log_g = math.log10(g)
        result = 10 ** (
            coeffs[0]
            + coeffs[1] * log_ibf
            + coeffs[2] * log_g
            + coeffs[3] * ibf**6
            + coeffs[4] * ibf**5
            + coeffs[5] * ibf**4
            + coeffs[6] * ibf**3
            + coeffs[7] * ibf**2
            + coeffs[8] * ibf
            + coeffs[9]
        )
        return result

    iarc600 = calcular_iarc("600", ibf, g, coef[config_eletrodos]["600"])
    iarc2700 = calcular_iarc("2700", ibf, g, coef[config_eletrodos]["2700"])
    iarc14300 = calcular_iarc("14300", ibf, g, coef[config_eletrodos]["14300"])

    iarc1 = ((iarc2700 - iarc600) / 2.1) * (voc - 2.7) + iarc2700
    iarc2 = ((iarc14300 - iarc2700) / 11.6) * (voc - 14.3) + iarc14300
    iarc3 = ((iarc1 * (2.7 - voc)) / 2.1) + ((iarc2 * (voc - 0.6)) / 2.1)

    iarc_final = iarc3 if voc <= 2.7 else iarc2
    return iarc600, iarc2700, iarc14300, iarc_final

# ==============================================================================
# INTERFACE STREAMLIT
# ==============================================================================

st.subheader("Entradas do Usuário:")
voc = st.number_input("Tensão de circuito aberto Voc (kV):", value=13.8, step=0.1)
ibf = st.number_input("Corrente de falta trifásica franca Ibf (kA):", value=4.852, step=0.01)
g = st.number_input("Distância entre os eletrodos G (mm):", value=152.0, step=1.0)
d = st.number_input("Distância de trabalho D (mm):", value=914.4, step=10.0)
t = st.number_input("Duração do arco T (s):", value=0.488, step=0.001)
altura = st.number_input("Altura do invólucro (mm):", value=1143.0, step=1.0)
largura = st.number_input("Largura do invólucro (mm):", value=762.0, step=1.0)
config_eletrodos = st.selectbox("Configuração dos eletrodos:", ["VCB", "VCBB", "HCB"])

cf = calcular_cf(altura, largura, config_eletrodos)
varcf = calcular_varcf(voc, config_eletrodos)
iarc600, iarc2700, iarc14300, iarc_final = calcular_correntes_interpoladas(voc, ibf, g, config_eletrodos)

st.subheader("Resultados:")
st.write(f"CF: {cf:.2f}")
st.write(f"VarCf: {varcf:.2f}")
st.write(f"Corrente de arco intermediária para 600 V: {iarc600:.2f} kA")
st.write(f"Corrente de arco final: {iarc_final:.2f} kA")
