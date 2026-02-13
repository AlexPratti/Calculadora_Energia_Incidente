import streamlit as st
import math
from fpdf import FPDF
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E CONEXÃO SUPABASE
# ==============================================================================
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

# 👇 CREDENCIAIS DO SUPABASE (JÁ PREENCHIDAS) 👇
SUPABASE_URL = "https://lfgqxphittdatzknwkqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxmZ3F4cGhpdHRkYXR6a253a3F3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4NzYyNzUsImV4cCI6MjA4NjQ1MjI3NX0.fZSfStTC5GdnP0Md1O0ptq8dD84zV-8cgirqIQTNO4Y"

@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Erro de conexão com Supabase: {e}")
    st.stop()

# ==============================================================================
# 2. FUNÇÕES AUXILIARES (PDF, WORD, TEXTO)
# ==============================================================================

def ft(texto):
    """Trata caracteres especiais para o PDF (latin-1)"""
    try:
        if texto is None: return ""
        return str(texto).encode('latin-1', 'replace').decode('latin-1')
    except:
        return str(texto)

def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, ft('Memorial de Cálculo - Arc Flash'), 0, 1, 'C') 
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(0, 6, 'Conforme NBR 17227 / IEEE 1584', 0, 1, 'C')
    pdf.ln(4)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, ft(f"Local: {dados['local']}"), 0, 1, 'C')
    eq_texto = dados['eq1']
    if dados['eq2']: eq_texto += f" [{dados['eq2']}]"
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 6, ft(eq_texto), 0, 1, 'C')
    pdf.ln(8)
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, ft("1. PARÂMETROS DE ENTRADA"), 1, 1, 'L', 1)
    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    pdf.cell(95, 6, ft(f"Tensão Nominal: {dados['v']:.3f} kV"), 0, 0)
    pdf.cell(95, 6, ft(f"Corrente de Curto (Ibf): {dados['i']:.3f} kA"), 0, 1)
    pdf.cell(95, 6, ft(f"Tempo de Arco: {dados['t']:.4f} s"), 0, 0)
    pdf.cell(95, 6, ft("Configuração: VCB"), 0, 1)
    gap_txt = "(Padrao)" if dados['is_gap_std'] else "(Manual)"
    dist_txt = "(Padrao)" if dados['is_dist_std'] else "(Manual)"
    pdf.cell(95, 6, ft(f"Gap: {dados['g']:.1f} mm {gap_txt}"), 0, 0)
    pdf.cell(95, 6, ft(f"Distância: {dados['d']:.1f} mm {dist_txt}"), 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, ft("2. ROTEIRO DE CÁLCULO"), 1, 1, 'L', 1)
    pdf.set_font("Courier", size=9)
    pdf.ln(2)
    pdf.cell(0, 5, f"A) Logaritmos:", 0, 1)
    pdf.cell(0, 5, f"   Log(Ibf)={math.log10(dados['i']):.4f} | Log(Gap)={math.log10(dados['g']):.4f}", 0, 1)
    pdf.ln(2)
    pdf.cell(0, 5, ft(f"B) Energia Base (En):"), 0, 1)
    pdf.cell(0, 5, f"   Log(En) = {dados['lg_en']:.4f} -> En = {dados['en_base']:.4f} cal/cm2", 0, 1)
    pdf.ln(2)
    pdf.cell(0, 5, ft(f"C) Fatores:"), 0, 1)
    pdf.cell(0, 5, f"   Tempo ({dados['t']}s/0.2s): {dados['fator_t']:.2f}", 0, 1)
    pdf.cell(0, 5, f"   Distancia (610/{dados['d']})^2: {dados['fator_d']:.3f}", 0, 1)
    pdf.cell(0, 5, f"   Fator Tensao: {dados['fator_v']}", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, ft("3. RESULTADO E CLASSIFICAÇÃO"), 1, 1, 'L', 1)
    pdf.ln(3)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, ft(f"Energia Incidente: {dados['e']:.2f} cal/cm²"), 0, 1)
    pdf.set_font("Arial", size=11)
    pdf.set_text_color(0, 0, 0)
    if dados['e'] > 40: pdf.set_text_color(200, 0, 0)
    elif dados['e'] >= 8: pdf.set_text_color(200, 100, 0)
    pdf.cell(0, 8, ft(f"Classificação: {dados['cat']}"), 0, 1)
    pdf.set_text_color(0, 0, 0) 
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, ft("Nota: A vestimenta deve possuir ATPV superior à energia calculada."), 0, 1)
    return pdf.output(dest='S').encode('latin-1')

