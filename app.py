import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
# Aqui está a correção: Usando o link RAW direto do seu repositório GitHub
st.set_page_config(
    page_title="Calculadora de Energia Incidente",
    page_icon="https://raw.githubusercontent.com/AlexPratti/Calculadora_Energia_Incidente/main/icone.png",
    layout="centered"
)

# --- TÍTULO E CABEÇALHO ---
st.title("⚡ Calculadora de Energia Incidente")
st.markdown("Use esta ferramenta para estimar a energia incidente e determinar a categoria de risco.")

st.divider()

# --- ENTRADA DE DADOS ---
st.subheader("Parâmetros do Sistema")

col1, col2 = st.columns(2)

with col1:
    corrente_falta = st.number_input(
        "Corrente de Falta (kA)", 
        min_value=0.0, 
        value=10.0, 
        step=0.1,
        help="Insira a corrente de curto-circuito presumida em quiloamperes."
    )
    tempo_arco = st.number_input(
        "Tempo de Arco (segundos)", 
        min_value=0.00, 
        value=0.10, 
        step=0.01,
        help="Tempo de atuação da proteção."
    )

with col2:
    distancia = st.number_input(
        "Distância de Trabalho (cm)", 
        min_value=10.0, 
        value=45.0, 
        step=1.0,
        help="Distância entre o rosto/peito do trabalhador e a fonte do arco."
    )
    # Seleção de tipo de equipamento para refinar o cálculo (fator de caixa)
    tipo_equipamento = st.selectbox(
        "Tipo de Equipamento",
        ["Painel Aberto (Ar Livre)", "Painel Fechado (Box)"],
        index=1
    )

# --- CÁLCULO ---
if st.button("Calcular Energia Incidente", type="primary"):
    
    # Lógica de cálculo simplificada baseada em modelos de estimativa (Ralph Lee / IEEE genérico)
    # Fórmula básica para Energia (E) em cal/cm²
    
    # Definição de fator baseando-se se é ar livre ou caixa fechada (efeito de reflexão)
    if tipo_equipamento == "Painel Fechado (Box)":
        fator_confinamento = 1.5  # Energia é focada na direção do trabalhador
    else:
        fator_confinamento = 1.0  # Energia se dissipa em 360 graus

    # Fórmula: Constante * Voltagem(assume-se baixa/média) * Corrente * Tempo / Distância^2
    # Ajuste empírico para demonstração funcional
    # E ≈ 1038.7 * I_kA * t * fator / D_cm^2 (Modelo teórico simplificado)
    
    energia_incidente = (1038.7 * corrente_falta * tempo_arco * fator_confinamento) / (distancia ** 2)

    # Determinação da Categoria de Risco (Baseado na NFPA 70E)
    if energia_incidente < 1.2:
        categoria = "Isento / Categoria 0"
        cor_alerta = "green"
    elif 1.2 <= energia_incidente < 4.0:
        categoria = "Categoria 1"
        cor_alerta = "orange"
    elif 4.0 <= energia_incidente < 8.0:
        categoria = "Categoria 2"
        cor_alerta = "orange"
    elif 8.0 <= energia_incidente < 25.0:
        categoria = "Categoria 3"
        cor_alerta = "red"
    elif 25.0 <= energia_incidente < 40.0:
        categoria = "Categoria 4"
        cor_alerta = "red"
    else:
        categoria = "PERIGO EXTREMO (Energia > 40 cal/cm²)"
        cor_alerta = "darkred"

    # --- EXIBIÇÃO DOS RESULTADOS ---
    st.divider()
    st.subheader("Resultados da Análise")

    res_col1, res_col2 = st.columns(2)

    with res_col1:
        st.metric(label="Energia Incidente", value=f"{energia_incidente:.2f} cal/cm²")

    with res_col2:
        st.markdown(f"**Categoria de Risco:**")
        st.markdown(f":{cor_alerta}[**{categoria}**]")

    # Alerta visual
    if energia_incidente > 40:
        st.error("⚠️ ATENÇÃO: A energia incidente excede 40 cal/cm². O trabalho não é permitido, mesmo com EPI.")
    elif energia_incidente > 1.2:
        st.warning("⚠️ O uso de EPI adequado (Vestimenta resistente a arco) é obrigatório.")
    else:
        st.success("✅ Risco baixo. Utilize EPI básico (algodão tratado) e óculos de proteção.")

# --- RODAPÉ ---
st.markdown("---")
st.caption("Desenvolvido para fins de estudo e simulação.")
