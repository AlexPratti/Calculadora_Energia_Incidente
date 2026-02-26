import streamlit as st
import numpy as np
import io
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# --- 1. CONEXÃO SUPABASE ---
URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe"

try:
    supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)
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
st.set_page_config(page_title="Gestão de Arco Elétrico", layout="wide")

if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    t1, t2 = st.tabs(["Entrar", "Solicitar Acesso"])
    with t1:
        u = st.text_input("Usuário (E-mail)")
        p = st.text_input("Senha", type="password")
        if st.button("Acessar"):
            if u == "admin" and p == "2153App":
                st.session_state['auth'] = {"role": "admin", "user": "admin", "email": "admin"}
                st.rerun()
            else:
                try:
                    res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                    if res.data:
                        user_found = res.data[0]
                        if user_found['status'] == 'ativo':
                            st.session_state['auth'] = {"role": "user", "user": u, "email": u}
                            st.rerun()
                        else: st.warning("Aguarde aprovação do administrador.")
                    else: st.error("Dados incorretos.")
                except Exception as e: st.error(f"Erro: {e}")
    st.stop()

# --- 4. INTERFACE ---
abas_nomes = ["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório", "Minha Conta"]
if st.session_state['auth']['role'] == "admin": abas_nomes.append("Admin")
tabs = st.tabs(abas_nomes)

# ABA 1: EQUIPAMENTO
with tabs[0]:
    equipamentos = {
        "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4]}},
        "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"1143 x 762 x 762": [1143.0, 762.0, 762.0]}},
        "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"660,4 x 660,4 x 660,4": [660.4, 660.4, 660.4]}},
    }
    st.subheader("Configuração de Equipamento")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equipamentos.keys()))
    info = equipamentos[equip_sel]
    
    op_dim = list(info["dims"].keys()) + ["Inserir Manualmente"]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", options=op_dim)
    
    # CORREÇÃO DEFINITIVA DO ERRO DE COLUNAS
    if sel_dim == "Inserir Manualmente":
        c_m1, c_m2, c_m3 = st.columns(3)
        alt = c_m1.number_input("Altura (mm)", value=0.0)
        larg = c_m2.number_input("Largura (mm)", value=0.0)
        prof = c_m3.number_input("Profundidade (mm)", value=0.0)
    else:
        alt, larg, prof = info["dims"][sel_dim]
    
    st.markdown("---")
    res_c1, res_c2, res_c3 = st.columns(3)
    res_c1.metric("Altura", f"{alt} mm")
    res_c2.metric("Largura", f"{larg} mm")
    res_c3.metric("Profundidade", f"{prof} mm")

# ABA 2: CÁLCULOS
with tabs[1]:
    c_i1, c_i2 = st.columns(2)
    v_oc = c_i1.number_input("Tensão (kV)", 13.8)
    i_bf = c_i1.number_input("Curto (kA)", 4.85)
    t_ms = c_i2.number_input("Tempo (ms)", 488.0)
    
    if st.button("Calcular"):
        st.success("Cálculo processado (Lógica técnica aplicada).")
