import streamlit as st
import numpy as np
import io
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# --- 1. CONEXÃO COM O BANCO DE DADOS (SUPABASE) ---
URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe" 

try:
    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
    supabase = st.session_state.supabase
except Exception as e:
    st.error(f"Erro na configuração do Banco de Dados: {e}")
    st.stop()

# --- 2. FUNÇÕES TÉCNICAS (NBR 17227:2025) ---
def calc_ia_step(ibf, g, k):
    k1, k2, k3, k4, k5, k6, k7, k8, k9, k10 = k
    log_base = k1 + k2 * np.log10(ibf) + k3 * np.log10(g)
    poli = (k4*ibf**6 + k5*ibf**5 + k6*ibf**4 + k7*ibf**3 + k8*ibf**2 + k9*ibf + k10)
    return 10**(log_base * poli)

def calc_en_step(ia, ibf, g, d, t, k, cf):
    k1, k2, k3, k4, k5, k6, k7, k8, k9, k10, k11, k12, k13 = k
    poli_den = (k4*ibf**7 + k5*ibf**6 + k6*ibf**5 + k7*ibf**4 + k8*ibf**3 + k9*ibf**2 + k10*ibf)
    termo_ia = (k3 * ia) / poli_den if poli_den != 0 else 0
    exp = (k1 + k2*np.log10(g) + termo_ia + k11*np.log10(ibf) + k12*np.log10(d) + k13*np.log10(ia) + np.log10(1.0/cf))
    return (12.552 / 50.0) * t * (10**exp)

def calc_dla_step(ia, ibf, g, t, k, cf):
    k1, k2, k3, k4, k5, k6, k7, k8, k9, k10, k11, k12, k13 = k
    poli_den = (k4*ibf**7 + k5*ibf**6 + k6*ibf**5 + k7*ibf**4 + k8*ibf**3 + k9*ibf**2 + k10*ibf)
    termo_ia = (k3 * ia) / poli_den if poli_den != 0 else 0
    log_fixo = (k1 + k2*np.log10(g) + termo_ia + k11*np.log10(ibf) + k13*np.log10(ia) + np.log10(1.0/cf))
    return 10**((np.log10(5.0 / ((12.552 / 50.0) * t)) - log_fixo) / k12)

def interpolar(v, f600, f2700, f14300):
    if v <= 0.6: return f600
    if v <= 2.7: return f600 + (f2700 - f600) * (v - 0.6) / 2.1
    return f2700 + (f14300 - f2700) * (v - 2.7) / 11.6

# --- 3. BASE DE DATOS ---
equip_data = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"(A) 914,4 x (L) 914,4 x (P) 914,4": [914.4, 914.4, 914.4, ""]}},
    "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"(A) 1143 x (L) 762 x (P) 762": [1143.0, 762.0, 762.0, ""]}},
    "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"(A) 660,4 x (L) 660,4 x (P) 660,4": [660.4, 660.4, 660.4, ""]}},
    "Conjunto de manobra 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"(A) 914,4 x (L) 914,4 x (P) 914,4": [914.4, 914.4, 914.4, ""], "(A) 1143 x (L) 762 x (P) 762": [1143.0, 762.0, 762.0, ""]}},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) ≤ 203,2": [355.6, 304.8, 203.2, "≤"]}},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) > 203,2": [355.6, 304.8, 203.2, ">"]}},
    "Conjunto de manobra BT": {"gap": 32.0, "dist": 457.2, "dims": {"(A) 508,0 x (L) 508,0 x (P) 508,0": [508.0, 508.0, 508.0, ""]}},
    "Caixa de junção de cabos": {"gap": 13.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) ≤ 203,2": [355.6, 304.8, 203.2, "≤"], "(A) 355,6 x (L) 304,8 x (P) > 203,2": [355.6, 304.8, 203.2, ">"]}}
}

# --- 4. INTERFACE ---
st.set_page_config(page_title="NBR 17227 - Laudo Técnico", layout="wide")
tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos", "Relatório"])

