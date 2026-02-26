import streamlit as st
import numpy as np
import io
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

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
                            data_str = user_found['data_aprovacao'].replace('Z', '+00:00')
                            data_ap = datetime.fromisoformat(data_str).astimezone(timezone.utc)
                            if datetime.now(timezone.utc) > data_ap + timedelta(days=365):
                                st.error("Acesso expirado (validade de 1 ano).")
                            else:
                                st.session_state['auth'] = {"role": "user", "user": u, "email": u}
                                st.rerun()
                        else: st.warning(f"Status: {user_found['status'].upper()}. Aguarde aprovação.")
                    else: st.error("Dados incorretos.")
                except Exception as e: st.error(f"Erro de conexão: {e}")
    with t2:
        ne = st.text_input("Novo E-mail")
        np_ = st.text_input("Defina uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            try:
                supabase.table("usuarios").insert({"email": ne, "senha": np_, "status": "pendente"}).execute()
                st.success("Solicitação enviada!")
            except: st.error("E-mail já cadastrado.")
    st.stop()

# --- 4. INTERFACE PRINCIPAL ---
st.sidebar.write(f"Conectado: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair do Sistema"):
    st.session_state['auth'] = None
    st.rerun()

abas_nomes = ["Equipamento/Dimensões", "Cálculos e Resultados", "Relatório", "👤 Minha Conta"]
if st.session_state['auth']['role'] == "admin":
    abas_nomes.append("⚙️ Admin")

tabs = st.tabs(abas_nomes)

# --- 5. ABA 1: EQUIPAMENTO/DIMENSÕES ---
with tabs[0]:
    equipamentos = {
        "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4]}},
        "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"1143 x 762 x 762": [1143.0, 762.0, 762.0]}},
        "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"660,4 x 660,4 x 660,4": [660.4, 660.4, 660.4]}},
        "Conjunto de manobra 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4], "1143 x 762 x 762": [1143.0, 762.0, 762.0]}},
        "CCM e painel BT": {"gap": 25.0, "dist": 457.2, "dims": {"355,6 x 304,8 x ≤203,2": [355.6, 304.8, 203.2]}},
    }
    st.subheader("Configuração de Equipamento")
    equip_sel = st.selectbox("Selecione o Equipamento:", list(equipamentos.keys()))
    info = equipamentos[equip_sel]
    op_dim = list(info["dims"].keys()) + ["Inserir Manualmente"]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", options=op_dim)
    if sel_dim == "Inserir Manualmente":
        c_m = st.columns(3)
        alt, larg, prof = c_m.number_input("A"), c_m.number_input("L"), c_m.number_input("P")
    else: alt, larg, prof = info["dims"][sel_dim]
    
    st.markdown("---")
    # Linha 1: GAP e Distância
    c1, c2 = st.columns(2)
    c1.write("**GAP (mm)**"); c1.write(f"## {info['gap']}")
    c2.write("**Distância (mm)**"); c2.write(f"## {info['dist']}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    # Linha 2: A, L e P com o mesmo tamanho (##)
    c4, c5, c6 = st.columns(3)
    c4.write("**Altura [A] (mm)**"); c4.write(f"## {alt}")
    c5.write("**Largura [L] (mm)**"); c5.write(f"## {larg}")
    c6.write("**Profundidade [P] (mm)**"); c6.write(f"## {prof}")

# --- 6. ABA 2: CÁLCULOS E RESULTADOS ---
with tabs[1]:
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        v_oc = st.number_input("Tensão Voc (kV)", 13.80, format="%.2f")
        i_bf = st.number_input("Curto Ibf (kA)", 4.85, format="%.2f")
        t_ms = st.number_input("Tempo T (ms)", 488.0, format="%.2f") # T abaixo do Ibf
    with col_c2:
        gap_g = st.number_input("Gap G (mm)", float(info['gap']), format="%.2f")
        dist_d = st.number_input("Distância D (mm)", float(info['dist']), format="%.2f")
    
    if st.button("Calcular Resultados"):
        k_ia = {600: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2700: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14300: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {600: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2700: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14300: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        ees = (alt/25.4 + larg/25.4) / 2.0; cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        ia_sts = [calc_ia_step(i_bf, gap_g, k_ia[v]) for v in [600, 2700, 14300]]
        en_sts = [calc_en_step(ia, i_bf, gap_g, dist_d, t_ms, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        dl_sts = [calc_dla_step(ia, i_bf, gap_g, t_ms, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        ia_f = interpolar(v_oc, *ia_sts); e_j = interpolar(v_oc, *en_sts); e_cal = e_j / 4.184; dla_f = interpolar(v_oc, *dl_sts)
        cat = "CAT 2" if e_cal <= 8 else "CAT 4" if e_cal <= 40 else "EXTREMO RISCO"
        st.session_state['res'] = {"Ia": ia_f, "E_cal": e_cal, "E_j": e_j, "DLA": dla_f, "Cat": cat, "Voc": v_oc, "Equip": equip_sel, "Dim": f"{alt}x{larg}x{prof}"}
        
        st.divider()
        st.write("### Resultados Técnicos:")
        st.write(f"**Corrente de Arco Final (Ia_Final):** {ia_f:.4f} kA")
        st.write(f"**Energia Incidente (cal/cm²):** {e_cal:.4f}")
        st.write(f"**Energia Incidente (J/cm²):** {e_j:.4f}")
        st.write(f"**Fronteira de Segurança (DLA):** {dla_f:.0f} mm")
        st.warning(f"🛡️ Vestimenta Sugerida: **{cat}**")

# --- 7. ABA 3: RELATÓRIO ---
with tabs[2]:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.write(f"Laudo Técnico para {r['Equip']}")
        def export_pdf():
            buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica-Bold", 14); c.drawString(7.5*cm, 27.5*cm, "LAUDO TÉCNICO NBR 17227")
            c.setFont("Helvetica", 10); y = 25*cm
            fields = [f"Equipamento: {r['Equip']}", f"Energia: {r['E_cal']:.4f} cal/cm²", f"Fronteira: {r['DLA']:.0f} mm", f"Vestimenta: {r['Cat']}"]
            for text in fields: c.drawString(1.5*cm, y, text); y -= 0.6*cm
            c.save(); return buf.getvalue()
        st.download_button("📩 Baixar PDF", export_pdf(), "laudo.pdf", "application/pdf")
    else: st.info("⚠️ Calcule para gerar o laudo.")

# --- 8. ABA: MINHA CONTA & ADMIN (FILTROS) ---
with tabs[3]:
    st.subheader("Alterar Senha")
    nova_p = st.text_input("Nova Senha", type="password")
    if st.button("Salvar Senha"):
        if st.session_state['auth']['user'] == "admin": st.warning("Altere o admin no código.")
        else:
            supabase.table("usuarios").update({"senha": nova_p}).eq("email", st.session_state['auth']['email']).execute()
            st.success("Senha atualizada!")

if st.session_state['auth']['role'] == "admin":
    with tabs[4]:
        st.subheader("Painel Administrativo")
        users_all = supabase.table("usuarios").select("*").execute().data
        f_col1, f_col2 = st.columns(2)
        filtro_status = f_col1.selectbox("Status:", ["Todos", "ativo", "pendente"])
        busca_email = f_col2.text_input("E-mail:")
        u_filt = [u for u in users_all if (filtro_status == "Todos" or u['status'] == filtro_status) and (busca_email.lower() in u['email'].lower())]
        for u in u_filt:
            ca = st.columns(3)
            ca[0].write(f"**{u['email']}**")
            if u['status'] == 'pendente' and ca[1].button("Aprovar", key=u['email']):
                supabase.table("usuarios").update({"status": "ativo", "data_aprovacao": datetime.now(timezone.utc).isoformat()}).eq("email", u['email']).execute(); st.rerun()
            if ca[2].button("❌", key=f"del_{u['email']}"): supabase.table("usuarios").delete().eq("email", u['email']).execute(); st.rerun()
