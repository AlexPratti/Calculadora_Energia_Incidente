import streamlit as st
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡")

st.title("⚡ Cálculo da Energia Incidente")
st.markdown("Ferramenta para estimativa de Arc Flash conforme **NBR 17227 / IEEE 1584**.")
st.markdown("---")

# --- BARRA LATERAL (OPCIONAIS) ---
with st.sidebar:
    st.header("Configurações Avançadas")
    st.info("Deixe 0 para usar os valores padrão da norma.")
    gap = st.number_input("Gap dos Eletrodos (mm)", value=0.0, step=1.0, help="Distância física entre condutores.")
    distancia = st.number_input("Distância de Trabalho (mm)", value=0.0, step=10.0, help="Distância até o corpo do trabalhador.")

# --- FORMULÁRIO PRINCIPAL ---
col1, col2 = st.columns(2)

with col1:
    tensao = st.number_input("1. Tensão Nominal (kV)", value=0.38, format="%.2f", help="Ex: 0.38 para 380V ou 13.8 para 13.8kV")
    tempo = st.number_input("3. Tempo de Arco (s)", value=0.200, format="%.3f", help="Tempo total de eliminação em SEGUNDOS.")

with col2:
    corrente = st.number_input("2. Corrente de Curto (kA)", value=17.0, format="%.3f", help="Corrente de curto-circuito franca.")

# --- LÓGICA DE CÁLCULO ---
def calcular():
    # 1. Definição de Padrões
    gap_local = gap
    dist_local = distancia
    
    if gap_local <= 0:
        gap_local = 152.0 if tensao >= 1.0 else 25.0
        
    if dist_local <= 0:
        dist_local = 914.0 if tensao >= 1.0 else 457.2

    # 2. Coeficientes e Fatores
    if tensao >= 1.0:
        # Modelo MT (> 1kV)
        k1, k2, k3 = 3.82, 0.11, -1.0
        c_dist = -1.568
        fator_Iarc = 0.97
        fator_box = 1.15
    else:
        # Modelo BT (< 1kV)
        k1, k2, k3 = 3.1, 0.15, -1.2
        c_dist = -1.60
        fator_Iarc = 0.85 
        fator_box = 1.25

    # 3. Cálculo Matemático
    # Logaritmos base 10
    log_Ibf = math.log10(corrente) if corrente > 0 else 0
    log_G = math.log10(gap_local)
    log_D = math.log10(dist_local)

    # Corrente de arco estimada
    I_arc = fator_Iarc * corrente
    log_Iarc = math.log10(I_arc) if I_arc > 0 else 0

    # Equação Polinomial (IEEE 1584 simplificada)
    # Importante: log_Gap e log_Dist aqui são as variáveis locais
    expoente = k1 + (k2 * log_Ibf) + (k3 * log_G) + (c_dist * log_D) + (0.99 * log_Iarc)
    
    # Energia em Joules
    E_joules = 0.25104 * (tempo * 1000) * (10 ** expoente)
    E_joules = E_joules * fator_box # Aplica correção do invólucro
    
    # Energia em cal/cm²
    E_cal = E_joules / 4.184
    
    return E_cal, gap_local, dist_local

# --- BOTÃO E RESULTADO ---
if st.button("Calcular Energia Incidente", type="primary"):
    if tensao > 0 and corrente > 0 and tempo > 0:
        try:
            resultado, g_used, d_used = calcular()
            
            # Classificação de Risco
            cat = "Indefinido"
            cor = "gray"
            
            if resultado < 1.2:
                cat, cor = "Risco Mínimo (Necessário roupa não-derretível)", "green"
            elif resultado < 4.0:
                cat, cor = "Categoria 1 ou 2 (Até 4 cal/cm²)", "orange"
            elif resultado < 8.0:
                cat, cor = "Categoria 2 (Até 8 cal/cm²)", "darkorange"
            elif resultado < 40.0:
                cat, cor = "Categoria 3 ou 4 (Até 40 cal/cm²)", "red"
            else:
                cat, cor = "PERIGO EXTREMO (> 40 cal/cm²) - NÃO OPERAR", "black"

            st.success("Cálculo realizado com sucesso!")
            
            # Mostrador Principal
            st.metric(label="Energia Incidente Estimada", value=f"{resultado:.2f} cal/cm²")
            
            # Caixa Colorida de Categoria
            st.markdown(f"""
            <div style="background-color: {cor}; padding: 15px; border-radius: 8px; color: white; text-align: center; margin-bottom: 10px;">
                <h3 style="margin:0;">{cat}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            st.caption(f"Parâmetros utilizados: Gap={g_used}mm | Distância={d_used}mm")
            
        except Exception as e:
            st.error(f"Erro no cálculo: {e}")
    else:
        st.warning("⚠️ Por favor, preencha Tensão, Corrente e Tempo com valores maiores que zero.")
