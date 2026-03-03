import streamlit as st
import numpy as np
import io
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="NBR 17227 - Gestão de Arco Elétrico", layout="wide")

URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe" 

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
supabase = st.session_state.supabase

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

# --- 3. SISTEMA DE LOGIN ---
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

# --- 4. BASE DE DADOS ---
equip_data = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"(A) 914,4 x (L) 914,4 x (P) 914,4": [914.4, 914.4, 914.4, ""]}},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) ≤ 203,2": [355.6, 304.8, 203.2, "≤"]}},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) > 203,2": [355.6, 304.8, 203.2, ">"]}}
}

tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório Final"])

with tab1:
    st.subheader("Configuração do Cenário")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões:", list(info["dims"].keys()))
    v_a, v_l, v_p, v_s = info["dims"][sel_dim]
    
    c1, c2, c3, c4 = st.columns(4)
    alt = c1.number_input("Altura [A] (mm)", value=float(v_a))
    larg = c2.number_input("Largura [L] (mm)", value=float(v_l))
    sinal_f = c3.selectbox("Sinal P", ["", "≤", ">"], index=["", "≤", ">"].index(v_s) if v_s in ["", "≤", ">"] else 0)
    prof = c4.number_input("Profundidade [P] (mm)", value=float(v_p))
    
    gap_f = st.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = st.number_input("Distância Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Resultados Técnicos e Sensibilidade")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Corrente Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)
    
    if st.button("Executar Estudo de Arco"):
        k_v = [0.6, 2.7, 14.3]
        k_ia = {0.6: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2.7: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14.3: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {0.6: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2.7: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14.3: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        # Corrente e Fronteira
        ia_sts = [calc_ia_step(i_bf, gap_f, k_ia[v]) for v in k_v]
        i_arc = interpolar(v_oc, *ia_sts)
        dla_sts = [calc_dla_step(ia, i_bf, gap_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
        dla = interpolar(v_oc, *dla_sts)

        # Tabela de Sensibilidade até a Fronteira
        d_pontos = np.linspace(dist_f, dla, 5)
        sens_list = []
        for d in d_pontos:
            e_sts_temp = [calc_en_step(ia, i_bf, gap_f, d, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
            e_v = interpolar(v_oc, *e_sts_temp) / 4.184
            c_v = "CAT 1" if e_v <= 4 else "CAT 2" if e_v <= 8 else "CAT 4"
            if e_v < 1.2: c_v = "SEGURO (<1.2)"
            sens_list.append({"Distância (mm)": round(d, 1), "Energia (cal/cm²)": round(e_v, 4), "Vestimenta": c_v})
        
        e_final = sens_list[0]["Energia (cal/cm²)"]
        cat_norma = sens_list[0]["Vestimenta"]
        cat_segura = "CAT 2" if (e_final > 1.2 and e_final <= 8) else cat_norma

        st.session_state['res'] = {"I": i_arc, "D": dla, "E": e_final, "CatN": cat_norma, "CatS": cat_segura, "Sens": sens_list, "Equip": equip_sel}
        
        st.divider()
        c_i, c_d = st.columns(2)
        c_i.metric("Corrente Final de Arco (Iarc_Final)", f"{i_arc:.3f} kA")
        c_d.metric("Fronteira de Aproximação (DLA)", f"{dla:.1f} mm")
        
        st.write("#### Tabela de Sensibilidade (Afastamento até a Fronteira)")
        st.table(pd.DataFrame(sens_list))
        
        st.metric("Energia Incidente no Ponto de Trabalho", f"{e_final:.4f} cal/cm²")
        st.success(f"**Vestimenta Requerida (Cálculo):** {cat_norma}")
        st.warning(f"**Vestimenta Requerida (Segurança/Norma):** {cat_segura}")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader("Configuração do Relatório")
        c_uf = st.text_input("UF do CREA:", "")
        c_num = st.text_input("Número do CREA:", "")

        def gerar_pdf():
            buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet(); elementos = []
            
            elementos.append(Paragraph("<b>RELATÓRIO TÉCNICO DE ESTUDO DE ARCO ELÉTRICO</b>", styles['Title']))
            elementos.append(Paragraph("Data: __/__/____", styles['Normal']))
            elementos.append(Spacer(1, 1*cm))

            elementos.append(Paragraph("<b>1. MEMORIAL DE CÁLCULO (NBR 17227:2025)</b>", styles['Heading2']))
            elementos.append(Paragraph("A metodologia aplicada segue a norma NBR 17227:2025 para painéis em espaços confinados, com cálculos de Iarc via interpolação polinomial e Energia Incidente com ajuste de fator de borda.", styles['Normal']))

            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>2. ANÁLISE DO RESULTADO</b>", styles['Heading2']))
            elementos.append(Paragraph(f"O estudo para o equipamento {r['Equip']} resultou em uma energia incidente de <b>{r['E']:.4f} cal/cm²</b>. Pela classificação estrita da norma, a vestimenta seria {r['CatN']}. Contudo, visando a proteção contra o limiar de queimadura de 2º grau (1,2 cal/cm²), recomenda-se a utilização da vestimenta <b>{r['CatS']}</b> para maior margem de segurança operacional.", styles['Normal']))

            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>3. EQUIPAMENTOS DE PROTEÇÃO (EPI) REQUERIDOS</b>", styles['Heading2']))
            elementos.append(Paragraph("• Vestimenta FR/AR conforme categoria recomendada;<br/>• Protetor facial contra arco elétrico;<br/>• Balaclava ignífuga;<br/>• Luvas isolantes de borracha e cobertura em couro;<br/>• Calçado de segurança sem componentes metálicos.", styles['Normal']))

            elementos.append(Spacer(1, 2*cm))
            elementos.append(Paragraph("________________________________________________", styles['Normal']))
            elementos.append(Paragraph("<b>Engenheiro Eletricista</b>", styles['Normal']))
            elementos.append(Paragraph(f"CREA: {c_uf} - {c_num}", styles['Normal']))
            
            doc.build(elementos); return buffer.getvalue()

        st.download_button("📩 Baixar Relatório (PDF)", gerar_pdf(), f"Laudo_{r['Equip']}.pdf")
