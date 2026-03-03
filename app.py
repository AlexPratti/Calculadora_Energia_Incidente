import streamlit as st
import numpy as np
import io
from datetime import datetime
from supabase import create_client, Client
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="NBR 17227 - Relatório Técnico", layout="wide")

URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe" 

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
supabase = st.session_state.supabase

# --- 2. FUNÇÕES TÉCNICAS (CONSERVAÇÃO DA LÓGICA DO CÓDIGO 1) ---
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

def interpolar(v, f600, f2700, f14300):
    if v <= 0.6: return f600
    if v <= 2.7: return f600 + (f2700 - f600) * (v - 0.6) / 2.1
    return f2700 + (f14300 - f2700) * (v - 2.7) / 11.6

# --- 3. SISTEMA DE LOGIN (RESTAURADO) ---
if 'auth' not in st.session_state: st.session_state['auth'] = None
if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    u = st.text_input("E-mail", key="l_u")
    p = st.text_input("Senha", type="password", key="l_p")
    if st.button("Acessar"):
        if u == "admin" and p == "101049app":
            st.session_state['auth'] = {"role": "admin", "user": "Administrador"}
            st.rerun()
        else:
            try:
                res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                if res.data and res.data[0]['status'] == 'ativo':
                    st.session_state['auth'] = {"role": "user", "user": u}
                    st.rerun()
                else: st.error("Acesso negado.")
            except: st.error("Erro de conexão.")
    st.stop()

# --- 4. INTERFACE ---
equip_data = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"(A) 914,4 x (L) 914,4 x (P) 914,4": [914.4, 914.4, 914.4, ""]}},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) ≤ 203,2": [355.6, 304.8, 203.2, "≤"]}},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) > 203,2": [355.6, 304.8, 203.2, ">"]}}
}

tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos", "Relatório Final"])

with tab1:
    equip_sel = st.selectbox("Equipamento:", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões:", list(info["dims"].keys()))
    v_a, v_l, v_p, v_s = info["dims"][sel_dim]
    c1, c2, c3, c4 = st.columns(4)
    alt = c1.number_input("Altura [A]", value=float(v_a))
    larg = c2.number_input("Largura [L]", value=float(v_l))
    sinal_f = c3.selectbox("Sinal P", ["", "≤", ">"], index=["", "≤", ">"].index(v_s) if v_s in ["", "≤", ">"] else 0)
    prof = c4.number_input("Profundidade [P]", value=float(v_p))
    gap_f = st.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = st.number_input("Distância Trabalho (mm)", value=float(info["dist"]))

with tab2:
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo (ms)", 10.0, 5000.0, 488.0)
    if st.button("Executar Cálculo"):
        k_v = [0.6, 2.7, 14.3]
        k_ia = {0.6: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2.7: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14.3: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {0.6: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2.7: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14.3: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        ia_sts = [calc_ia_step(i_bf, gap_f, k_ia[v]) for v in k_v]
        en_sts = [calc_en_step(ia, i_bf, gap_f, dist_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
        e_cal = interpolar(v_oc, *en_sts) / 4.184
        cat_n = "CAT 1" if e_cal <= 4 else "CAT 2" if e_cal <= 8 else "CAT 4"
        cat_s = "CAT 2" if (e_cal > 1.2 and e_cal <= 8) else cat_n
        st.session_state['res'] = {"E": e_cal, "CatN": cat_n, "CatS": cat_s, "Equip": equip_sel}
        st.success(f"Cálculo Concluído: {e_cal:.4f} cal/cm²")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        col_f1, col_f2 = st.columns(2)
        uf_crea = col_f1.text_input("Estado (UF):", "")
        num_crea = col_f2.text_input("Número do CREA:", "")

        def gerar_pdf():
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            elementos = []

            # Título conforme a imagem
            elementos.append(Paragraph("<font size=16><b>RELATÓRIO TÉCNICO DE ESTUDO DE ARCO ELÉTRICO</b></font>", styles['Title']))
            elementos.append(Paragraph("Emitido em: Data: __/__/____", styles['Normal']))
            elementos.append(Spacer(1, 1.5*cm))

            # Tópico 1 - Memorial
            elementos.append(Paragraph("<b>1. MEMORIAL DE CÁLCULO (NBR 17227:2025)</b>", styles['Heading2']))
            elementos.append(Paragraph(
                "A metodologia de cálculo aplicada segue rigorosamente a norma <b>NBR 17227:2025</b> para painéis em espaços confinados. "
                "Foram executados cálculos de Corrente de Arco ($I_{arc}$) via interpolação polinomial e determinação da Energia Incidente ($E_{cal}$) "
                "com ajuste do fator de borda ($C_f$) para refletir a geometria real do invólucro.", styles['Normal']))

            # Tópico 2 - Análise (Com a explicação solicitada)
            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>2. ANÁLISE DO RESULTADO</b>", styles['Heading2']))
            elementos.append(Paragraph(
                f"O estudo para o equipamento <b>{r['Equip']}</b> resultou em uma energia incidente de <b>{r['E']:.4f} cal/cm²</b>. "
                f"Pela classificação estrita da norma, a vestimenta seria {r['CatN']}. Contudo, visando a proteção contra o limiar de queimadura "
                f"de 2º grau (1,2 cal/cm²), recomenda-se a utilização da vestimenta <b>{r['CatS']}</b> para maior margem de segurança operacional.", styles['Normal']))

            # Tópico 3 - EPIs
            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>3. EQUIPAMENTOS DE PROTEÇÃO (EPI) REQUERIDOS</b>", styles['Heading2']))
            elementos.append(Paragraph(
                "• Vestimenta FR/AR conforme categoria recomendada;<br/>"
                "• Protetor facial contra arco elétrico (especificado para cal/cm² do laudo);<br/>"
                "• Balaclava ignífuga;<br/>"
                "• Luvas isolantes de borracha e cobertura em couro;<br/>"
                "• Calçado de segurança sem componentes metálicos.", styles['Normal']))

            # Assinatura (Fiel à imagem com as alterações solicitadas)
            elementos.append(Spacer(1, 3*cm))
            elementos.append(Paragraph("________________________________________________", styles['Normal']))
            elementos.append(Paragraph("<b>Engenheiro Eletricista</b>", styles['Normal']))
            elementos.append(Paragraph(f"CREA: {uf_crea} - {num_crea}", styles['Normal']))

            doc.build(elementos)
            return buffer.getvalue()

        st.download_button("📩 Baixar Relatório (PDF)", gerar_pdf(), f"Relatorio_{r['Equip']}.pdf")