def gerar_word(dados):
    doc = Document()
    head = doc.add_heading('Memorial - Arc Flash', 0) 
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_local = doc.add_paragraph()
    p_local.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_l = p_local.add_run(f"Local: {dados['local']}")
    run_l.bold = True
    run_l.font.size = Pt(12)
    eq_texto = dados['eq1']
    if dados['eq2']: eq_texto += f" [{dados['eq2']}]"
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_eq = p_eq.add_run(eq_texto)
    run_eq.bold = True
    run_eq.font.size = Pt(11)
    doc.add_paragraph("-" * 70).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_heading('1. Parâmetros', level=1)
    p = doc.add_paragraph()
    p.add_run(f"Tensão: {dados['v']:.3f} kV | Corrente: {dados['i']:.3f} kA | Tempo: {dados['t']:.4f} s\n")
    p.add_run(f"Gap: {dados['g']:.1f} mm | Distância: {dados['d']:.1f} mm\n")
    p.add_run("Configuração: VCB")
    doc.add_heading('2. Resultado', level=1)
    p_res = doc.add_paragraph()
    run_res = p_res.add_run(f"{dados['e']:.2f} cal/cm²")
    run_res.bold = True
    run_res.font.size = Pt(16)
    doc.add_paragraph(f"Classificação: {dados['cat']}")
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 3. LÓGICA DO APP PRINCIPAL
# ==============================================================================