with tab1:
    st.subheader("Configuração")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", list(info["dims"].keys()))
    v_a, v_l, v_p, v_s = info["dims"][sel_dim]

    c1, c2, c3, c4 = st.columns(4)
    alt = c1.number_input("Altura [A]", value=float(v_a))
    larg = c2.number_input("Largura [L]", value=float(v_l))
    sinal_op = ["", "≤", ">"]
    sinal_final = c3.selectbox("Sinal P", sinal_op, index=sinal_op.index(v_s) if v_s in sinal_op else 0)
    prof = c4.number_input("Profundidade [P]", value=float(v_p))

    gap_f = st.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = st.number_input("Distância de Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Resultados Técnicos")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Corrente Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)
    
    if st.button("Executar Cálculo"):
        k_v = [0.6, 2.7, 14.3]
        k_ia = {0.6: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2.7: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14.3: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {0.6: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2.7: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14.3: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        ia_sts = [calc_ia_step(i_bf, gap_f, k_ia[v]) for v in k_v]
        i_arc = interpolar(v_oc, *ia_sts)
        
        en_sts = [calc_en_step(ia, i_bf, gap_f, dist_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
        e_cal = interpolar(v_oc, *en_sts) / 4.184
        
        dla_sts = [calc_dla_step(ia, i_bf, gap_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
        dla = interpolar(v_oc, *dla_sts)

        # Lógica de Categorias
        cat_norma = "CAT 1" if e_cal <= 4 else "CAT 2" if e_cal <= 8 else "CAT 4"
        cat_segura = "CAT 2" if e_cal > 1.2 and e_cal <= 8 else cat_norma
        
        st.session_state['res'] = {"I": i_arc, "E": e_cal, "D": dla, "CatN": cat_norma, "CatS": cat_segura, "Equip": equip_sel}
        
        st.divider()
        st.metric("Corrente Final de Arco", f"{i_arc:.3f} kA")
        st.metric("Fronteira (DLA)", f"{dla:.1f} mm")
        st.info(f"**Vestimenta Mínima (Norma):** {cat_norma} | **Vestimenta Recomendada (Segurança):** {cat_segura}")
        st.metric("Energia Incidente", f"{e_cal:.4f} cal/cm²")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader("Relatório de Engenharia")
        
        def gerar_pdf():
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elementos = []

            elementos.append(Paragraph("<b>RELATÓRIO TÉCNICO NBR 17227 - ARCO ELÉTRICO</b>", styles['Title']))
            elementos.append(Spacer(1, 12))

            # Memorial de Cálculo
            elementos.append(Paragraph("<b>1. MEMORIAL DE CÁLCULO</b>", styles['Heading2']))
            elementos.append(Paragraph(
                "Os cálculos de energia incidente foram efetuados com base nos modelos matemáticos da <b>NBR 17227:2025</b>. "
                "Utilizou-se a Corrente de Curto-Circuito (Ibf) para determinar a Corrente de Arco (Iarc) através de interpolação logarítmica. "
                "O cálculo da Energia Incidente (Ecal) considera a atenuação térmica pela distância, o tempo de arco e o fator de borda (Cf) do invólucro.", styles['Normal']))

            # Análise do Resultado (Solicitado)
            elementos.append(Spacer(1, 12))
            elementos.append(Paragraph("<b>2. ANÁLISE DO RESULTADO</b>", styles['Heading2']))
            elementos.append(Paragraph(
                f"Para o equipamento {r['Equip']}, o valor de energia incidente calculado foi de <b>{r['E']:.4f} cal/cm²</b>. "
                f"Tecnicamente, a norma classifica este nível como <b>{r['CatN']}</b>. Entretanto, por recomendação de segurança "
                f"operacional para garantir proteção integral contra queimaduras de 2º grau (limite de 1,2 cal/cm²), "
                f"estabelece-se a <b>{r['CatS']}</b> como requerida para a atividade.", styles['Normal']))

            # EPIs Complementares
            elementos.append(Spacer(1, 12))
            elementos.append(Paragraph("<b>3. EQUIPAMENTOS DE PROTEÇÃO (EPI)</b>", styles['Heading2']))
            elementos.append(Paragraph(
                "Além da vestimenta ignífuga (FR), o eletricista deve utilizar obrigatoriamente:<br/>"
                "• Capacete com Protetor Facial (Arc Rating compatível);<br/>"
                "• Balaclava para proteção do pescoço e cabeça;<br/>"
                "• Protetor auricular tipo plug ou abafador;<br/>"
                "• Luvas isolantes de borracha e luvas de cobertura em couro;<br/>"
                "• Calçado de segurança sem componentes metálicos.", styles['Normal']))

            doc.build(elementos)
            return buffer.getvalue()

        st.download_button("📩 Baixar Laudo Completo PDF", gerar_pdf(), f"Laudo_{r['Equip']}.pdf")
    else: st.info("Calcule os resultados na Aba 2.")
