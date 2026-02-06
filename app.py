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

# --- INICIALIZAÇÃO DE ESTADO ---
if 'corrente_stored' not in st.session_state:
    st.session_state['corrente_stored'] = 17.0
if 'resultado_icc_detalhe' not in st.session_state:
    st.session_state['resultado_icc_detalhe'] = None
if 'ultimo_calculo' not in st.session_state:
    st.session_state['ultimo_calculo'] = None

# --- FUNÇÃO AUXILIAR PARA CORRIGIR ACENTOS (PDF) ---
def ft(texto):
    """
    Converte string UTF-8 (Python) para Latin-1 (PDF padrão).
    Resolve problemas de cedilha (ç) e acentos (ã, é, í).
    """
    try:
        return str(texto).encode('latin-1', 'replace').decode('latin-1')
    except Exception:
        return str(texto)

# --- FUNÇÕES DE GERAÇÃO DE RELATÓRIOS ---

def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Arial", 'B', 14)
    # Note o uso de ft() em todos os textos com acento
    pdf.cell(0, 10, ft('Memorial de Cálculo Detalhado - Energia Incidente'), 0, 1, 'C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, 'Conforme NBR 17227 / IEEE 1584', 0, 1, 'C')
    pdf.ln(5)
    
    # 1. Dados de Entrada
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, ft("1. Parâmetros de Entrada"), 1, 1, 'L', 1)
    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    
    pdf.cell(95, 7, ft(f"Tensão Nominal (Voc): {dados['v']:.3f} kV"), 0, 0)
    pdf.cell(95, 7, ft(f"Corrente de Curto (Ibf): {dados['i']:.3f} kA"), 0, 1)
    pdf.cell(95, 7, ft(f"Tempo de Eliminação (t): {dados['t']:.4f} s"), 0, 0)
    pdf.cell(95, 7, ft(f"Configuração: VCB (Vertical Box)"), 0, 1)
    
    # Geometria
    gap_tipo = "(Padrao)" if dados['is_gap_std'] else "(Inserido)"
    dist_tipo = "(Padrao)" if dados['is_dist_std'] else "(Inserido)"
    
    pdf.cell(95, 7, ft(f"Gap dos Eletrodos (G): {dados['g']:.1f} mm {gap_tipo}"), 0, 0)
    pdf.cell(95, 7, ft(f"Distância de Trabalho (D): {dados['d']:.1f} mm {dist_tipo}"), 0, 1)
    pdf.ln(5)

    # 2. Roteiro de Cálculo
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, ft("2. Roteiro de Cálculo (Passo a Passo)"), 1, 1, 'L', 1)
    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    
    pdf.multi_cell(0, 6, ft("O cálculo baseia-se no modelo empírico da IEEE 1584, determinando primeiro a energia normalizada e aplicando os fatores de correção."))
    pdf.ln(2)
    
    pdf.set_font("Courier", size=10)
    # Passo 2.1
    pdf.cell(0, 6, f"A) Variáveis Logarítmicas:", 0, 1)
    pdf.cell(0, 6, f"   Log(Ibf) = {math.log10(dados['i']):.4f}", 0, 1)
    pdf.cell(0, 6, f"   Log(G)   = {math.log10(dados['g']):.4f}", 0, 1)
    pdf.ln(2)
    
    # Passo 2.2
    modelo_txt = "Média Tensão (>1kV)" if dados['v']>=1 else "Baixa Tensão (<1kV)"
    pdf.cell(0, 6, ft(f"B) Cálculo da Energia Base (Log En):"), 0, 1)
    pdf.cell(0, 6, ft(f"   Modelo Utilizado: {modelo_txt}"), 0, 1)
    pdf.cell(0, 6, f"   Constantes: k1={dados['k_base']}, k2={dados['k_i']}, k3={dados['k_g']}", 0, 1)
    pdf.cell(0, 6, f"   Eq: Log(En) = k1 + k2*Log(Ibf) + k3*Gap", 0, 1)
    pdf.cell(0, 6, f"   Log(En) = {dados['lg_en']:.4f}", 0, 1)
    pdf.cell(0, 6, f"   En (Normalizada) = 10^{dados['lg_en']:.4f} = {dados['en_base']:.4f} cal/cm2", 0, 1)
    pdf.ln(2)
    
    # Passo 2.3
    pdf.cell(0, 6, ft(f"C) Fatores de Correção:"), 0, 1)
    pdf.cell(0, 6, ft(f"   Fator Tempo (t / 0.2s): {dados['t']}/0.2 = {dados['fator_t']:.2f}"), 0, 1)
    pdf.cell(0, 6, ft(f"   Fator Distância (610 / D)^x: (610/{dados['d']:.1f})^{dados['x_dist']} = {dados['fator_d']:.3f}"), 0, 1)
    pdf.cell(0, 6, ft(f"   Fator de Calibração (V): {dados['fator_v']}"), 0, 1)
    pdf.ln(2)
    
    # Passo 2.4
    pdf.cell(0, 6, f"D) Energia Final (E):", 0, 1)
    pdf.cell(0, 6, f"   E = En * Fator_Tempo * Fator_Distancia * Fator_V", 0, 1)
    pdf.cell(0, 6, f"   E = {dados['en_base']:.3f} * {dados['fator_t']:.2f} * {dados['fator_d']:.3f} * {dados['fator_v']}", 0, 1)
    pdf.ln(5)

    # 3. Resultado Final
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, ft("3. Resultado e Classificação"), 1, 1, 'L', 1)
    pdf.ln(4)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, ft(f"Energia Incidente: {dados['e']:.2f} cal/cm²"), 0, 1)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, ft(f"Classificação de Risco: {dados['cat']}"), 0, 1)
    
    if dados['e'] > 40:
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 8, ft("ATENÇÃO: Valor excede limite seguro para EPI comum."), 0, 1)
        pdf.set_text_color(0, 0, 0)
    
    # Rodapé do documento
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, ft("Documento gerado automaticamente pela plataforma WEG GenAI - Módulo Arc Flash."), 0, 1, 'C')
        
    return pdf.output(dest='S').encode('latin-1')

