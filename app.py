import streamlit as st
import numpy as np
import io
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# --- 1. CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="NBR 17227 - Gestão de Arco Elétrico", layout="wide")

URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe" 

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
supabase = st.session_state.supabase

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

# --- 3. SISTEMA DE LOGIN (BLOQUEIO TOTAL) ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acesso Restrito - NBR 17227")
    t1, t2 = st.tabs(["Entrar", "Solicitar Acesso"])
    
    with t1:
        u = st.text_input("E-mail", key="log_u")
        p = st.text_input("Senha", type="password", key="log_p")
        if st.button("Acessar Aplicativo"):
            if u == "admin" and p == "101049app":
                st.session_state['auth'] = {"role": "admin", "user": "Administrador"}
                st.rerun()
            else:
                try:
                    res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                    if res.data:
                        user = res.data[0]
                        if user['status'] == 'ativo':
                            st.session_state['auth'] = {"role": "user", "user": u}
                            st.rerun()
                        else:
                            st.warning("Seu acesso ainda não foi aprovado pelo administrador.")
                    else:
                        st.error("Credenciais inválidas.")
                except:
                    st.error("Erro na conexão com o banco de dados.")
    with t2:
        ne = st.text_input("Novo E-mail", key="reg_u")
        np = st.text_input("Nova Senha", type="password", key="reg_p")
        if st.button("Enviar Cadastro"):
            supabase.table("usuarios").insert({"email": ne, "senha": np, "status": "pendente"}).execute()
            st.success("Solicitação enviada!")
    st.stop() # Interrompe a execução aqui se não estiver logado

# --- 4. CONTEÚDO PROTEGIDO (SÓ APARECE SE LOGADO) ---
st.sidebar.write(f"Usuário: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair / Logout"):
    st.session_state['auth'] = None
    st.rerun()

# Painel ADM
if st.session_state['auth']['role'] == "admin":
    with st.expander("⚙️ Gerenciar Usuários"):
        users = supabase.table("usuarios").select("*").execute()
        for user in users.data:
            c1, c2, c3 = st.columns(3)
            c1.write(user['email'])
            if user['status'] == 'pendente' and c2.button("Aprovar", key=f"ap_{user['email']}"):
                supabase.table("usuarios").update({"status": "ativo", "data_aprovacao": datetime.now(timezone.utc).isoformat()}).eq("email", user['email']).execute()
                st.rerun()
            if c3.button("Remover", key=f"rm_{user['email']}"):
                supabase.table("usuarios").delete().eq("email", user['email']).execute()
                st.rerun()

# --- 5. INTERFACE TÉCNICA (ABAS) ---
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

tab1, tab2, tab3 = st.tabs(["Configuração", "Cálculos", "Relatório"])

with tab1:
    st.subheader("Configuração")
    equip_sel = st.selectbox("Equipamento:", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox(f"Dimensões:", list(info["dims"].keys()))
    v_a, v_l, v_p, v_s = info["dims"][sel_dim]

    c1, c2, c3, c4 = st.columns(4)
    alt = c1.number_input("Altura [A]", value=float(v_a))
    larg = c2.number_input("Largura [L]", value=float(v_l))
    sinal_op = ["", "≤", ">"]
    sinal_final = c3.selectbox("Sinal P", sinal_op, index=sinal_op.index(v_s) if v_s in sinal_op else 0)
    prof = c4.number_input("Profundidade [P]", value=float(v_p))

    gap_f = st.number_input("GAP (mm)", value=float(info["gap"]))
    dist_f = st.number_input("Distância Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Processamento")
    col1, col2, col3 = st.columns(3)
    v_oc = col1.number_input("Tensão Voc (kV)", 0.208, 15.0, 13.8)
    i_bf = col2.number_input("Ibf (kA)", 0.5, 106.0, 4.85)
    t_arc = col3.number_input("Tempo T (ms)", 10.0, 5000.0, 488.0)
    
    if st.button("Executar Estudo"):
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

        cat_n = "CAT 1" if e_cal <= 4 else "CAT 2" if e_cal <= 8 else "CAT 4"
        cat_s = "CAT 2" if (e_cal > 1.2 and e_cal <= 8) else cat_n
        
        st.session_state['res'] = {"I": i_arc, "E": e_cal, "D": dla, "CatN": cat_n, "CatS": cat_s, "Equip": equip_sel}
        
        st.divider()
        st.metric("Iarc Final", f"{i_arc:.3f} kA")
        st.metric("Fronteira (DLA)", f"{dla:.1f} mm")
        st.metric("Energia Incidente", f"{e_cal:.4f} cal/cm²")
        st.info(f"Recomendação: {cat_s}")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader("Laudo")
        nome = st.text_input("Engenheiro:", "Seu Nome")
        crea = st.text_input("CREA:", "Seu Registro")
        
        def gerar_pdf():
            buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4)
            styles = getSampleStyleSheet(); elem = []
            elem.append(Paragraph("<b>LAUDO TÉCNICO NBR 17227</b>", styles['Title']))
            elem.append(Paragraph(f"<b>Equipamento:</b> {r['Equip']}", styles['Normal']))
            elem.append(Paragraph(f"<b>Energia:</b> {r['E']:.4f} cal/cm²", styles['Normal']))
            elem.append(Spacer(1, 1*cm))
            elem.append(Paragraph("<b>ANÁLISE DO RESULTADO:</b>", styles['Heading3']))
            elem.append(Paragraph(f"O valor calculado indica {r['CatN']}, mas recomenda-se {r['CatS']} por segurança operacional (limite 1,2 cal/cm²).", styles['Normal']))
            elem.append(Spacer(1, 2*cm))
            elem.append(Paragraph(f"{nome} - CREA: {crea}", styles['Normal']))
            doc.build(elem); return buf.getvalue()
        
        st.download_button("Baixar PDF", gerar_pdf(), "laudo.pdf")
