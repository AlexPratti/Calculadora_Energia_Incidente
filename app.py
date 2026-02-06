import streamlit as st
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

st.title("⚡ Sistema de Análise de Arc Flash (NBR 17227)")
st.markdown("---")

# --- INICIALIZAÇÃO DE ESTADO (MEMÓRIA) ---
# Isso garante que o valor da corrente seja compartilhado entre as abas
if 'corrente_stored' not in st.session_state:
    st.session_state['corrente_stored'] = 17.0 # Valor inicial padrão

# Criando abas
tab1, tab2 = st.tabs(["🔥 Cálculo de Energia Incidente", "🧮 Estimativa de Icc (Curto-Circuito)"])

# =======================================================
# ABA 1: CÁLCULO DE ENERGIA (ARC FLASH)
# =======================================================
with tab1:
    st.header("Cálculo da Energia Incidente")
    st.info("Preencha os dados abaixo. Se calcular o curto na outra aba, o valor aparecerá aqui automaticamente.")

    # --- BARRA LATERAL DENTRO DA ABA ---
    col_in1, col_in2 = st.columns(2)
    
    with col_in1:
        tensao = st.number_input("1. Tensão Nominal (kV)", value=0.38, format="%.3f", help="Ex: 0.38 para 380V")
        tempo = st.number_input("3. Tempo de Arco (s)", value=0.200, format="%.4f", help="Tempo de atuação da proteção.")
        
    with col_in2:
        # AQUI ESTÁ O TRUQUE: usamos a 'key' para ligar à memória
        corrente = st.number_input("2. Corrente de Curto (kA)", key="corrente_stored", format="%.3f", help="Ibf: Corrente de curto trifásica franca.")
        
    with st.expander("Configurações Avançadas de Geometria (Opcional)"):
        st.write("Se deixar zerado, o sistema usa os padrões da norma.")
        gap = st.number_input("Gap dos Eletrodos (mm)", value=0.0, step=1.0)
        distancia = st.number_input("Distância de Trabalho (mm)", value=0.0, step=10.0)

    # Função de Cálculo
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
        
        # Correção rápida para log de Gap
        gap_log_val = gap_local if gap_local > 0 else 1
        log_G = math.log10(gap_log_val)
        
        dist_log_val = dist_local if dist_local > 0 else 1
        log_D = math.log10(dist_log_val)

        I_arc = fator_Iarc * corrente
        log_Iarc = math.log10(I_arc) if I_arc > 0 else 0

        # Importante: log_Gap estava errado na versão anterior, corrigido para log_G
        expoente = k1 + (k2 * log_Ibf) + (k3 * log_G) + (c_dist * log_D) + (0.99 * log_Iarc)
        
        E_joules = 0.25104 * (tempo * 1000) * (10 ** expoente)
        E_joules = E_joules * fator_box
        E_cal = E_joules / 4.184
        
        return E_cal, gap_local, dist_local

    if st.button("Calcular Energia", type="primary"):
        if tensao > 0 and corrente > 0 and tempo > 0:
            res, g_used, d_used = calcular_energia()
            
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
    st.markdown("Calcule aqui e o sistema enviará o resultado automaticamente para a Aba de Energia.")
    
    col_trafo1, col_trafo2 = st.columns(2)
    
    with col_trafo1:
        trafo_kva = st.number_input("Potência do Transformador (kVA)", value=1000.0, step=100.0)
        trafo_v = st.number_input("Tensão Secundária (Volts)", value=380.0, step=10.0)
        
    with col_trafo2:
        trafo_z = st.number_input("Impedância (Z%)", value=5.0, step=0.1)
        motor_contrib = st.checkbox("Incluir contribuição de motores?", value=True)

    # Botão de Calcular e Atualizar
    if st.button("Calcular e Atualizar Icc (kA)", type="primary"):
        if trafo_v > 0 and trafo_z > 0:
            # Cálculos
            i_nom = (trafo_kva * 1000) / (math.sqrt(3) * trafo_v)
            i_cc_trafo = i_nom / (trafo_z / 100)
            
            i_motor = 0
            if motor_contrib:
                i_motor = 4 * i_nom 
            
            i_total_ka = (i_cc_trafo + i_motor) / 1000
            
            # --- ATUALIZAÇÃO AUTOMÁTICA ---
            st.session_state['corrente_stored'] = i_total_ka # Atualiza a memória
            
            st.success(f"Corrente Calculada: {i_total_ka:.3f} kA")
            st.info("✅ Valor enviado automaticamente para a aba 'Cálculo de Energia Incidente'!")
            
            # Detalhes visuais
            st.write(f"Resumo: Trafo {(i_cc_trafo/1000):.2f} kA + Motores {(i_motor/1000):.2f} kA")
            
            # Força o recarregamento da página para mostrar o valor novo na outra aba
            st.rerun()
