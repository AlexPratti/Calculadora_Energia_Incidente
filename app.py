import streamlit as st
import math
from fpdf import FPDF
from docx import Document
from docx.shared import Pt
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

st.title("⚡ Sistema de Análise de Arc Flash (NBR 17227)")
st.markdown("---")

# --- INICIALIZAÇÃO DE ESTADO (MEMÓRIA) ---
if 'corrente_stored' not in st.session_state:
    st.session_state['corrente_stored'] = 17.0
if 'resultado_icc_detalhe' not in st.session_state:
    st.session_state['resultado_icc_detalhe'] = None
# Variável para guardar o último cálculo realizado
if 'ultimo_calculo' not in st.session_state:
    st.session_state['ultimo_calculo'] = None

# --- FUNÇÕES DE GERAÇÃO DE ARQUIVOS ---

def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, 'Memorial de Calculo - Arc Flash', 0, 1, 'C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, 'Conforme NBR 17227 / IEEE 1584', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=11)
    # Dados
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Parametros de Entrada:", 0, 1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"   - Tensao: {dados['v']:.3f} kV", 0, 1)
    pdf.cell(0, 7, f"   - Corrente (Ibf): {dados['i']:.3f} kA", 0, 1)
    pdf.cell(0, 7, f"   - Tempo: {dados['t']:.4f} s", 0, 1)
    pdf.cell(0, 7, f"   - Gap: {dados['g']:.1f} mm", 0, 1)
    pdf.cell(0, 7, f"   - Distancia: {dados['d']:.1f} mm", 0, 1)
    pdf.ln(5)
    
    # Resultado
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Resultado Final:", 0, 1)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"   Energia: {dados['e']:.2f} cal/cm2", 0, 1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 10, f"   Classificacao: {dados['cat']}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

def gerar_word(dados):
    doc = Document()
    doc.add_heading('Memorial de Cálculo - Arc Flash', 0)
    doc.add_paragraph('Baseado na norma NBR 17227 / IEEE 1584')
    
    doc.add_heading('1. Parâmetros de Entrada', level=1)
    p = doc.add_paragraph()
    p.add_run(f"Tensão Nominal: ").bold = True
    p.add_run(f"{dados['v']:.3f} kV\n")
    p.add_run(f"Corrente de Curto (Ibf): ").bold = True
    p.add_run(f"{dados['i']:.3f} kA\n")
    p.add_run(f"Tempo de Arco: ").bold = True
    p.add_run(f"{dados['t']:.4f} s\n")
    p.add_run(f"Gap dos Eletrodos: ").bold = True
    p.add_run(f"{dados['g']:.1f} mm\n")
    p.add_run(f"Distância de Trabalho: ").bold = True
    p.add_run(f"{dados['d']:.1f} mm")

    doc.add_heading('2. Detalhes do Cálculo', level=1)
    p2 = doc.add_paragraph()
    p2.add_run(f"Log10(Corrente): {math.log10(dados['i']):.4f}\n")
    fator_dist = (610/dados['d'])**2
    p2.add_run(f"Fator de Distância (610/D)²: {fator_dist:.3f}")

    doc.add_heading('3. Resultado Final', level=1)
    res_par = doc.add_paragraph()
    run = res_par.add_run(f"Energia Incidente: {dados['e']:.2f} cal/cm²")
    run.bold = True
    run.font.size = Pt(14)
    
    doc.add_paragraph(f"Classificação de Risco: {dados['cat']}")
    
    # Salvar em memória
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- CALLBACK PARA ATUALIZAR ICC ---
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
            st.session_state['resultado_icc_detalhe'] = {
                'total': i_total_ka, 'nom': i_nom, 'trafo_ka': i_cc_trafo/1000, 'motor_ka': i_motor/1000
            }
            st.toast(f"Calculado: {i_total_ka:.3f} kA", icon="✅")
    except Exception:
        pass

# --- ABAS ---
tab1, tab2 = st.tabs(["🔥 Cálculo de Energia Incidente", "🧮 Estimativa de Icc (Curto-Circuito)"])

