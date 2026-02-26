import streamlit as st
import numpy as np
import io
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# --- 1. CONEXÃO COM O BANCO DE DADOS (SUPABASE) ---
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
                st.session_state['auth'] = {"role": "admin", "user": "Administrador"}
                st.rerun()
            else:
                try:
                    res = supabase.table("usuarios").select("*").eq("email", u).eq("senha", p).execute()
                    if res.data:
                        user_data = res.data[0]
                        if user_data['status'] == 'ativo':
                            data_ap = datetime.fromisoformat(user_data['data_aprovacao'].replace('Z', '+00:00'))
                            if datetime.now(timezone.utc) > data_ap + timedelta(days=365):
                                st.error("Acesso expirado (validade de 1 ano).")
                            else:
                                st.session_state['auth'] = {"role": "user", "user": u}
                                st.rerun()
                        else:
                            st.warning(f"Acesso: {user_data['status'].upper()}")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")
    with t2:
        ne = st.text_input("Novo E-mail")
        np_ = st.text_input("Nova Senha", type="password")
        if st.button("Enviar Solicitação"):
            try:
                supabase.table("usuarios").insert({"email": ne, "senha": np_, "status": "pendente"}).execute()
                st.success("Solicitação enviada!")
            except:
                st.error("Erro ao enviar solicitação.")
    st.stop()

# --- 4. INTERFACE PRINCIPAL ---
st.sidebar.write(f"Conectado: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair"):
    st.session_state['auth'] = None
    st.rerun()

if st.session_state['auth']['role'] == "admin":
    with st.expander("⚙️ Painel de Controle de Usuários"):
        try:
            users = supabase.table("usuarios").select("*").execute().data
            if users:
                for user in users:
                    c1, c2, c3 = st.columns()
                    status_icon = "🟢" if user['status'] == 'ativo' else "🟡"
                    c1.write(f"{status_icon} **{user['email']}**")
                    if user['status'] == 'pendente' and c2.button("Aprovar", key=user['email']):
                        supabase.table("usuarios").update({"status": "ativo", "data_aprovacao": datetime.now(timezone.utc).isoformat()}).eq("email", user['email']).execute()
                        st.rerun()
                    if c3.button("Excluir", key=f"del_{user['email']}"):
                        supabase.table("usuarios").delete().eq("email", user['email']).execute()
                        st.rerun()
        except Exception as e:
            st.error(f"Erro no painel: {e}")

# --- 5. ABAS TÉCNICAS ---
equipamentos = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4]}},
    "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"1143 x 762 x 762": [1143.0, 762.0, 762.0]}},
    "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"660,4 x 660,4 x 660,4": [660.4, 660.4, 660.4]}},
    "Conjunto de manobra 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4], "1143 x 762 x 762": [1143.0, 762.0, 762.0]}},
    "CCM e painel BT": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x ≤203,2": [355.6, 304.8, 203.2]}},
}

tab1, tab2, tab3 = st.tabs(["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório"])

with tab1:
    st.subheader("Configuração")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equipamentos.keys()))
    info = equipamentos[equip_sel]
    op_dim = list(info["dims"].keys()) + ["Inserir Dimensões Manualmente"]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", options=op_dim)
    if sel_dim == "Inserir Dimensões Manualmente":
        c_m1, c_m2, c_m3 = st.columns(3)
        alt, larg, prof = c_m1.number_input("Altura [A]"), c_m2.number_input("Largura [L]"), c_m3.number_input("Profundidade [P]")
    else: alt, larg, prof = info["dims"][sel_dim]
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("GAP (mm)", f"{info['gap']}"); c2.metric("Distância (mm)", f"{info['dist']}")
    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.write(f"**Altura [A]:** {alt} mm"); r2c2.write(f"**Largura [L]:** {larg} mm"); r2c3.write(f"**Profundidade [P]:** {prof} mm")

with tab2:
    col1, col2, col3 = st.columns(3)
    with col1:
        v_oc, i_bf, tempo_t = st.number_input("Tensão Voc (kV)", 13.80), st.number_input("Curto Ibf (kA)", 4.85), st.number_input("Tempo T (ms)", 488.0)
    with col2:
        gap_g, dist_d = st.number_input("Gap G (mm)", float(info['gap'])), st.number_input("Distância D (mm)", float(info['dist']))
    if st.button("Calcular Resultados"):
        k_ia = {600: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2700: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14300: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {600: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2700: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14300: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        ees = (alt/25.4 + larg/25.4) / 2.0; cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        # CORREÇÃO DA LINHA 179:
        ia_sts = [calc_ia_step(i_bf, gap_g, k_ia[v]) for v in [600, 2700, 14300]]
        en_sts = [calc_en_step(ia, i_bf, gap_g, dist_d, tempo_t, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        dl_sts = [calc_dla_step(ia, i_bf, gap_g, tempo_t, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        ia_f = interpolar(v_oc, *ia_sts); e_cal = interpolar(v_oc, *en_sts)/4.184; dla_f = interpolar(v_oc, *dl_sts)
        cat = "CAT 2" if e_cal <= 8 else "CAT 4" if e_cal <= 40 else "EXTREMO RISCO"
        st.session_state['res'] = {"Ia": ia_f, "E_cal": e_cal, "DLA": dla_f, "Cat": cat, "Voc": v_oc, "Equip": equip_sel, "Gap": gap_g, "Dist": dist_d, "Dim": f"{alt}x{larg}x{prof}", "Ibf": i_bf, "Tempo": tempo_t}
        st.divider(); st.write("### Resultados Técnicos:"); st.write(f"**Energia:** {e_cal:.4f} cal/cm²"); st.warning(f"🛡️ Vestimenta: {cat}")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader(f"Laudo Técnico - {r['Equip']}")
        def export_pdf():
            buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica-Bold", 14); c.drawString(7.5*cm, 27.5*cm, "LAUDO TÉCNICO NBR 17227")
            c.setFont("Helvetica", 10); y = 25*cm
            for text in [f"Equipamento: {r['Equip']}", f"Energia: {r['E_cal']:.4f} cal/cm²", f"Vestimenta: {r['Cat']}"]:
                c.drawString(1.5*cm, y, text); y -= 0.6*cm
            c.save(); return buf.getvalue()
        st.download_button("📩 Baixar Laudo PDF", export_pdf(), "laudo.pdf", "application/pdf")
    else: st.info("⚠️ Calcule primeiro.")
