import streamlit as st
import math
from fpdf import FPDF

# Configuração da página
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

# ==============================================================================
# Funções para os cálculos
# ==============================================================================

# Funções para interpolação da corrente de arco
def calcular_correntes_interpoladas(voc, ibf, g, config_eletrodos):
    coef_vcb = {
        "VCB": {"600": [-0.04287, 1.035, -0.083, 0, 0, -4.783E-09, 1.962E-06, -0.000229, 0.003141, 1.092],
                "2700": [0.0065, 1.001, -0.024, -1.557E-12, 4.556E-10, -4.186E-08, 8.346E-07, 5.482E-05, -0.003191, 0.9729],
                "14300": [0.005795, 1.015, -0.011, -1.557E-12, 4.556E-10, -4.186E-08, 8.346E-07, 5.482E-05, -0.003191, 0.9729]}
        # Adicione outros tipos de configuração, como VCBB e HCB, conforme necessário.
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

    # Correntes intermediárias
    iarc600 = calcular_iarc("600", ibf, g, coef_vcb[config_eletrodos]["600"])
    iarc2700 = calcular_iarc("2700", ibf, g, coef_vcb[config_eletrodos]["2700"])
    iarc14300 = calcular_iarc("14300", ibf, g, coef_vcb[config_eletrodos]["14300"])

    # Interpolação das correntes
    iarc1 = ((iarc2700 - iarc600) / 2.1) * (voc - 2.7) + iarc2700
    iarc2 = ((iarc14300 - iarc2700) / 11.6) * (voc - 14.3) + iarc14300
    iarc3 = ((iarc1 * (2.7 - voc)) / 2.1) + ((iarc2 * (voc - 0.6)) / 2.1)

    # Corrente final
    iarc_final = iarc3 if voc <= 2.7 else iarc2
    return iarc600, iarc2700, iarc14300, iarc_final

# Função para calcular energia incidente
def calcular_energia_incidente(voc, ibf, g, d, t, cf, iarc600, iarc2700, iarc14300, config_eletrodos):
    def energia(voc_level, iarc, coeffs):
        log_ibf = math.log10(ibf)
        log_g = math.log10(g)
        log_d = math.log10(d)
        energia = (
            (12.552 / 50)
            * (
                coeffs[0]
                + coeffs[1] * log_g
                + (t / 10) * coeffs[2] * iarc
                + coeffs[3] * ibf**7
                + coeffs[4] * ibf**6
                + coeffs[5] * ibf**5
                + coeffs[6] * ibf**4
                + coeffs[7] * ibf**3
                + coeffs[8] * ibf**2
                + coeffs[9] * ibf
                + coeffs[10] * log_ibf
                + coeffs[11] * log_d
                + math.log10(1 / cf)
            )
        )
        return energia

    coef_vcb = {
        "VCB": {"600": [0.753364, 0.566, 1.752636, 0, 0, -4.783E-09, 1.962E-06, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957],
                "2700": [2.40021, 0.165, 0.354202, -1.557E-12, 4.556E-10, -4.186E-08, 8.346E-07, 5.482E-05, -0.003191, 0.9729, 0, -1.569, 0.9778],
                "14300": [3.825917, 0.11, -0.999749, -1.557E-12, 4.556E-10, -4.186E-08, 8.346E-07, 5.482E-05, -0.003191, 0.9729, 0, -1.568, 0.99]}
        # Adicione outros tipos de configuração, como VCBB e HCB, conforme necessário.
    }

    e600 = energia("600", iarc600, coef_vcb[config_eletrodos]["600"])
    e2700 = energia("2700", iarc2700, coef_vcb[config_eletrodos]["2700"])
    e14300 = energia("14300", iarc14300, coef_vcb[config_eletrodos]["14300"])

    # Interpolação da energia
    e1 = ((e2700 - e600) / 2.1) * (voc - 2.7) + e2700
    e2 = ((e14300 - e2700) / 11.6) * (voc - 14.3) + e14300
    e3 = ((e1 * (2.7 - voc)) / 2.1) + ((e2 * (voc - 0.6)) / 2.1)

    energia_final = e3 if voc <= 2.7 else e2
    return e600, e2700, e14300, energia_final

# ==============================================================================
# Interface Streamlit
# ==============================================================================

# Título
st.title("Arc Flash - Cálculo de Energia Incidente")

# Entradas do usuário:
voc = st.number_input("Tensão de circuito aberto Voc (kV):", value=13.8, step=0.1)
ibf = st.number_input("Corrente de falta trifásica franca Ibf (kA):", value=4.852, step=0.01)
g = st.number_input("Distância entre os eletrodos G (mm):", value=152.0, step=1.0)
d = st.number_input("Distância de trabalho D (mm):", value=914.4, step=10.0)
t = st.number_input("Duração do arco T (s):", value=0.488, step=0.001)
altura_inv = st.number_input("Altura do invólucro (mm):", value=1143.0, step=1.0)
largura_inv = st.number_input("Largura do invólucro (mm):", value=762.0, step=1.0)
cf = st.number_input("Fator de correção do invólucro CF:", value=1.28372, step=0.01)
var_cf = st.number_input("Variação do CF:", value=0.02391, step=0.001)
config_eletrodos = st.selectbox("Configuração dos eletrodos:", ["VCB", "VCBB", "HCB", "VOA", "HOA"])

# Cálculos
iarc600, iarc2700, iarc14300, iarc_final = calcular_correntes_interpoladas(voc, ibf, g, config_eletrodos)
e600, e2700, e14300, energia_final = calcular_energia_incidente(voc, ibf, g, d, t, cf, iarc600, iarc2700, iarc14300, config_eletrodos)

# Exibição dos resultados
st.subheader("Resultados")
st.write(f"Corrente de arco intermediária para 600 V: {iarc600:.2f} kA")
st.write(f"Corrente de arco intermediária para 2700 V: {iarc2700:.2f} kA")
st.write(f"Corrente de arco intermediária para 14300 V: {iarc14300:.2f} kA")
st.write(f"Corrente de arco final: {iarc_final:.2f} kA")
st.write(f"Energia incidente para 600 V: {e600:.2f} cal/cm²")
st.write(f"Energia incidente para 2700 V: {e2700:.2f} cal/cm²")
st.write(f"Energia incidente para 14300 V: {e14300:.2f} cal/cm²")
st.write(f"Energia incidente final: {energia_final:.2f} cal/cm²")
