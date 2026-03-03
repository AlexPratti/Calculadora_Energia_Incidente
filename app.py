import streamlit as st
import numpy as np
import io
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
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

# --- 3. SISTEMA DE LOGIN ---
st.set_page_config(page_title="NBR 17227 - Estudo de Arco", layout="wide")
if 'auth' not in st.session_state: st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    u = st.text_input("Usuário (E-mail)")
    p = st.text_input("Senha", type="password")
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
                else: st.error("Acesso negado ou pendente.")
            except: st.error("Erro de conexão.")
    st.stop()

# --- 4. BASE DE DADOS TÉCNICA ---
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

# --- 5. INTERFACE ---
tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos", "Relatório"])

with tab1:
    st.subheader("Configuração")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equip_data.keys()), key="main_equip_sel")
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", list(info["dims"].keys()), key="dim_sel_box")
    val_a, val_l, val_p, val_sinal = info["dims"][sel_dim]

    st.write("#### Ajuste Manual")
    c1, c2, c3, c4 = st.columns(4)
    alt = c1.number_input("Altura [A]", value=float(val_a))
    larg = c2.number_input("Largura [L]", value=float(val_l))
    sinal_op = ["", "≤", ">"]
    sinal_final = c3.selectbox("Sinal P", sinal_op, index=sinal_op.index(val_sinal) if val_sinal in sinal_op else 0)
    prof = c4.number_input("Profundidade [P]", value=float(val_p))

    st.divider()
    cg, cd = st.columns(2)
    gap_f = cg.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = cd.number_input("Distância de Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Resultados Técnicos")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Corrente Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)
    
    if st.button("Calcular Estudo de Arco"):
        k_v = [0.6, 2.7, 14.3]
        k_ia = {0.6: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2.7: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14.3: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {0.6: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2.7: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14.3: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        ia_sts = [calc_ia_step(i_bf, gap_f, k_ia[v]) for v in k_v]
        i_arc_final = interpolar(v_oc, *ia_sts)
        
        dl_sts = [calc_dla_step(ia, i_bf, gap_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
        dla_final = interpolar(v_oc, *dl_sts)

        d_range = np.linspace(dist_f, dla_final, 5)
        sens_list = []
        for d in d_range:
            e_sts = [calc_en_step(ia, i_bf, gap_f, d, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
            e_val = interpolar(v_oc, *e_sts) / 4.184
            c_val = "CAT 1 (Leve)" if e_val <= 4 else "CAT 2 (Moderado)" if e_val <= 8 else "CAT 4 (Alto)" if e_val <= 40 else "EXTREMO"
            if e_val < 1.2: c_val = "SEGURO"
            sens_list.append({"Distância (mm)": round(d, 1), "Energia (cal/cm²)": round(e_val, 4), "Vestimenta": c_val})
        
        st.session_state['res'] = {"I": i_arc_final, "D": dla_final, "Sens": sens_list, "Equip": equip_sel, "E_final": sens_list[0]["Energia (cal/cm²)"], "Cat_final": sens_list[0]["Vestimenta"]}
        
        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("Iarc Final", f"{i_arc_final:.3f} kA")
        c2.metric("Fronteira (DLA)", f"{dla_final:.1f} mm")
        st.table(pd.DataFrame(sens_list))
        st.metric("Energia Incidente", f"{st.session_state['res']['E_final']:.4f} cal/cm²")
        st.warning(f"🛡️ Recomendação: **{st.session_state['res']['Cat_final']}**")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader(f"Laudo: {r['Equip']}")
        def pdf_gen():
            buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet(); elementos = []
            elementos.append(Paragraph("<b>RELATÓRIO TÉCNICO NBR 17227</b>", styles['Title']))
            elementos.append(Paragraph(f"<b>Equipamento:</b> {r['Equip']}", styles['Normal']))
            elementos.append(Paragraph(f"<b>Iarc:</b> {r['I']:.3f} kA | <b>Energia:</b> {r['E_final']:.4f} cal/cm²", styles['Normal']))
            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>Memorial de Cálculo:</b> Aplicada NBR 17227:2025 para arco em espaço confinado, considerando interpolação de tensão e efeito de borda.", styles['Normal']))
            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>EPIs Obrigatórios:</b> Capacete com Protetor Facial, Luvas de Couro/Borracha, Balaclava e Vestimenta FR compatível.", styles['Normal']))
            doc.build(elementos); return buffer.getvalue()
        st.download_button("Baixar PDF", pdf_gen(), "laudo.pdf")
    else: st.info("Calcule na Aba 2 primeiro.")
