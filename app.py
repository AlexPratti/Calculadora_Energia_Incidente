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
st.set_page_config(page_title="Gestão de Arco Elétrico NBR 17227", layout="wide")
if 'auth' not in st.session_state: st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    t_login, t_reg = st.tabs(["Entrar", "Solicitar Acesso"])
    with t_login:
        u = st.text_input("Usuário (E-mail)", key="l_user")
        p = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar", key="l_btn"):
            if u == "admin" and p == "101049app":
                st.session_state['auth'] = {"role": "admin", "user": "Administrador"}
                st.rerun()
            else:
                try:
                    res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                    if res.data and res.data[0]['status'] == 'ativo':
                        st.session_state['auth'] = {"role": "user", "user": u}
                        st.rerun()
                    else: st.error("Acesso pendente ou incorreto.")
                except: st.error("Erro de conexão.")
    st.stop()

# --- 4. BASE DE DADOS ---
equip_data = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4, ""]}},
    "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"1143 x 762 x 762": [1143.0, 762.0, 762.0, ""]}},
    "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"660,4 x 660,4 x 660,4": [660.4, 660.4, 660.4, ""]}},
    "Conjunto de manobra 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4, ""], "1143 x 762 x 762": [1143.0, 762.0, 762.0, ""]}},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x ≤ 203,2": [355.6, 304.8, 203.2, "≤"]}},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"508,0 x 508,0 x > 508,0": [508.0, 508.0, 508.0, ">"]}},
    "Caixa de junção de cabos": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x ≤ 203,2": [355.6, 304.8, 203.2, "≤"], "508,0 x 508,0 x ≤ 203,2": [508.0, 508.0, 203.2, "≤"]}}
}

# --- 5. INTERFACE ---
tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos", "Relatório"])

with tab1:
    st.subheader("Configuração do Equipamento")
    equip_sel = st.selectbox("Selecione o Equipamento (Tab. 3):", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", list(info["dims"].keys()))
    val_a, val_l, val_p, val_sinal = info["dims"][sel_dim]

    st.write("#### Ajuste Manual de Dimensões")
    c1, c2 = st.columns(2)
    alt = c1.number_input("Altura [A] (mm)", value=float(val_a))
    larg = c2.number_input("Largura [L] (mm)", value=float(val_l))
    
    st.write("Profundidade [P] (mm)")
    cp1, cp2 = st.columns([1, 4]) # Layout alinhado: sinal menor, valor maior
    sinal_final = cp1.selectbox("Sinal", ["", "≤", ">"], index=["", "≤", ">"].index(val_sinal) if val_sinal in ["", "≤", ">"] else 0)
    prof = cp2.number_input("Valor P", value=float(val_p), label_visibility="collapsed")

    st.divider()
    st.write("#### Parâmetros da Tabela 3")
    gap_f = st.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = st.number_input("Distância de Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Cálculos")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Corrente Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)
    
    if st.button("Calcular Resultados"):
        k_ia = {600: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2700: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14300: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {600: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2700: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14300: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        ia_sts = [calc_ia_step(i_bf, gap_f, k_ia[v]) for v in [600, 2700, 14300]]
        en_sts = [calc_en_step(ia, i_bf, gap_f, dist_f, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        
        e_cal = interpolar(v_oc, *en_sts) / 4.184
        cat = "CAT 2" if e_cal <= 8 else "CAT 4" if e_cal <= 40 else "EXTREMO RISCO"
        
        st.session_state['res'] = {"E_cal": e_cal, "Cat": cat, "Equip": equip_sel} # Chave E_cal garantida aqui
        st.metric("Energia Incidente", f"{e_cal:.4f} cal/cm²")
        st.warning(f"Vestimenta: {cat}")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.write(f"### Laudo Técnico: {r['Equip']}")
        def pdf_gen():
            b = io.BytesIO(); c = canvas.Canvas(b, pagesize=A4)
            c.drawString(2*cm, 25*cm, f"Equipamento: {r['Equip']}")
            # CORREÇÃO DA CHAVE: Usando r['E_cal'] que foi definida no botão Calcular
            c.drawString(2*cm, 24*cm, f"Energia Incidente: {r['E_cal']:.4f} cal/cm²") 
            c.save(); return b.getvalue()
        st.download_button("Baixar PDF", pdf_gen(), "laudo.pdf")
    else:
        st.info("⚠️ Realize o cálculo na Aba 2 primeiro para habilitar o relatório.")
