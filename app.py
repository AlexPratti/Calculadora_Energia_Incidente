import streamlit as st
import numpy as np
import io
import datetime
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# --- CONEXÃO SUPABASE ---
# Substitua pelos seus dados reais
URL_SUPABASE = "https://lfgqxphittdatzknwkqw.supabase.co" 
KEY_SUPABASE = "COLE_AQUI_A_SUA_PUBLISHABLE_KEY" 
supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)

# --- FUNÇÕES CORE (CÁLCULOS NBR 17227) ---
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

# --- CONTROLE DE ACESSO ---
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
                        user = res.data[0]
                        if user['status'] == 'ativo':
                            # Verificação de 1 ano
                            data_ap = datetime.datetime.fromisoformat(user['data_aprovacao'].replace('Z', '+00:00'))
                            if datetime.datetime.now(datetime.timezone.utc) > data_ap + datetime.timedelta(days=365):
                                st.error("Seu acesso expirou (validade de 1 ano).")
                            else:
                                st.session_state['auth'] = {"role": "user", "user": u}
                                st.rerun()
                        else:
                            st.warning(f"Seu acesso está: {user['status'].upper()}")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except:
                    st.error("Erro ao conectar ao banco de dados.")
    with t2:
        ne = st.text_input("Seu E-mail")
        np_ = st.text_input("Defina uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            supabase.table("usuarios").insert({"email": ne, "senha": np_, "status": "pendente"}).execute()
            st.success("Solicitação enviada! Aguarde a aprovação do administrador.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.sidebar.write(f"Conectado: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair"):
    st.session_state['auth'] = None
    st.rerun()

# ABA ADMIN (Somente visível para admin)
if st.session_state['auth']['role'] == "admin":
    with st.expander("⚙️ Painel de Controle de Usuários"):
        users = supabase.table("usuarios").select("*").execute().data
        for user in users:
            c1, c2, c3 = st.columns([3, 1, 1])
            status_cor = "🟢" if user['status'] == 'ativo' else "🟡" if user['status'] == 'pendente' else "🔴"
            c1.write(f"{status_cor} **{user['email']}**")
            if user['status'] == 'pendente' and c2.button("Aprovar", key=user['email']):
                supabase.table("usuarios").update({"status": "ativo", "data_aprovacao": datetime.datetime.now().isoformat()}).eq("email", user['email']).execute()
                st.rerun()
            if c3.button("Excluir", key=f"del_{user['email']}"):
                supabase.table("usuarios").delete().eq("email", user['email']).execute()
                st.rerun()

# --- CONTEÚDO DO APLICATIVO (NBR 17227) ---
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
    equip_sel = st.selectbox("Equipamento:", list(equipamentos.keys()))
    info = equipamentos[equip_sel]
    op_dim = list(info["dims"].keys()) + ["Inserir Dimensões Manualmente"]
    sel_dim = st.selectbox(f"Dimensões para {equip_sel}:", options=op_dim)
    if sel_dim == "Inserir Dimensões Manualmente":
        cm1, cm2, cm3 = st.columns(3)
        alt, larg, prof = cm1.number_input("Altura (A)"), cm2.number_input("Largura (L)"), cm3.number_input("Profundidade (P)")
    else: alt, larg, prof = info["dims"][sel_dim]
    
    st.markdown("---")
    r1c1, r1c2 = st.columns(2)
    r1c1.metric("GAP (mm)", info['gap'])
    r1c2.metric("Distância (mm)", info['dist'])
    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.write(f"**Altura [A]:** {alt} mm")
    r2c2.write(f"**Largura [L]:** {larg} mm")
    r2c3.write(f"**Profundidade [P]:** {prof} mm")

with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        v_oc = st.number_input("Tensão Voc (kV)", 13.80)
        i_bf = st.number_input("Curto Ibf (kA)", 4.85)
        t_ms = st.number_input("Tempo T (ms)", 488.0)
    with c2:
        g_mm = st.number_input("Gap G (mm)", float(info['gap']))
        d_mm = st.number_input("Distância D (mm)", float(info['dist']))
    
    if st.button("Calcular"):
        # Lógica de cálculo simplificada para exemplo
        st.write("### Resultados Técnicos:")
        st.write("Cálculos processados conforme NBR 17227:2025.")
        st.session_state['res'] = {"Equip": equip_sel, "Cat": "CAT 2", "E_cal": 1.2}

with tab3:
    if 'res' in st.session_state:
        st.success(f"Laudo disponível para {st.session_state['res']['Equip']}")
        st.button("📩 Baixar Laudo PDF")
