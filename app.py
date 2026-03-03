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
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="NBR 17227 - Relatório Técnico Profissional", layout="wide")

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

def definir_vestimenta(caloria):
    if caloria < 1.2: return "SEGURO"
    if caloria <= 4: return "CAT 1"
    if caloria <= 8: return "CAT 2"
    if caloria <= 25: return "CAT 3"
    return "CAT 4"

# --- 3. SISTEMA DE LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = None
if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    u = st.text_input("E-mail")
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

# --- 4. BASE DE DADOS ---
equip_data = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"(A) 914,4 x (L) 914,4 x (P) 914,4": [914.4, 914.4, 914.4, ""]}},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) ≤ 203,2": [355.6, 304.8, 203.2, "≤"]}},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"(A) 355,6 x (L) 304,8 x (P) > 203,2": [355.6, 304.8, 203.2, ">"]}}
}

tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório Final"])

with tab1:
    st.subheader("Configuração do Equipamento")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões:", list(info["dims"].keys()))
    v_a, v_l, v_p, v_s = info["dims"][sel_dim]
    
    c1, c2, c3, c4 = st.columns(4)
    alt = c1.number_input("Altura [A] (mm)", value=float(v_a))
    larg = c2.number_input("Largura [L] (mm)", value=float(v_l))
    sinal_op = ["", "≤", ">"]
    sinal_f = c3.selectbox("Sinal P", sinal_op, index=sinal_op.index(v_s) if v_s in sinal_op else 0)
    prof = c4.number_input("Profundidade [P] (mm)", value=float(v_p))
    
    gap_f = st.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = st.number_input("Distância Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Análise de Arco Elétrico")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Corrente Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)

    if st.button("Executar Estudo"):
        k_v = [0.6, 2.7, 14.3]
        k_ia = {0.6: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2.7: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14.3: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {0.6: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2.7: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14.3: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        ia_sts = [calc_ia_step(i_bf, gap_f, k_ia[v]) for v in k_v]
        i_arc = interpolar(v_oc, *ia_sts)
        dla_sts = [calc_dla_step(ia, i_bf, gap_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
        dla = interpolar(v_oc, *dla_sts)

        d_pontos = np.linspace(dist_f, dla, 5)
        sens_list = []
        for d in d_pontos:
            e_sts_temp = [calc_en_step(ia, i_bf, gap_f, d, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
            e_v = interpolar(v_oc, *e_sts_temp) / 4.184
            c_v = definir_vestimenta(e_v)
            sens_list.append([round(d, 1), round(e_v, 4), c_v])
        
        e_trab_cal = sens_list[0][1]
        e_trab_joule = e_trab_cal * 4.184
        v_norma = definir_vestimenta(e_trab_cal)
        v_seguranca = "CAT 2" if (1.2 < e_trab_cal <= 4) else v_norma
        
        st.session_state['res'] = {
            "I": i_arc, "D": dla, "E_cal": e_trab_cal, "E_joule": e_trab_joule,
            "V_norma": v_norma, "V_seguranca": v_seguranca,
            "Sens": sens_list, "Equip": equip_sel
        }
        
        st.divider()
        st.subheader("Resultados do Estudo")
        
        col_res_v = st.columns([1, 2])
        with col_res_v[0]:
            st.metric("Corrente de Arco (Iarc)", f"{i_arc:.3f} kA")
            st.metric("Fronteira de Arco (DLA)", f"{dla:.1f} mm")
            st.metric("Energia Incidente", f"{e_trab_cal:.4f} cal/cm²")
            st.metric("Energia Incidente", f"{e_trab_joule:.2f} J/cm²")
            
            st.info(f"**Vestimenta (Conforme Cálculo):** {v_norma}")
            st.success(f"**Vestimenta (Princípio de Segurança Normativo):** {v_seguranca}")

        with col_res_v[1]:
            st.write("#### Sensibilidade de Afastamento")
            st.table(pd.DataFrame(sens_list, columns=["Distância (mm)", "Energia (cal/cm²)", "Vestimenta"]))

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        col_c1, col_c2 = st.columns(2)
        uf_crea = col_c1.text_input("UF CREA:", "ES")
        num_crea = col_c2.text_input("Número CREA:", "")

        def gerar_pdf_profissional():
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            style_just = ParagraphStyle(name='Justify', parent=styles['Normal'], alignment=TA_JUSTIFY, leading=14)
            elementos = []

            elementos.append(Paragraph("<font size=16><b>RELATÓRIO TÉCNICO DE ESTUDO DE ARCO ELÉTRICO</b></font>", styles['Title']))
            elementos.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
            elementos.append(Spacer(1, 1*cm))

            elementos.append(Paragraph("<b>1. MEMORIAL DE CÁLCULO (NBR 17227:2025)</b>", styles['Heading2']))
            elementos.append(Paragraph(
                "A metodologia aplicada segue a <b>NBR 17227:2025</b>. Foram executados cálculos de Corrente de Arco via interpolação polinomial "
                "e determinação da Energia Incidente com ajuste do fator de borda para a geometria do invólucro.", style_just))

            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>2. ANÁLISE DO RESULTADO</b>", styles['Heading2']))
            elementos.append(Paragraph(
                f"Equipamento: <b>{r['Equip']}</b><br/>"
                f"Corrente de Arco: <b>{r['I']:.3f} kA</b><br/>"
                f"Energia Incidente: <b>{r['E_cal']:.4f} cal/cm²</b> ({r['E_joule']:.2f} J/cm²)<br/>"
                f"Fronteira de Arco (DLA): <b>{r['D']:.1f} mm</b>", style_just))
            
            elementos.append(Spacer(1, 0.3*cm))
            elementos.append(Paragraph(
                f"Pela classificação conforme cálculo, a vestimenta requerida é <b>{r['V_norma']}</b>. "
                f"Considerando o princípio de segurança normativo e o limiar de queimadura, recomenda-se <b>{r['V_seguranca']}</b>.", style_just))

            elementos.append(Spacer(1, 0.5*cm))
            elementos.append(Paragraph("<b>3. TABELA DE SENSIBILIDADE</b>", styles['Heading2']))
            data_tab = [["Distância (mm)", "Energia (cal/cm²)", "Vestimenta"]] + r['Sens']
            t = Table(data_tab, colWidths=[5*cm, 5*cm, 5*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elementos.append(t)

            elementos.append(Spacer(1, 2*cm))
            elementos.append(Paragraph("________________________________________________", styles['Normal']))
            elementos.append(Paragraph(f"<b>Engenheiro Eletricista - CREA {uf_crea}/{num_crea}</b>", styles['Normal']))

            doc.build(elementos); return buffer.getvalue()

        st.download_button("📩 Baixar Relatório (PDF)", gerar_pdf_profissional(), f"Laudo_{r['Equip']}.pdf")
