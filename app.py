import streamlit as st
import numpy as np
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# --- 1. CONEXÃO SUPABASE ---
URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe"

try:
    supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)
except Exception as e:
    st.error(f"Erro no Banco de Dados: {e}")
    st.stop()

# --- 2. FUNÇÕES TÉCNICAS ---
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

# --- 3. LOGIN (SIMPLIFICADO PARA TESTE) ---
st.set_page_config(page_title="Gestão de Arco Elétrico", layout="wide")
if 'auth' not in st.session_state: st.session_state['auth'] = {"role": "admin", "user": "admin"} # Pular login para teste

# --- 4. INTERFACE ---
abas_nomes = ["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório"]
tabs = st.tabs(abas_nomes)

# ABA 1: DIMENSÕES
with tabs[0]:
    equipamentos = {
        "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4]}},
        "CCM e painel BT": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x 203,2": [355.6, 304.8, 203.2]}},
    }
    equip_sel = st.selectbox("Equipamento:", list(equipamentos.keys()))
    info = equipamentos[equip_sel]
    sel_dim = st.selectbox("Dimensões:", list(info["dims"].keys()) + ["Manual"])
    
    if sel_dim == "Manual":
        c_m = st.columns(3)
        alt = c_m[0].number_input("Altura (A)", value=500.0)
        larg = c_m[1].number_input("Largura (L)", value=500.0)
        prof = c_m[2].number_input("Profundidade (P)", value=500.0)
    else:
        alt, larg, prof = info["dims"][sel_dim]

# ABA 2: CÁLCULOS
with tabs[1]:
    col1, col2 = st.columns(2)
    v_oc = col1.number_input("Tensão (kV)", 13.8)
    i_bf = col1.number_input("Ibf (kA)", 4.85)
    t_ms = col2.number_input("Tempo (ms)", 488.0)
    
    if st.button("Calcular"):
        # Coeficientes simplificados para o exemplo
        k_ia = {600: [-0.042, 1.03, -0.08, 0,0,0,0,0,0,1.09], 2700: [0.006, 1.0, -0.02, 0,0,0,0,0,0,0.97], 14300: [0.005, 1.01, -0.01, 0,0,0,0,0,0,0.97]}
        k_en = {600: [0.75, 0.56, 1.75, 0,0,0,0,0,0,1.09, 0, -1.59, 0.95], 2700: [2.4, 0.16, 0.35, 0,0,0,0,0,0,0.97, 0, -1.56, 0.97], 14300: [3.8, 0.11, -0.99, 0,0,0,0,0,0,0.97, 0, -1.56, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        # Cálculo em 3 pontos para interpolação
        ia_n = [calc_ia_step(i_bf, info['gap'], k_ia[v]) for v in [600, 2700, 14300]]
        en_n = [calc_en_step(ia, i_bf, info['gap'], info['dist'], t_ms, k_en[v], cf) for ia, v in zip(ia_n, [600, 2700, 14300])]
        dl_n = [calc_dla_step(ia, i_bf, info['gap'], t_ms, k_en[v], cf) for ia, v in zip(ia_n, [600, 2700, 14300])]
        
        ia_f = interpolar(v_oc, ia_n[0], ia_n[1], ia_n[2])
        en_cal = interpolar(v_oc, en_n[0], en_n[1], en_n[2])
        en_j = en_cal * 4.184
        dla_f = interpolar(v_oc, dl_n[0], dl_n[1], dl_n[2])
        
        # Vestimenta
        if en_cal <= 1.2: epi = "Algodão"
        elif en_cal <= 8: epi = "CAT 2"
        else: epi = "CAT 4"
        
        st.divider()
        st.subheader("Resultados:")
        r1, r2, r3 = st.columns(3)
        r1.metric("Iarc Final", f"{ia_f:.2f} kA")
        r2.metric("Energia (cal/cm²)", f"{en_cal:.2f}")
        r3.metric("Energia (J/cm²)", f"{en_j:.2f}")
        st.info(f"DLA: {dla_f:.0f} mm | Vestimenta: {epi}")