def gerar_word(dados):
    doc = Document()
    doc.add_heading('Memorial de Cálculo - Energia Incidente', 0)
    
    # 1. Parâmetros
    doc.add_heading('1. Parâmetros de Entrada', level=1)
    p = doc.add_paragraph()
    p.add_run(f"Tensão Nominal: {dados['v']:.3f} kV\n").bold = True
    p.add_run(f"Corrente de Curto (Ibf): {dados['i']:.3f} kA\n")
    p.add_run(f"Tempo de Arco: {dados['t']:.4f} s\n")
    
    gap_txt = " (Padrão)" if dados['is_gap_std'] else " (Manual)"
    dist_txt = " (Padrão)" if dados['is_dist_std'] else " (Manual)"
    
    p.add_run(f"Gap dos Eletrodos: {dados['g']:.1f} mm{gap_txt}\n")
    p.add_run(f"Distância de Trabalho: {dados['d']:.1f} mm{dist_txt}\n")
    p.add_run("Configuração: VCB (Vertical Conductors in Metal Box)")

    # 2. Roteiro
    doc.add_heading('2. Roteiro de Cálculo Detalhado', level=1)
    doc.add_paragraph("Metodologia baseada na norma IEEE 1584 / NBR 17227.")
    
    p2 = doc.add_paragraph()
    p2.add_run("A) Variáveis Logarítmicas:\n").bold = True
    p2.add_run(f"Log10(Ibf) = {math.log10(dados['i']):.4f}\n")
    p2.add_run(f"Log10(Gap) = {math.log10(dados['g']):.4f}\n")
    
    p2.add_run("\nB) Energia Base Normalizada (En):\n").bold = True
    p2.add_run(f"Constantes utilizadas: k1={dados['k_base']}, k2={dados['k_i']}\n")
    p2.add_run(f"Log(En) calculado = {dados['lg_en']:.4f}\n")
    p2.add_run(f"En (Energia Base) = {dados['en_base']:.4f} cal/cm²\n")
    
    p2.add_run("\nC) Fatores de Correção:\n").bold = True
    p2.add_run(f"Fator de Tempo (t/0.2): {dados['fator_t']:.3f}\n")
    p2.add_run(f"Fator de Distância (610/D)^{dados['x_dist']}: {dados['fator_d']:.3f}\n")
    p2.add_run(f"Fator de Tensão/Calibração: {dados['fator_v']}\n")

    # 3. Resultado
    doc.add_heading('3. Resultado Final', level=1)
    pres = doc.add_paragraph()
    run = pres.add_run(f"{dados['e']:.2f} cal/cm²")
    run.bold = True
    run.font.size = Pt(16)
    
    doc.add_paragraph(f"Classificação: {dados['cat']}")
    doc.add_paragraph("Nota: A vestimenta deve possuir ATPV superior à energia calculada.")

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- CALLBACK DE ATUALIZAÇÃO ---
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

# --- INTERFACE PRINCIPAL ---
tab1, tab2 = st.tabs(["🔥 Cálculo de Energia Incidente", "🧮 Estimativa de Icc (Curto-Circuito)"])

