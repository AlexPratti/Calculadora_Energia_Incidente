import streamlit as st
import math
from fpdf import FPDF
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

st.title("⚡ Sistema de Análise de Arc Flash (NBR 17227)")
st.markdown("---")

# --- INICIALIZAÇÃO DE ESTADO ---
if 'corrente_stored' not in st.session_state:
    st.session_state['corrente_stored'] = 17.0
if 'resultado_icc_detalhe' not in st.session_state:
    st.session_state['resultado_icc_detalhe'] = None

# --- CLASSE PARA GERAR O PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Memorial de Calculo - Energia Incidente (Arc Flash)', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Baseado na norma NBR 17227 / IEEE 1584', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def gerar_pdf(v, i, t, g, d, e_final, cat_risco):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    # 1. Dados de Entrada
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Dados de Entrada:", 0, 1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"   - Tensao Nominal: {v:.3f} kV", 0, 1)
    pdf.cell(0, 7, f"   - Corrente de Curto (Ibf): {i:.3f} kA", 0, 1)
    pdf.cell(0, 7, f"   - Tempo de Arco: {t:.4f} s", 0, 1)
    pdf.cell(0, 7, f"   - Gap (Espacamento): {g:.1f} mm", 0, 1)
    pdf.cell(0, 7, f"   - Distancia de Trabalho: {d:.1f} mm", 0, 1)
    pdf.ln(5)

    # 2. Parametros Calculados (Detalhando a matemática)
    # Recalculando logs para mostrar no relatório
    log_i = math.log10(i) if i > 0 else 0
    
    # Lógica simplificada para exibição
    tipo_tensao = "Media Tensao (> 1kV)" if v >= 1.0 else "Baixa Tensao (< 1kV)"
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Detalhes do Calculo:", 0, 1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"   - Modelo Utilizado: {tipo_tensao}", 0, 1)
    pdf.cell(0, 7, f"   - Log10(Ibf): {log_i:.4f}", 0, 1)
    
    # Fatores principais
    if v < 1.0:
        fator_v = "0.85 (Redutor para 380V/480V)" if v < 0.6 else "1.0"
    else:
        fator_v = "1.15 (Calibracao MT)"
    
    pdf.cell(0, 7, f"   - Fator de Tensao/Calibracao: {fator_v}", 0, 1)
    
    dist_fator = (610 / d) ** 2
    pdf.cell(0, 7, f"   - Fator de Distancia (610/D)^2: {dist_fator:.3f}", 0, 1)
    pdf.ln(5)

    # 3. Resultado Final
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "3. Resultado Final:", 0, 1)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"   Energia Incidente: {e_final:.2f} cal/cm2", 0, 1)
    pdf.ln(5)

    # 4. Conclusão e EPI
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "4. Classificacao e EPI (NBR 17227):", 0, 1)
    pdf.set_font("Arial", size=11)
    
    pdf.cell(0, 7, f"   Categoria Estimada: {cat_risco}", 0, 1)
    pdf.ln(2)
    pdf.multi_cell(0, 7, "Recomendacao: A vestimenta deve possuir ATPV (Arc Thermal Performance Value) superior a energia calculada acima.")
    
    if e_final > 40:
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, "ALERTA: TRABALHO PROIBIDO (Energia > 40 cal/cm2)", 0, 1)
        pdf.set_text_color(0, 0, 0)

    return pdf.output(dest='S').encode('latin-1')

# --- FUNÇÃO CALLBACK (ATUALIZAR ICC) ---
def atualizar_icc():
    try:
        t_kva = st.session_state['k_kva']
        t_v = st.session_state['k_v']
        t_z = st.session_state['k_z']
        usar_motor = st.session_state['k_motor']
        
        if t_v > 0 and t_z > 0:
            i_nom = (t_kva * 1000) / (math.sqrt(3) * t_v)
            i_cc_trafo = i_nom / (t_z / 100)
            
            i_motor = 0
            if usar_motor:
                i_motor = 4 * i_nom 
            
            i_total_ka = (i_cc_trafo + i_motor) / 1000
            
            st.session_state['corrente_stored'] = i_total_ka
            st.session_state['resultado_icc_detalhe'] = {
                'total': i_total_ka,
                'nom': i_nom,
                'trafo_ka': i_cc_trafo/1000,
                'motor_ka': i_motor/1000
            }
            st.toast(f"✅ Calculado: {i_total_ka:.3f} kA", icon="⚡")
    except Exception as e:
        st.error(f"Erro: {e}")

# Criando abas
tab1, tab2 = st.tabs(["🔥 Cálculo de Energia Incidente", "🧮 Estimativa de Icc (Curto-Circuito)"])

