import streamlit as st
import numpy as np
import io
import datetime
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# --- 1. CONEXÃO COM O BANCO DE DADOS (SUPABASE) ---
# Substitua pelos seus dados do painel do Supabase (Settings > API)
URL_SUPABASE = "https://lfgqxphittdatzkmwkqw.supabase.co" 
KEY_SUPABASE = "COLE_AQUI_A_SUA_PUBLISHABLE_KEY" 

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

# --- 3. SISTEMA DE LOGIN E CONTROLE DE ACESSO ---
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
                        user = res.data[0]
                        if user['status'] == 'ativo':
                            # Verificação de validade de 1 ano
                            data_ap = datetime.datetime.fromisoformat(user['data_aprovacao'].replace('Z', '+00:00'))
                            if datetime.datetime.now(datetime.timezone.utc) > data_ap + datetime.timedelta(days=365):
                                st.error("Seu acesso expirou (validade de 1 ano atingida).")
                            else:
                                st.session_state['auth'] = {"role": "user", "user": u}
                                st.rerun()
                        else:
                            st.warning(f"Seu acesso está: {user['status'].upper()}. Aguarde aprovação.")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro ao conectar ao banco de dados: {e}")
    
    with t2:
        ne = st.text_input("Seu E-mail para cadastro")
        np_ = st.text_input("Crie uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            try:
                supabase.table("usuarios").insert({"email": ne, "senha": np_, "status": "pendente"}).execute()
                st.success("Solicitação enviada! O administrador revisará seu acesso.")
            except:
                st.error("Este e-mail já possui uma solicitação pendente ou cadastro.")
    st.stop()

# --- 4. INTERFACE PRINCIPAL ---
st.title("⚡ Gestão de Risco de Arco Elétrico - NBR 17227:2025")
st.sidebar.write(f"Conectado: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair do Sistema"):
    st.session_state['auth'] = None
    st.rerun()

# --- 5. PAINEL DO ADMINISTRADOR (CORRIGIDO) ---
if st.session_state['auth']['role'] == "admin":
    with st.expander("⚙️ Painel de Controle de Usuários", expanded=False):
        st.write("### Gerenciamento de Acessos")
        try:
            users_res = supabase.table("usuarios").select("*").execute()
            users_list = users_res.data
            
            if not users_list:
                st.info("Nenhum usuário cadastrado no banco de dados.")
            else:
                for user in users_list:
                    c1, c2, c3 = st.columns([3, 1, 1])
                    status_icon = "🟢" if user['status'] == 'ativo' else "🟡"
                    c1.write(f"{status_icon} **{user['email']}** ({user['status']})")
                    
                    if user['status'] == 'pendente':
                        if c2.button("Aprovar", key=f"ap_{user['email']}"):
                            supabase.table("usuarios").update({
                                "status": "ativo", 
                                "data_aprovacao": datetime.datetime.now().isoformat()
                            }).eq("email", user['email']).execute()
                            st.rerun()
                    
                    if c3.button("Excluir", key=f"del_{user['email']}"):
                        supabase.table("usuarios").delete().eq("email", user['email']).execute()
                        st.rerun()
        except Exception as e:
            st.error(f"Erro ao carregar usuários: {e}")

# --- 6. CONTEÚDO TÉCNICO DO APLICATIVO ---
equipamentos = {
    "CCM 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4]}},
    "Conjunto de manobra 15 kV": {"gap": 152.0, "dist": 914.4, "dims": {"1143 x 762 x 762": [1143.0, 762.0, 762.0]}},
    "CCM 5 kV": {"gap": 104.0, "dist": 914.4, "dims": {"660,4 x 660,4 x 660,4": [660.4, 660.4, 660.4]}},
    "Conjunto de manobra 5 kV": {
        "gap": 104.0, "dist": 914.4, 
        "dims": {"914,4 x 914,4 x 914,4": [914.4, 914.4, 914.4], "1143 x 762 x 762": [1143.0, 762.0, 762.0]}
    },
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
        alt = c_m1.number_input("Altura [A] (mm)", value=500.0)
        larg = c_m2.number_input("Largura [L] (mm)", value=500.0)
        prof = c_m3.number_input("Profundidade [P] (mm)", value=500.0)
    else:
        alt, larg, prof = info["dims"][sel_dim]

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("**GAP (mm)**")
        st.write(f"### {info['gap']}")
    with c2:
        st.write("**Distância Trabalho (mm)**")
        st.write(f"### {info['dist']}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    c4, c5, c6 = st.columns(3)
    with c4:
        st.write("**Altura [A]**")
        st.write(f"### {alt} mm")
    with c5:
        st.write("**Largura [L]**")
        st.write(f"### {larg} mm")
    with c6:
        st.write("**Profundidade [P]**")
        st.write(f"### {prof} mm")

with tab2:
    col1, col2, col3 = st.columns(3)
    with col1:
        v_oc = st.number_input("Tensão Voc (kV)", value=13.80, format="%.2f")
        i_bf = st.number_input("Curto Ibf (kA)", value=4.85, format="%.2f")
        tempo_t = st.number_input("Tempo T (ms)", value=488.0, format="%.2f")
    with col2:
        gap_g = st.number_input("Gap G (mm)", value=float(info['gap']), format="%.2f")
        dist_d = st.number_input("Distância D (mm)", value=float(info['dist']), format="%.2f")
    
    if st.button("Calcular Resultados"):
        # Coeficientes NBR 17227
        k_ia = {600: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 2700: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 14300: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]}
        k_en = {600: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 2700: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 14300: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]}
        
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        ia_sts = [calc_ia_step(i_bf, gap_g, k_ia[v]) for v in [600, 2700, 14300]]
        en_sts = [calc_en_step(ia, i_bf, gap_g, dist_d, tempo_t, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]
        dl_sts = [calc_dla_step(ia, i_bf, gap_g, tempo_t, k_en[v], cf) for ia, v in zip(ia_sts, [600, 2700, 14300])]

        ia_f = interpolar(v_oc, *ia_sts)
        e_j = interpolar(v_oc, *en_sts)
        e_cal = e_j / 4.184
        dla_f = interpolar(v_oc, *dl_sts)
        ia_min = ia_f * (1 - 0.5*(-0.0001*v_oc**2 + 0.0022*v_oc + 0.02))
        cat = "CAT 2" if e_cal <= 8 else "CAT 4" if e_cal <= 40 else "EXTREMO RISCO"

        st.session_state['res'] = {"Ia": ia_f, "IaMin": ia_min, "E_cal": e_cal, "E_j": e_j, "DLA": dla_f, "Cat": cat, "Voc": v_oc, "Equip": equip_sel, "Gap": gap_g, "Dist": dist_d, "Dim": f"{alt}x{larg}x{prof}", "Ibf": i_bf, "Tempo": tempo_t}
        
        st.divider()
        st.write("### Resultados Técnicos:")
        st.write(f"**Iarc Final:** {ia_f:.4f} kA")
        st.write(f"**Iarc Reduzida:** {ia_min:.4f} kA")
        st.write(f"**Energia Incidente (cal/cm²):** {e_cal:.4f}")
        st.write(f"**Energia Incidente (J/cm²):** {e_j:.4f}")
        st.write(f"**Fronteira (mm):** {dla_f:.0f}")
        st.warning(f"🛡️ Vestimenta Sugerida: **{cat}**")

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader(f"Laudo Técnico - {r['Equip']}")
        def export_pdf():
            buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
            c.setStrokeColor(colors.black); c.rect(1*cm, 25.5*cm, 19*cm, 3*cm)
            c.setFont("Helvetica-Bold", 14); c.drawString(7.5*cm, 27.5*cm, "LAUDO TÉCNICO")
            c.setFont("Helvetica", 10); y = 24*cm
            fields = [f"Equipamento: {r['Equip']}", f"Dimensões: {r['Dim']} mm", f"Gap: {r['Gap']} mm", f"Distância: {r['Dist']} mm", f"Energia: {r['E_cal']:.4f} cal/cm²", f"Vestimenta: {r['Cat']}"]
            for f in fields: c.drawString(1.5*cm, y, f); y -= 0.6*cm
            c.save(); return buf.getvalue()
        st.download_button("📩 Baixar Laudo PDF", export_pdf(), "laudo_arco.pdf", "application/pdf")
    else: st.info("⚠️ Execute o cálculo para habilitar o relatório.")

if __name__ == "__main__":
    pass # Main já executado pelo fluxo do Streamlit
