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
                        # Pega o primeiro item da lista de retorno
                        user_found = res.data[0] 
                        
                        if user_found['status'] == 'ativo':
                            # --- CORREÇÃO TÉCNICA DA DATA ---
                            # Garante que a data do banco seja lida com timezone UTC
                            data_str = user_found['data_aprovacao'].replace('Z', '+00:00')
                            data_ap = datetime.fromisoformat(data_str)
                            
                            # Compara com o 'agora' também em UTC
                            agora_utc = datetime.now(timezone.utc)
                            
                            if agora_utc > data_ap + timedelta(days=365):
                                st.error("Seu acesso expirou (validade de 1 ano atingida).")
                            else:
                                st.session_state['auth'] = {"role": "user", "user": u}
                                st.rerun()
                        else:
                            st.warning(f"Seu acesso está: {user_found['status'].upper()}. Aguarde aprovação.")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro de processamento: {e}")
    
    with t2:
        ne = st.text_input("Seu E-mail para cadastro")
        np_ = st.text_input("Crie uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            try:
                supabase.table("usuarios").insert({"email": ne, "senha": np_, "status": "pendente"}).execute()
                st.success("Solicitação enviada! O administrador revisará seu acesso.")
            except:
                st.error("Este e-mail já possui uma solicitação ou cadastro.")
    st.stop()

# --- 4. INTERFACE PRINCIPAL (SÓ CARREGA SE LOGADO) ---
st.title("⚡ Gestão de Risco de Arco Elétrico - NBR 17227:2025")
st.sidebar.write(f"Conectado: **{st.session_state['auth']['user']}**")
if st.sidebar.button("Sair do Sistema"):
    st.session_state['auth'] = None
    st.rerun()

# --- 5. PAINEL DO ADMINISTRADOR ---
if st.session_state['auth']['role'] == "admin":
    with st.expander("⚙️ Painel de Controle de Usuários", expanded=False):
        try:
            users_res = supabase.table("usuarios").select("*").execute()
            users_list = users_res.data
            if users_list:
                for user in users_list:
                    c1, c2, c3 = st.columns([2,1,1])
                    status_icon = "🟢" if user['status'] == 'ativo' else "🟡"
                    c1.write(f"{status_icon} **{user['email']}**")
                    if user['status'] == 'pendente' and c2.button("Aprovar", key=f"ap_{user['email']}"):
                        supabase.table("usuarios").update({
                            "status": "ativo", 
                            "data_aprovacao": datetime.now(timezone.utc).isoformat()
                        }).eq("email", user['email']).execute()
                        st.rerun()
                    if c3.button("Excluir", key=f"del_{user['email']}"):
                        supabase.table("usuarios").delete().eq("email", user['email']).execute()
                        st.rerun()
            else:
                st.info("Nenhum usuário no banco de dados.")
        except Exception as e:
            st.error(f"Erro ao carregar usuários: {e}")

# --- 6. CONTEÚDO TÉCNICO (CÁLCULOS) ---
# (As abas Equipamento, Cálculos e Relatório continuam aqui conforme as versões anteriores)
st.info("Sistema pronto para cálculos.")
