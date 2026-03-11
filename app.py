import streamlit as st
from supabase import create_client, Client
import numpy as np
import io
import pandas as pd
from datetime import datetime, timezone, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfgen import canvas

# 1. Configuração da página deve vir ANTES de qualquer outro comando Streamlit
st.set_page_config(page_title="Gestão de Arco Elétrico", layout="wide")

# 2. Configuração Supabase
URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co"
KEY_SUPABASE = "sb_publishable_zLiarara0IVVcwQm6oR2IQ_Sb0YOWTe"

# Inicialização direta (sem cache por enquanto para testar)
try:
    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
    supabase = st.session_state.supabase
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()


# --- FUNÇÕES DE APOIO ---
def enviar_solicitacao(email, senha):
    try:
        existente = supabase.table("usuarios").select("email").eq("email", email).execute()
        if existente.data:
            st.warning("Usuário já cadastrado!")
            return
        novo_usuario = {
            "email": email,
            "senha": senha,
            "status": "pendente",
            "data_solicitacao": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("usuarios").insert(novo_usuario).execute()
        st.success("Solicitação enviada com sucesso!")
    except Exception as e:
        st.error(f"Erro ao enviar solicitação: {e}")

# --- FUNÇÕES TÉCNICAS (NBR 17227:2025) ---
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

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("Outros Cálculos")
    st.link_button("Corrente de Curto-Circuito", "https://short-circuit-calc-e5u5dmgap2uqfdtbkc3d4e.streamlit.app", use_container_width=True)
    st.link_button("Banco de Capacitores", "https://c-lculobancocapacitores-tne9epqsrh64gtwaakzyax.streamlit.app", use_container_width=True)
# --- 3. SISTEMA DE LOGIN ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acesso ao Sistema NBR 17227")
    t1, t2 = st.tabs(["Entrar", "Solicitar Acesso"])
    
    with t1:
        u = st.text_input("Usuário (E-mail)")
        p = st.text_input("Senha", type="password")
        if st.button("Acessar"):
            if u == "admin" and p == "101049app":
                st.session_state['auth'] = {"role": "admin", "user": "Administrador"}
                st.rerun()
            else:
                try:
                    res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                    if res.data and len(res.data) > 0:
                        user_found = res.data[0]
                        if user_found['status'] == 'ativo':
                            data_str = user_found.get('data_aprovacao')
                            if data_str:
                                data_ap = datetime.fromisoformat(data_str.replace('Z', '+00:00'))
                                if datetime.now(timezone.utc) > data_ap + timedelta(days=365):
                                    st.error("Acesso expirado.")
                                    st.stop()
                            st.session_state['auth'] = {"role": "user", "user": u}
                            st.rerun()
                        else:
                            st.warning(f"Status: {user_found['status'].upper()}. Aguarde aprovação.")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro no login: {e}")
    with t2:
        ne = st.text_input("Seu E-mail para cadastro")
        np_ = st.text_input("Crie uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            enviar_solicitacao(ne, np_)
    st.stop()

# --- 4. INTERFACE PRINCIPAL ---
st.sidebar.write(f"Conectado: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair"):
    st.session_state['auth'] = None
    if 'res' in st.session_state: del st.session_state['res']
    st.rerun()

# --- 4. PAINEL DO ADMINISTRADOR (Versão de Diagnóstico) ---
if st.session_state['auth']['role'] == "admin":
    with st.expander("⚙️ Painel de Controle de Usuários"):
        try:
            # Buscando todos os usuários
            users_res = supabase.table("usuarios").select("*").execute()
            
            if not users_res.data:
                st.info("Nenhum usuário encontrado no banco de dados.")
            else:
                for user in users_res.data:
                    # Criando colunas para organizar a linha do usuário
                    c1, c2, c3 = st.columns([2, 1, 1])
                    
                    # Status e E-mail
                    status_icon = '🟢' if user.get('status') == 'ativo' else '🟡'
                    email_user = user.get('email', 'E-mail não encontrado')
                    c1.write(f"{status_icon} **{email_user}**")
                    
                    # Botão Aprovar (Apenas para pendentes)
                    if user.get('status') == 'pendente':
                        if c2.button("Aprovar", key=f"ap_{email_user}"):
                            supabase.table("usuarios").update({
                                "status": "ativo", 
                                "data_aprovacao": datetime.now(timezone.utc).isoformat()
                            }).eq("email", email_user).execute()
                            st.success(f"Aprovado: {email_user}")
                            st.rerun()
                    else:
                        c2.write("✅ Ativo")

                    # Botão Excluir
                    if c3.button("Excluir", key=f"ex_{email_user}"):
                        supabase.table("usuarios").delete().eq("email", email_user).execute()
                        st.warning(f"Excluído: {email_user}")
                        st.rerun()
                    st.divider() # Linha separadora entre usuários
                    
        except Exception as e:
            st.error(f"Erro ao carregar usuários: {e}")
            # Isso vai nos dizer exatamente qual coluna está faltando ou se há erro de permissão

# --- 5. BASE DE DADOS E ABAS ---
equip_data = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4, ""]}},
    "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"1143 x 762 x 762": [1143.0, 762.0, 762.0, ""]}},
    "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"660,4 x 660,4 x 660,4": [660.4, 660.4, 660.4, ""]}},
    "Conjunto de manobra 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4, ""], "1143 x 762 x 762": [1143.0, 762.0, 762.0, ""]}},
    "CCM e painel raso de BT": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x ≤ 203,2": [355.6, 304.8, 203.2, "≤"]}},
    "CCM e painel típico de BT": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x > 203,2": [355.6, 304.8, 203.2, ">"]}},
    "Conjunto de manobra BT": {"gap": 32.0, "dist": 609.6, "dims": {"508 x 508 x 508": [508.0, 508.0, 508.0, ""]}},
    "Caixa de junção de cabos": {"gap": 13.0, "dist": 457.2, "dims": {"355,6 x 304,8 x ≤ 203,2": [355.6, 304.8, 203.2, "≤"], "355,6 x 304,8 x > 203,2": [355.6, 304.8, 203.2, ">"]}}
}

tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório Final"])

with tab1:
    st.subheader("Configuração do Equipamento")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equip_data.keys()))
    info = equip_data[equip_sel]
    sel_dim = st.selectbox("Selecione o Invólucro:", list(info["dims"].keys()))
    v_a, v_l, v_p, v_s = info["dims"][sel_dim]
    c1, c2, c3, c4 = st.columns(4)
    alt, larg = c1.number_input("Altura (mm)", value=float(v_a)), c2.number_input("Largura (mm)", value=float(v_l))
    sinal_f = c3.selectbox("Sinal P", ["", "≤", ">"], index=["", "≤", ">"].index(v_s) if v_s in ["", "≤", ">"] else 0)
    prof = c4.number_input("Profundidade (mm)", value=float(v_p))
    gap_f, dist_f = st.number_input("GAP (mm)", value=float(info["gap"])), st.number_input("Distância Trabalho (mm)", value=float(info["dist"]))

with tab2:
    st.subheader("Análise de Arco Elétrico")
    col1, col2, col3 = st.columns(3)
    v_oc, i_bf, t_arc = col1.number_input("Voc (kV)", 0.208, 15.0, 13.8), col2.number_input("Ibf (kA)", 0.5, 106.0, 4.85), col3.number_input("T (ms)", 10.0, 5000.0, 488.0)
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
        sens_list = []
        for d in np.linspace(dist_f, dla, 5):
            e_sts_temp = [calc_en_step(ia, i_bf, gap_f, d, t_arc, k_en[v], cf) for ia, v in zip(ia_sts, k_v)]
            e_v = interpolar(v_oc, *e_sts_temp) / 4.184
            sens_list.append([f"{d:.1f}", f"{e_v:.4f}", definir_vestimenta(e_v)])
        e_trab_cal = float(sens_list[0][1])
        v_norma = definir_vestimenta(e_trab_cal)
        v_seguranca = "CAT 2" if (1.2 < e_trab_cal <= 4) else v_norma
        st.session_state['res'] = {"I": i_arc, "D": dla, "E_cal": e_trab_cal, "E_joule": e_trab_cal*4.184, "V_norma": v_norma, "V_seguranca": v_seguranca, "Sens": sens_list, "Equip": equip_sel, "Gap": gap_f, "Dist": dist_f}
        st.rerun()

    if 'res' in st.session_state:
        r = st.session_state['res']
        st.metric("Iarc", f"{r['I']:.3f} kA"), st.metric("DLA", f"{r['D']:.1f} mm")
        st.write(f"**Energia Incidente:** {r['E_cal']:.4f} cal/cm²")
        st.table(pd.DataFrame(r['Sens'], columns=["Distância (mm)", "Energia", "Vestimenta"]))

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        cliente = st.text_input("Cliente:", "Empresa Exemplo")
        def gerar_pdf_profissional():
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [Paragraph(f"Relatório: {cliente}", styles['Title']), Paragraph(f"Equipamento: {r['Equip']}", styles['Normal']), Spacer(1, 1*cm)]
            t = Table([["Distância (mm)", "Energia", "Vestimenta"]] + r['Sens'])
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey), ('GRID',(0,0),(-1,-1),1,colors.black)]))
            elements.append(t)
            doc.build(elements); return buffer.getvalue()
        st.download_button("📩 Baixar PDF", gerar_pdf_profissional(), f"Relatorio_{cliente}.pdf")
    else:
        st.info("💡 Realize o cálculo primeiro.")
