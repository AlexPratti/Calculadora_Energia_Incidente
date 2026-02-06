import streamlit as st
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

st.title("⚡ Sistema de Análise de Arc Flash (NBR 17227)")
st.markdown("---")

# Criando abas para separar as ferramentas
tab1, tab2 = st.tabs(["🔥 Cálculo de Energia Incidente", "🧮 Estimativa de Icc (Curto-Circuito)"])

# =======================================================
# ABA 1: CÁLCULO DE ENERGIA (ARC FLASH)
# =======================================================
with tab1:
    st.header("Cálculo da Energia Incidente")
    st.info("Preencha os dados abaixo com base no estudo de proteção.")

    # --- BARRA LATERAL DENTRO DA ABA ---
    col_in1, col_in2 = st.columns(2)
    
    with col_in1:
        tensao = st.number_input("1. Tensão Nominal (kV)", value=0.38, format="%.3f", help="Ex: 0.38 para 380V")
        tempo = st.number_input("3. Tempo de Arco (s)", value=0.200, format="%.4f", help="Tempo de atuação da proteção.")
        
    with col_in2:
        corrente = st.number_input("2. Corrente de Curto (kA)", value=17.0, format="%.3f", help="Ibf: Corrente de curto trifásica franca.")
        
    with st.expander("Configurações Avançadas de Geometria (Opcional)"):
        st.write("Se deixar zerado, o sistema usa os padrões da norma.")
        gap = st.number_input("Gap dos Eletrodos (mm)", value=0.0, step=1.0)
        distancia = st.number_input("Distância de Trabalho (mm)", value=0.0, step=10.0)

    # Função de Cálculo (Mesma lógica validada anteriormente)
    def calcular_energia():
        # Padrões
        gap_local = gap
        dist_local = distancia
        if gap_local <= 0:
            gap_local = 152.0 if tensao >= 1.0 else 25.0
        if dist_local <= 0:
            dist_local = 914.0 if tensao >= 1.0 else 457.2

        # Coeficientes
        if tensao >= 1.0: # MT
            k1, k2, k3 = 3.82, 0.11, -1.0
            c_dist = -1.568
            fator_Iarc = 0.97
            fator_box = 1.15
        else: # BT
            k1, k2, k3 = 3.1, 0.15, -1.2
            c_dist = -1.60
            fator_Iarc = 0.85 
            fator_box = 1.25

        # Cálculo
        log_Ibf = math.log10(corrente) if corrente > 0 else 0
        log_G = math.log10(gap_local)
        log_D = math.log10(dist_local)

        I_arc = fator_Iarc * corrente
        log_Iarc = math.log10(I_arc) if I_arc > 0 else 0

        expoente = k1 + (k2 * log_Ibf) + (k3 * log_Gap) + (c_dist * log_D) + (0.99 * log_Iarc)
        
        E_joules = 0.25104 * (tempo * 1000) * (10 ** expoente)
        E_joules = E_joules * fator_box
        E_cal = E_joules / 4.184
        
        return E_cal, gap_local, dist_local

    if st.button("Calcular Energia", type="primary"):
        if tensao > 0 and corrente > 0 and tempo > 0:
            # Correção de variável para cálculo
            gap_calc = gap if gap > 0 else (152.0 if tensao >= 1.0 else 25.0)
            log_Gap = math.log10(gap_calc)
            
            res, g_used, d_used = calcular_energia()
            
            # Categorias
            if res < 1.2: cat, cor = "Risco Mínimo", "green"
            elif res < 4.0: cat, cor = "Categoria 1 ou 2", "orange"
            elif res < 8.0: cat, cor = "Categoria 2", "darkorange"
            elif res < 40.0: cat, cor = "Categoria 3 ou 4", "red"
            else: cat, cor = "PERIGO EXTREMO", "black"

            st.metric(label="Energia Incidente", value=f"{res:.2f} cal/cm²")
            st.markdown(f"<div style='background-color:{cor};color:white;padding:10px;text-align:center;border-radius:5px;'><b>{cat}</b></div>", unsafe_allow_html=True)
            st.caption(f"Gap: {g_used}mm | Dist: {d_used}mm")

# =======================================================
# ABA 2: CALCULADORA DE CURTO-CIRCUITO (AUXILIAR)
# =======================================================
with tab2:
    st.header("Estimativa de Icc pelo Transformador")
    st.markdown("""
    Esta ferramenta estima a corrente de curto-circuito **no secundário do transformador**, 
    considerando barramento infinito no primário (pior caso conservativo).
    """)
    
    col_trafo1, col_trafo2 = st.columns(2)
    
    with col_trafo1:
        trafo_kva = st.number_input("Potência do Transformador (kVA)", value=1000.0, step=100.0)
        trafo_v = st.number_input("Tensão Secundária (Volts)", value=380.0, step=10.0)
        
    with col_trafo2:
        trafo_z = st.number_input("Impedância (Z%)", value=5.0, step=0.1, help="Geralmente entre 4% e 6% na placa do trafo.")
        motor_contrib = st.checkbox("Incluir contribuição de motores?", value=True, help="Adiciona 4x a corrente nominal estimada.")

    if st.button("Calcular Ibf (kA)"):
        if trafo_v > 0 and trafo_z > 0:
            # 1. Corrente Nominal
            i_nom = (trafo_kva * 1000) / (math.sqrt(3) * trafo_v)
            
            # 2. Curto no Trafo
            i_cc_trafo = i_nom / (trafo_z / 100)
            
            # 3. Contribuição de Motores (Estimativa NBR/IEEE: 4x Inom ou 100% carga conectada)
            # Assumindo 100% de carga de motores para pior caso
            i_motor = 0
            if motor_contrib:
                i_motor = 4 * i_nom 
            
            i_total_ka = (i_cc_trafo + i_motor) / 1000
            
            st.success(f"Corrente de Curto Estimada: **{i_total_ka:.3f} kA**")
            
            st.markdown("---")
            st.write(f"Detalhes:")
            st.write(f"- Corrente Nominal: {i_nom:.1f} A")
            st.write(f"- Icc do Trafo: {(i_cc_trafo/1000):.3f} kA")
            if motor_contrib:
                st.write(f"- Contrib. Motores: {(i_motor/1000):.3f} kA")
            
            st.info("💡 Copie o valor em **kA** acima e cole na aba 'Cálculo de Energia Incidente'.")
