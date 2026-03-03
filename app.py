import streamlit as st
import numpy as np
import io
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

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

def interpolar(v, f600, f2700, f14300):
    if v <= 0.6: return f600
    if v <= 2.7: return f600 + (f2700 - f600) * (v - 0.6) / 2.1
    return f2700 + (f14300 - f2700) * (v - 2.7) / 11.6

# --- 3. SISTEMA DE LOGIN ---
st.set_page_config(page_title="Gestão de Arco Elétrico", layout="wide")
if 'auth' not in st.session_state: st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    t_login, t_reg = st.tabs(["Entrar", "Solicitar Acesso"])
    with t_login:
        u = st.text_input("Usuário (E-mail)", key="login_u")
        p = st.text_input("Senha", type="password", key="login_p")
        if st.button("Acessar", key="btn_login"):
            if u == "admin" and p == "101049app":
                st.session_state['auth'] = {"role": "admin", "user": "Administrador"}
                st.rerun()
            else:
                res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                if res.data and res.data[0]['status'] == 'ativo':
                    st.session_state['auth'] = {"role": "user", "user": u}
                    st.rerun()
                else: st.error("Acesso negado ou pendente.")
    st.stop()

# --- 6. EQUIPAMENTOS E DIMENSÕES (Tabelas 1 e 3) ---
equipamentos = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"Padrão": [914.4, 914.4, 914.4]}, "pref": ""},
    "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"Padrão": [1143.0, 762.0, 762.0]}, "pref": ""},
    "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"Padrão": [660.4, 660.4, 660.4]}, "pref": ""},
    "Conjunto de manobra 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"Padrão": [914.4, 914.4, 914.4]}, "pref": ""},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"Padrão": [355.6, 304.8, 203.2]}, "pref": "≤"},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"Padrão": [508.0, 508.0, 508.0]}, "pref": ">"},
    "Caixa de junção de cabos": {
        "gap": 25.0, "dist": 457.2, 
        "dims": {
            "Situação 1 (Rasa)": [355.6, 304.8, 203.2],
            "Situação 2 (Típica)": [508.0, 508.0, 508.0]
        },
        "pref": "≤"
    }
}

tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos", "Relatório"])

with tab1:
    st.subheader("Configuração")
    equip_sel = st.selectbox("Selecione o Equipamento (Tab. 3):", list(equipamentos.keys()), key="equip")
    info = equipamentos[equip_sel]
    
    # Seleção de dimensão (necessário para Caixa de Junção)
    op_dim = list(info["dims"].keys())
    sel_dim = st.selectbox(f"Dimensões para {equip_sel} (Tab. 1):", options=op_dim, key="dim")
    
    a_p, l_p, p_p = info["dims"][sel_dim]
    
    c_m1, c_m2 = st.columns(2)
    alt = c_m1.number_input("Altura [A] (mm)", value=float(a_p))
    larg = c_m2.number_input("Largura [L] (mm)", value=float(l_p))
    
    c_p1, c_p2 = st.columns([1, 3])
    sinal = c_p1.selectbox("Sinal", ["", "≤", ">"], index=(1 if info["pref"] == "≤" else 2 if info["pref"] == ">" else 0))
    prof = c_p2.number_input("Profundidade [P] (mm)", value=float(p_p))

    st.info(f"**GAP Padrão:** {info['gap']} mm | **Distância de Trabalho Padrão:** {info['dist']} mm")
    gap_final = st.number_input("Ajustar GAP (mm)", value=float(info["gap"]))
    dist_final = st.number_input("Ajustar Distância de Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Cálculos NBR 17227")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Corrente Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)
    
    if st.button("Calcular"):
        k_ia = {600: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2700: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14300: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {600: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2700: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14300: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        ia_sts = [calc_ia_step(i_bf, gap_final, k_ia[v]) for v in [600, 2700, 14300]]
        en_sts = [calc_en_step(ia, i_bf, gap_final, dist_final, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        
        e_cal = interpolar(v_oc, *en_sts) / 4.184
        cat = "CAT 2" if e_cal <= 8 else "CAT 4" if e_cal <= 40 else "EXTREMO RISCO"
        
        st.session_state['res'] = {"E_cal": e_cal, "Cat": cat, "Equip": equip_sel}
        st.metric("Energia Incidente", f"{e_cal:.4f} cal/cm²")
        st.warning(f"Vestimenta: {cat}")

with tab3:
    if 'res' in st.session_state:
        st.write(f"Relatório gerado para {st.session_state['res']['Equip']}")
        if st.button("Exportar PDF"):
            buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
            c.drawString(2*cm, 25*cm, f"Equipamento: {st.session_state['res']['Equip']}")
            c.drawString(2*cm, 24*cm, f"Energia Incidente: {st.session_state['res']['E_cal']:.4f} cal/cm²")
            c.save(); st.download_button("Baixar", buf.getvalue(), "relatorio.pdf")