def main_app_logic():
    st.markdown(f"### ⚡ Cálculo de Arc Flash")
    st.caption(f"Logado como: {st.session_state['user_name']}")
    
    if 'corrente_stored' not in st.session_state: st.session_state['corrente_stored'] = 17.0
    if 'resultado_icc_detalhe' not in st.session_state: st.session_state['resultado_icc_detalhe'] = None
    if 'ultimo_calculo' not in st.session_state: st.session_state['ultimo_calculo'] = None

    # --- LAYOUT DE DUAS COLUNAS: [ APP (70%) | HISTÓRICO (30%) ] ---
    col_app, col_hist = st.columns([7, 3])

    # --------------------------------------------------------
    # COLUNA DA ESQUERDA: CALCULADORA (Abas originais)
    # --------------------------------------------------------
    with col_app:
        tab1, tab2 = st.tabs(["🔥 Energia Incidente", "🧮 Icc (Curto)"])

        # --- ABA 1: CÁLCULO ARC FLASH ---
        with tab1:
            st.subheader("Análise de Energia")
            with st.container(border=True):
                st.caption("Identificação")
                local_input = st.text_input("Local", placeholder="Ex: Sala Elétrica 01")
                c_eq1, c_eq2 = st.columns(2)
                with c_eq1: eq1_input = st.text_input("Equipamento", placeholder="Ex: QGBT Geral")
                with c_eq2: eq2_input = st.text_input("Detalhe", placeholder="Ex: Disjuntor Entrada")

            st.write("")
            st.info("Parâmetros do Arco:")
            c1, c2, c3 = st.columns(3)
            with c1: tensao = st.number_input("1. Tensão (kV)", value=13.80, format="%.3f")
            with c2: corrente = st.number_input("2. Corrente (kA)", key="corrente_stored", format="%.3f")
            with c3: tempo = st.number_input("3. Tempo (s)", value=0.500, format="%.4f")

            c4, c5 = st.columns(2)
            with c4: gap = st.number_input("Gap (mm)", value=0.0, step=1.0, help="0 = Padrão Automático")
            with c5: distancia = st.number_input("Distância (mm)", value=0.0, step=10.0, help="0 = Padrão Automático")

            # Função de Cálculo (Lógica Original)
            def calcular_completo():
                g_c = gap if gap > 0 else (152.0 if tensao >= 1.0 else 25.0)
                d_c = distancia if distancia > 0 else (914.0 if tensao >= 1.0 else 457.2)
                is_gap_std = (gap <= 0)
                is_dist_std = (distancia <= 0)
                lg_i = math.log10(corrente) if corrente > 0 else 0
                
                if tensao < 1.0:
                    k_base, k_i, k_g = -0.555, 1.081, 0.0011
                    x_dist = 2.0
                    fator_v = 0.85 if tensao < 0.6 else 1.0
                else:
                    k_base, k_i, k_g = -0.555, 1.081, 0.0011
                    x_dist = 2.0
                    fator_v = 1.15

                lg_en = k_base + (k_i * lg_i) + (k_g * g_c)
                en_base = 10 ** lg_en
                fator_t = tempo / 0.2
                fator_d = (610 / d_c) ** x_dist
                e_final = 1.0 * en_base * fator_t * fator_d * fator_v
                
                if e_final < 1.2: cat, cor = "Risco Mínimo", "green"
                elif e_final < 4.0: cat, cor = "Cat 1 / 2", "orange"
                elif e_final < 8.0: cat, cor = "Cat 2", "darkorange"
                elif e_final < 40.0: cat, cor = "Cat 3 / 4", "red"
                else: cat, cor = "PERIGO", "black"

                return {
                    'local': local_input, 'eq1': eq1_input, 'eq2': eq2_input,
                    'v': tensao, 'i': corrente, 't': tempo, 'g': g_c, 'd': d_c,
                    'is_gap_std': is_gap_std, 'is_dist_std': is_dist_std,
                    'k_base': k_base, 'k_i': k_i, 'k_g': k_g,
                    'lg_en': lg_en, 'en_base': en_base,
                    'fator_t': fator_t, 'fator_d': fator_d, 'fator_v': fator_v, 'x_dist': x_dist,
                    'e': e_final, 'cat': cat, 'cor': cor
                }

            # Botão Calcular
            if st.button("CALCULAR", type="primary", use_container_width=True):
                if tensao > 0 and corrente > 0 and tempo > 0:
                    resultado = calcular_completo()
                    st.session_state['ultimo_calculo'] = resultado
                else:
                    st.warning("Preencha dados obrigatórios.")

            # Resultados
            if st.session_state['ultimo_calculo']:
                res = st.session_state['ultimo_calculo']
                st.divider()
                st.markdown(f"**Resultado:** {res['local']} - {res['eq1']}")
                
                c_res1, c_res2 = st.columns([1, 2])
                c_res1.metric("Energia Incidente", f"{res['e']:.2f} cal/cm²")
                c_res2.markdown(f"<div style='background-color:{res['cor']};color:white;padding:15px;text-align:center;border-radius:10px;'><h3>{res['cat']}</h3></div>", unsafe_allow_html=True)
                
                st.divider()
                st.caption("Ações:")
                
                # --- BOTÃO DE SALVAR NO SUPABASE (INTEGRAÇÃO NOVA) ---
                if st.button("💾 Salvar no Histórico"):
                    try:
                        payload = {
                            "username": st.session_state['user_login'],
                            "tag_equipamento": res['eq1'] if res['eq1'] else "Sem Tag",
                            "tensao_kv": res['v'],
                            "corrente_ka": res['i'],
                            "tempo_s": res['t'],
                            "distancia_mm": res['d'],
                            "energia_cal": float(f"{res['e']:.2f}")
                        }
                        supabase.table("arc_flash_history").insert(payload).execute()
                        st.toast("✅ Salvo no banco de dados!", icon="💾")
                        st.rerun() # Recarrega para atualizar a tabela lateral
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

                # Botões de Download
                dl1, dl2 = st.columns(2)
                with dl1:
                    pdf_data = gerar_pdf(res)
                    st.download_button("📥 Baixar PDF", data=pdf_data, file_name="memorial.pdf", mime="application/pdf", use_container_width=True)
                with dl2:
                    docx_data = gerar_word(res)
                    st.download_button("📝 Baixar Word", data=docx_data, file_name="memorial.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

        # --- ABA 2: CÁLCULO ICC (CURTO CIRCUITO) ---
        with tab2:
            st.subheader("Estimativa Curto-Circuito")
            
            def atualizar_icc():
                try:
                    t_kva = st.session_state['k_kva']
                    t_v = st.session_state['k_v']
                    t_z = st.session_state['k_z']
                    usar_motor = st.session_state['k_motor']
                    if t_v > 0 and t_z > 0:
                        i_nom = (t_kva * 1000) / (math.sqrt(3) * t_v)
                        i_cc_trafo = i_nom / (t_z / 100)
                        i_motor = 4 * i_nom if usar_motor else 0
                        i_total_ka = (i_cc_trafo + i_motor) / 1000
                        st.session_state['corrente_stored'] = i_total_ka
                        st.session_state['resultado_icc_detalhe'] = {'total': i_total_ka, 'nom': i_nom, 'trafo_ka': i_cc_trafo/1000, 'motor_ka': i_motor/1000}
                        st.toast(f"Calculado: {i_total_ka:.3f} kA", icon="✅")
                except: pass

            c1, c2 = st.columns(2)
            with c1:
                st.number_input("Potência Trafo (kVA)", value=1000.0, step=100.0, key="k_kva")
                st.number_input("Tensão Sec. (V)", value=380.0, step=10.0, key="k_v")
            with c2:
                st.number_input("Impedância Z (%)", value=5.0, step=0.1, key="k_z")
                st.checkbox("Considerar Motores?", value=True, key="k_motor")
            
            st.write("")
            st.button("Calcular Icc", on_click=atualizar_icc, type="primary", use_container_width=True)
            
            dados = st.session_state['resultado_icc_detalhe']
            if dados:
                st.divider()
                st.metric("Icc Estimada", f"{dados['total']:.3f} kA")
                st.success("Valor copiado automaticamente para a Aba 1.")

    # --------------------------------------------------------
    # COLUNA DA DIREITA: HISTÓRICO (SUPABASE)
    # --------------------------------------------------------
    with col_hist:
        st.markdown("### 📂 Histórico")
        if st.button("🔄 Atualizar"):
            st.rerun()
            
        try:
            # Busca histórico no Supabase
            res_hist = supabase.table("arc_flash_history").select("*").order("created_at", desc=True).limit(20).execute()
            
            if res_hist.data:
                # Exibe como cards ou dataframe simplificado
                for item in res_hist.data:
                    # Definição de cor baseada na energia (simplificada para visualização rápida)
                    cor_barra = "green"
                    if item['energia_cal'] > 8: cor_barra = "red"
                    elif item['energia_cal'] > 1.2: cor_barra = "orange"
                    
                    with st.container(border=True):
                        st.markdown(f"**{item['tag_equipamento']}**")
                        st.caption(f"{pd.to_datetime(item['created_at']).strftime('%d/%m %H:%M')}")
                        st.markdown(f"<span style='color:{cor_barra}; font-weight:bold; font-size:18px'>{item['energia_cal']} cal/cm²</span>", unsafe_allow_html=True)
                        st.text(f"{item['tensao_kv']}kV | {item['corrente_ka']}kA")
            else:
                st.info("Nenhum histórico recente.")
        except Exception as e:
            st.error("Erro ao carregar histórico.")


# ==============================================================================
# 4. SISTEMA DE LOGIN (AGORA VIA SUPABASE)
# ==============================================================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_role'] = None
    st.session_state['user_name'] = None
    st.session_state['user_login'] = None

# Sidebar Admin (Mantido lógica, mas adaptado para Supabase se necessário futuramente)
def admin_panel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ Admin")
    # Para simplificar este código, removi a gestão completa de admin aqui para focar no cálculo
    # Mas o usuário Admin continua existindo no banco.
    st.sidebar.info("Painel de gestão disponível via Supabase Dashboard.")

# Tela de Login
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.title("🔒 Login")
        with st.form("login_form"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", type="primary")
            
            if submitted:
                try:
                    res = supabase.table('users').select("*").eq('username', user).eq('password', pwd).execute()
                    if res.data:
                        data = res.data[0]
                        if data.get('approved'):
                            st.session_state['logged_in'] = True
                            st.session_state['user_role'] = 'admin' if user == 'admin' else 'user'
                            st.session_state['user_name'] = data.get('name', user)
                            st.session_state['user_login'] = user
                            st.rerun()
                        else:
                            st.warning("Usuário pendente de aprovação.")
                    else:
                        st.error("Dados incorretos.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

else:
    # Sidebar
    st.sidebar.success(f"Olá, {st.session_state['user_name']}")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.rerun()

    if st.session_state['user_role'] == 'admin':
        admin_panel()

    # Executa o App Principal
    main_app_logic()
