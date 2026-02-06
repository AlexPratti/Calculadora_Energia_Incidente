import streamlit as st
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

st.title("⚡ Sistema de Análise de Arc Flash (NBR 17227)")
st.markdown("---")

# --- INICIALIZAÇÃO DE ESTADO (MEMÓRIA) ---
if 'corrente_stored' not in st.session_state:
    st.session_state['corrente_stored'] = 17.0

# --- FUNÇÃO CALLBACK (O SEGREDO PARA NÃO DAR ERRO) ---
# Esta função roda ANTES de desenhar a tela, evitando o erro de "widget já renderizado"
def atualizar_icc():
    # Pega os valores dos inputs da Aba 2 (através das keys)
    try:
        t_kva = st.session_state['k_kva']
        t_v = st.session_state['k_v']
        t_z = st.session_state['k_z']
        usar_motor = st.session_state['k_motor']
        
        if t_v > 0 and t_z > 0:
            # 1. Corrente Nominal
            i_nom = (t_kva * 1000) / (math.sqrt(3) * t_v)
            
            # 2. Curto no Trafo
            i_cc_trafo = i_nom / (t_z / 100)
            
            # 3. Contribuição de Motores
            i_motor = 0
            if usar_motor:
                i_motor = 4 * i_nom 
            
            i_total_ka = (i_cc_trafo + i_motor) / 1000
            
            # ATUALIZA O VALOR DA ABA 1
            st.session_state['corrente_stored'] = i_total_ka
            st.toast(f"✅ Icc Atualizada: {i_total_ka:.3f} kA", icon="🔄")
            
    except Exception as e:
        st.error(f"Erro no cálculo: {e}")

# Criando abas
tab1, tab2 = st.tabs(["🔥 Cálculo de Energia Incidente", "🧮 Estimativa de Icc (Curto-Circuito)"])

# =======================================================
# ABA 1: CÁLCULO DE ENERGIA (ARC FLASH)
# =======================================================
with tab1:
    st.header("Cálculo da Energia Incidente")
    st.info("O campo de Corrente abaixo aceita digitação manual OU atualização automática pela Aba 2.")

    col_in1, col_in2 = st.columns(2)
    
    with col_in1:
        tensao = st.number_input("1. Tensão Nominal (kV)", value=0.38, format="%.3f", help="Ex: 0.38 para 380V")
        tempo = st.number_input("3. Tempo de Arco (s)", value=0.200, format="%.4f", help="Tempo de atuação da proteção.")
        
    with col_in2:
        # Este campo está ligado à memória 'corrente_stored'
        corrente = st.number_input(
            "2. Corrente de Curto (kA)", 
            key="corrente_stored", 
            format="%.3f", 
            help="Ibf: Pode digitar ou calcular na outra aba."
        )
        
    with st.expander("Configurações Avançadas de Geometria (Opcional)"):
        gap = st.number_input("Gap dos Eletrodos (mm)", value=0.0, step=1.0)
        distancia = st.number_input("Distância de Trabalho (mm)", value=0.0, step=10.0)

    # Função de Cálculo da Energia
    def calcular_energia_final():
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
        
        # Correção Logs
        g_val = gap_local if gap_local > 0 else 1
        d_val = dist_local if dist_local > 0 else 1
        log_G = math.log10(g_val)
        log_D = math.log10(d_val)

        I_arc = fator_Iarc * corrente
        log_Iarc = math.log10(I_arc) if I_arc > 0 else 0

        expoente = k1 + (k2 * log_Ibf) + (k3 * log_G) + (c_dist * log_D) + (0.99 * log_Iarc)
        
        E_joules = 0.25104 * (tempo * 1000) * (10 ** expoente)
        E_joules = E_joules * fator_box
        E_cal = E_joules / 4.184
        
        return E_cal, gap_local, dist_local

    if st.button("Calcular Energia", type="primary"):
        if tensao > 0 and corrente > 0 and tempo > 0:
            res, g_used, d_used = calcular_energia_final()
            
            # Categorias
            if res < 1.2: cat, cor = "Risco Mínimo", "green"
            elif res < 4.0: cat, cor = "Categoria 1 ou 2", "orange"
            elif res < 8.0: cat, cor = "Categoria 2", "darkorange"
            elif res < 40.0: cat, cor = "Categoria 3 ou 4", "red"
            else: cat, cor = "PERIGO EXTREMO", "black"

            st.metric(label="Energia Incidente", value=f"{res:.2f} cal/cm²")
            st.markdown(f"<div style='background-color:{cor};color:white;padding:15px;text-align:center;border-radius:10px;'><h3>{cat}</h3></div>", unsafe_allow_html=True)
            st.caption(f"Gap usado: {g_used}mm | Distância usada: {d_used}mm")

# =======================================================
# ABA 2: CALCULADORA DE CURTO-CIRCUITO (AUXILIAR)
# =======================================================
with tab2:
    st.header("Estimativa de Icc pelo Transformador")
    st.markdown("Os valores abaixo alimentam a calculadora automaticamente ao clicar no botão.")
    
    col_trafo1, col_trafo2 = st.columns(2)
    
    # Adicionamos 'key' para cada input para podermos ler na função 'atualizar_icc'
    with col_trafo1:
        st.number_input("Potência do Transformador (kVA)", value=1000.0, step=100.0, key="k_kva")
        st.number_input("Tensão Secundária (Volts)", value=380.0, step=10.0, key="k_v")
        
    with col_trafo2:
        st.number_input("Impedância (Z%)", value=5.0, step=0.1, key="k_z")
        st.checkbox("Incluir contribuição de motores?", value=True, key="k_motor")

    # BOTÃO COM CALLBACK (ON_CLICK)
    # Isso garante que o cálculo ocorra antes da tela ser renderizada
    st.button("Calcular e Atualizar Icc (kA)", type="primary", on_click=atualizar_icc)