# ABA 1: ARC FLASH
with tab1:
    st.header("Cálculo da Energia Incidente")
    
    c1, c2, c3 = st.columns(3)
    with c1: tensao = st.number_input("1. Tensão (kV)", value=13.80, format="%.3f")
    with c2: corrente = st.number_input("2. Corrente (kA)", key="corrente_stored", format="%.3f")
    with c3: tempo = st.number_input("3. Tempo (s)", value=0.500, format="%.4f")

    st.subheader("Geometria (Opcional)")
    c4, c5 = st.columns(2)
    with c4: gap = st.number_input("4. Gap (mm)", value=152.0, step=1.0)
    with c5: distancia = st.number_input("5. Distância (mm)", value=914.0, step=10.0)

    # LÓGICA DE CÁLCULO
    def calcular_final():
        g_c = gap if gap > 0 else (152.0 if tensao >= 1.0 else 25.0)
        d_c = distancia if distancia > 0 else (914.0 if tensao >= 1.0 else 457.2)
        
        lg_i = math.log10(corrente) if corrente > 0 else 0
        
        # Modelo Simplificado IEEE 1584
        if tensao < 1.0: # BT
            k_base, k_i, k_g = -0.555, 1.081, 0.0011
            x_dist = 2.0
            fator_v = 0.85 if tensao < 0.6 else 1.0
        else: # MT
            k_base, k_i, k_g = -0.555, 1.081, 0.0011
            x_dist = 2.0
            fator_v = 1.15

        lg_en = k_base + (k_i * lg_i) + (k_g * g_c)
        en = 10 ** lg_en
        e_final = 1.0 * en * (tempo / 0.2) * ((610 / d_c) ** x_dist) * fator_v
        
        # Define Categoria
        if e_final < 1.2: cat, cor = "Risco Mínimo", "green"
        elif e_final < 4.0: cat, cor = "Categoria 1 ou 2", "orange"
        elif e_final < 8.0: cat, cor = "Categoria 2", "darkorange"
        elif e_final < 40.0: cat, cor = "Categoria 3 ou 4", "red"
        else: cat, cor = "PERIGO EXTREMO", "black"

        return {
            'v': tensao, 'i': corrente, 't': tempo, 'g': g_c, 'd': d_c,
            'e': e_final, 'cat': cat, 'cor': cor
        }

    # BOTÃO CALCULAR (Salva no Estado)
    if st.button("Calcular Energia", type="primary", use_container_width=True):
        if tensao > 0 and corrente > 0 and tempo > 0:
            resultado = calcular_final()
            st.session_state['ultimo_calculo'] = resultado # Salva na memória
        else:
            st.warning("Preencha todos os campos.")

    # EXIBIÇÃO PERSISTENTE DO RESULTADO
    if st.session_state['ultimo_calculo']:
        res = st.session_state['ultimo_calculo']
        
        st.divider()
        col_res1, col_res2 = st.columns([1, 2])
        col_res1.metric("Energia Incidente", f"{res['e']:.2f} cal/cm²")
        col_res2.markdown(f"<div style='background-color:{res['cor']};color:white;padding:15px;text-align:center;border-radius:10px;'><h3>{res['cat']}</h3></div>", unsafe_allow_html=True)
        
        st.caption(f"Parâmetros: Gap {res['g']}mm | Distância {res['d']}mm")
        
        # ÁREA DE DOWNLOAD (Agora não some!)
        st.subheader("📂 Exportar Relatório")
        col_dl1, col_dl2 = st.columns(2)
        
        # Botão PDF
        with col_dl1:
            pdf_data = gerar_pdf(res)
            st.download_button("📄 Baixar PDF", data=pdf_data, file_name="memorial.pdf", mime="application/pdf", use_container_width=True)
            
        # Botão Word
        with col_dl2:
            docx_data = gerar_word(res)
            st.download_button("📝 Baixar Word (.docx)", data=docx_data, file_name="memorial.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

# ABA 2: CALCULADORA ICC
with tab2:
    st.header("Estimativa de Icc")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("Potência (kVA)", value=1000.0, step=100.0, key="k_kva")
        st.number_input("Tensão (V)", value=380.0, step=10.0, key="k_v")
    with c2:
        st.number_input("Z (%)", value=5.0, step=0.1, key="k_z")
        st.checkbox("Contribuição Motores?", value=True, key="k_motor")
        
    st.write("")
    st.button("Calcular e Atualizar", on_click=atualizar_icc, type="primary", use_container_width=True)
    
    dados = st.session_state['resultado_icc_detalhe']
    if dados:
        st.metric("Icc Estimada", f"{dados['total']:.3f} kA")
        st.info("Valor enviado para a Aba 1.")