# ABA 1
with tab1:
    st.header("Cálculo da Energia Incidente")
    
    c1, c2, c3 = st.columns(3)
    with c1: tensao = st.number_input("1. Tensão (kV)", value=13.80, format="%.3f")
    with c2: corrente = st.number_input("2. Corrente (kA)", key="corrente_stored", format="%.3f")
    with c3: tempo = st.number_input("3. Tempo (s)", value=0.500, format="%.4f")

    st.subheader("Geometria (Opcional)")
    st.caption("Deixe 0 para usar os padrões normativos.")
    c4, c5 = st.columns(2)
    with c4: gap = st.number_input("4. Gap (mm)", value=0.0, step=1.0)
    with c5: distancia = st.number_input("5. Distância (mm)", value=0.0, step=10.0)

    # LÓGICA DO CÁLCULO
    def calcular_completo():
        # Lógica de Padrões
        is_gap_std = False
        if gap <= 0:
            g_c = 152.0 if tensao >= 1.0 else 25.0
            is_gap_std = True
        else:
            g_c = gap
            
        is_dist_std = False
        if distancia <= 0:
            d_c = 914.0 if tensao >= 1.0 else 457.2
            is_dist_std = True
        else:
            d_c = distancia

        lg_i = math.log10(corrente) if corrente > 0 else 0
        
        # Coeficientes
        if tensao < 1.0: # BT
            k_base, k_i, k_g = -0.555, 1.081, 0.0011
            x_dist = 2.0
            fator_v = 0.85 if tensao < 0.6 else 1.0
        else: # MT
            k_base, k_i, k_g = -0.555, 1.081, 0.0011
            x_dist = 2.0
            fator_v = 1.15

        # Passo a Passo
        lg_en = k_base + (k_i * lg_i) + (k_g * g_c)
        en_base = 10 ** lg_en
        
        fator_t = tempo / 0.2
        fator_d = (610 / d_c) ** x_dist
        
        e_final = 1.0 * en_base * fator_t * fator_d * fator_v
        
        # Classificação
        if e_final < 1.2: cat, cor = "Risco Mínimo (Isento)", "green"
        elif e_final < 4.0: cat, cor = "Categoria 1 ou 2 (Até 4 cal)", "orange"
        elif e_final < 8.0: cat, cor = "Categoria 2 (Até 8 cal)", "darkorange"
        elif e_final < 40.0: cat, cor = "Categoria 3 ou 4 (Até 40 cal)", "red"
        else: cat, cor = "PERIGO EXTREMO (>40 cal)", "black"

        return {
            'v': tensao, 'i': corrente, 't': tempo, 'g': g_c, 'd': d_c,
            'is_gap_std': is_gap_std, 'is_dist_std': is_dist_std,
            'k_base': k_base, 'k_i': k_i, 'k_g': k_g,
            'lg_en': lg_en, 'en_base': en_base,
            'fator_t': fator_t, 'fator_d': fator_d, 'fator_v': fator_v, 'x_dist': x_dist,
            'e': e_final, 'cat': cat, 'cor': cor
        }

    # BOTÃO CALCULAR
    if st.button("Calcular Energia", type="primary", use_container_width=True):
        if tensao > 0 and corrente > 0 and tempo > 0:
            resultado = calcular_completo()
            st.session_state['ultimo_calculo'] = resultado
        else:
            st.warning("Preencha os campos obrigatórios.")

    # EXIBIÇÃO RESULTADOS
    if st.session_state['ultimo_calculo']:
        res = st.session_state['ultimo_calculo']
        
        st.divider()
        col_res1, col_res2 = st.columns([1, 2])
        col_res1.metric("Energia Incidente", f"{res['e']:.2f} cal/cm²")
        col_res2.markdown(f"<div style='background-color:{res['cor']};color:white;padding:15px;text-align:center;border-radius:10px;'><h3>{res['cat']}</h3></div>", unsafe_allow_html=True)
        
        st.caption(f"Parâmetros: Gap {res['g']}mm | Distância {res['d']}mm")
        
        st.subheader("📄 Documentação Técnica")
        st.info("Baixe o memorial detalhado para comprovação dos cálculos.")
        
        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            pdf_data = gerar_pdf(res)
            st.download_button("📥 Baixar Memorial em PDF", data=pdf_data, file_name="memorial_arc_flash.pdf", mime="application/pdf", use_container_width=True)
        
        with c_dl2:
            docx_data = gerar_word(res)
            st.download_button("📝 Baixar Memorial em Word", data=docx_data, file_name="memorial_arc_flash.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

# ABA 2
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