# =======================================================
# ABA 1: CÁLCULO DE ENERGIA (ARC FLASH)
# =======================================================
with tab1:
    st.header("Cálculo da Energia Incidente")
    st.info("Preencha os dados elétricos e geométricos abaixo.")

    col_in1, col_in2, col_in3 = st.columns(3)
    with col_in1:
        tensao = st.number_input("1. Tensão Nominal (kV)", value=13.80, format="%.3f")
    with col_in2:
        corrente = st.number_input("2. Corrente de Curto (kA)", key="corrente_stored", format="%.3f")
    with col_in3:
        tempo = st.number_input("3. Tempo de Arco (s)", value=0.500, format="%.4f")

    st.markdown("---")
    st.subheader("Geometria e Distâncias (Opcional)")
    
    col_geo1, col_geo2 = st.columns(2)
    with col_geo1:
        gap = st.number_input("4. Gap dos Eletrodos (mm)", value=152.0, step=1.0)
    with col_geo2:
        distancia = st.number_input("5. Distância de Trabalho (mm)", value=914.0, step=10.0)

    # --- LÓGICA DE CÁLCULO ---
    def calcular_energia_final():
        g_calc = gap
        d_calc = distancia
        
        if g_calc <= 0:
            g_calc = 152.0 if tensao >= 1.0 else 25.0
        if d_calc <= 0:
            d_calc = 914.0 if tensao >= 1.0 else 457.2

        lg_i = math.log10(corrente) if corrente > 0 else 0
        
        if tensao < 1.0: # BT
            k_base = -0.555
            k_i = 1.081
            k_g = 0.0011
            lg_en = k_base + (k_i * lg_i) + (k_g * g_calc)
            en = 10 ** lg_en
            x_dist = 2.0
            fator_v = 0.85 if tensao < 0.6 else 1.0
        else: # MT
            k_base = -0.555
            k_i = 1.081
            k_g = 0.0011
            lg_en = k_base + (k_i * lg_i) + (k_g * g_calc)
            en = 10 ** lg_en
            x_dist = 2.0
            fator_v = 1.15 # Calibração IEEE 1584-2018 Conservadora

        cf = 1.0
        e_final = cf * en * (tempo / 0.2) * ((610 / d_calc) ** x_dist)
        e_final = e_final * fator_v

        return e_final, g_calc, d_calc

    st.write("")
    if st.button("Calcular Energia", type="primary", use_container_width=True):
        if tensao > 0 and corrente > 0 and tempo > 0:
            res, g_used, d_used = calcular_energia_final()
            
            # Categorias
            if res < 1.2: cat_txt, cor = "Risco Minimo", "green"
            elif res < 4.0: cat_txt, cor = "Categoria 1 ou 2 (Ate 4 cal)", "orange"
            elif res < 8.0: cat_txt, cor = "Categoria 2 (Ate 8 cal)", "darkorange"
            elif res < 40.0: cat_txt, cor = "Categoria 3 ou 4 (Ate 40 cal)", "red"
            else: cat_txt, cor = "PERIGO EXTREMO", "black"

            # Exibe Resultado na Tela
            st.success("Cálculo Realizado!")
            c1, c2 = st.columns([1, 2])
            c1.metric("Energia Incidente", f"{res:.2f} cal/cm²")
            c2.markdown(f"<div style='background-color:{cor};color:white;padding:15px;text-align:center;border-radius:10px;'><h3>{cat_txt}</h3></div>", unsafe_allow_html=True)
            
            # --- GERAR PDF ---
            st.markdown("---")
            st.subheader("📄 Documentação")
            
            # Gera o binário do PDF
            pdf_bytes = gerar_pdf(tensao, corrente, tempo, g_used, d_used, res, cat_txt)
            
            # Botão de Download
            st.download_button(
                label="📥 Baixar Memorial de Cálculo (PDF)",
                data=pdf_bytes,
                file_name="memorial_arc_flash.pdf",
                mime="application/pdf",
                type="secondary"
            )

# =======================================================
# ABA 2: CALCULADORA DE CURTO-CIRCUITO (AUXILIAR)
# =======================================================
with tab2:
    st.header("Estimativa de Icc pelo Transformador")
    st.markdown("Insira os dados do transformador para estimar a corrente de curto.")
    
    col_trafo1, col_trafo2 = st.columns(2)
    with col_trafo1:
        st.number_input("Potência do Transformador (kVA)", value=1000.0, step=100.0, key="k_kva")
        st.number_input("Tensão Secundária (Volts)", value=380.0, step=10.0, key="k_v")
    with col_trafo2:
        st.number_input("Impedância (Z%)", value=5.0, step=0.1, key="k_z")
        st.checkbox("Incluir contribuição de motores?", value=True, key="k_motor")

    st.write("")
    st.button("Calcular e Atualizar Icc (kA)", type="primary", on_click=atualizar_icc, use_container_width=True)

    dados = st.session_state['resultado_icc_detalhe']
    if dados is not None:
        st.divider()
        st.subheader("Resultados Calculados")
        st.metric(label="Corrente de Curto-Circuito (Ibf)", value=f"{dados['total']:.3f} kA")
        st.info(f"Trafo: {dados['trafo_ka']:.3f} kA | Motores: {dados['motor_ka']:.3f} kA | Valor enviado para Aba 1.")
