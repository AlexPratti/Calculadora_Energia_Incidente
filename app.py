import streamlit as st
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cálculo de Energia Incidente", page_icon="⚡", layout="wide")

st.title("⚡ Sistema de Análise de Arc Flash (NBR 17227)")
st.markdown("---")

# --- INICIALIZAÇÃO DE ESTADO (MEMÓRIA) ---
if 'corrente_stored' not in st.session_state:
    st.session_state['corrente_stored'] = 5.0 

if 'resultado_icc_detalhe' not in st.session_state:
    st.session_state['resultado_icc_detalhe'] = None

# --- FUNÇÃO CALLBACK (CÁLCULO DO CURTO) ---
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

    # Linha 1: Dados Elétricos
    col_in1, col_in2, col_in3 = st.columns(3)
    
    with col_in1:
        tensao = st.number_input("1. Tensão Nominal (kV)", value=13.80, format="%.3f", help="Ex: 0.38 ou 13.8")
    with col_in2:
        corrente = st.number_input("2. Corrente de Curto (kA)", key="corrente_stored", format="%.3f")
    with col_in3:
        tempo = st.number_input("3. Tempo de Arco (s)", value=0.500, format="%.4f", help="Tempo de atuação.")

    st.markdown("---")
    st.subheader("Geometria e Distâncias (Opcional)")
    st.caption("Se deixar 0, o sistema aplica o padrão da norma.")

    # Linha 2: Geometria
    col_geo1, col_geo2 = st.columns(2)
    
    with col_geo1:
        gap = st.number_input("4. Gap dos Eletrodos (mm)", value=152.0, step=1.0)
    with col_geo2:
        distancia = st.number_input("5. Distância de Trabalho (mm)", value=914.0, step=10.0)

    # --- LÓGICA CORRIGIDA (IEEE 1584) ---
    def calcular_energia_final():
        g_calc = gap
        d_calc = distancia
        
        if g_calc <= 0:
            g_calc = 152.0 if tensao >= 1.0 else 25.0
        
        if d_calc <= 0:
            d_calc = 914.0 if tensao >= 1.0 else 457.2

        lg_i = math.log10(corrente) if corrente > 0 else 0
        
        if tensao < 1.0:
            # BT (< 1 kV)
            k_base = -0.555
            k_i = 1.081
            k_g = 0.0011
            
            lg_en = k_base + (k_i * lg_i) + (k_g * g_calc)
            en = 10 ** lg_en
            x_dist = 2.0
            
            fator_v = 1.0
            if tensao < 0.6: 
                fator_v = 0.85 
        else:
            # MT (>= 1 kV)
            k_base = -0.555
            k_i = 1.081
            k_g = 0.0011
            
            lg_en = k_base + (k_i * lg_i) + (k_g * g_calc)
            en = 10 ** lg_en
            x_dist = 2.0
            fator_v = 1.0

        cf = 1.0
        e_final = cf * en * (tempo / 0.2) * ((610 / d_calc) ** x_dist)
        
        if tensao >= 1.0:
            e_final = e_final * 1.15
        else:
            e_final = e_final * fator_v

        return e_final, g_calc, d_calc

    st.write("")
    if st.button("Calcular Energia", type="primary", use_container_width=True):
        if tensao > 0 and corrente > 0 and tempo > 0:
            res, g_used, d_used = calcular_energia_final()
            
            if res < 1.2: 
                cat, cor = "Risco Mínimo", "green"
            elif res < 4.0: 
                cat, cor = "Categoria 1 ou 2 (Até 4)", "orange"
            elif res < 8.0: 
                cat, cor = "Categoria 2 (Até 8)", "darkorange"
            elif res < 25.0: 
                cat, cor = "Categoria 3 (Até 25)", "red"
            elif res < 40.0: 
                cat, cor = "Categoria 4 (Até 40)", "darkred"
            else: 
                cat, cor = "PERIGO EXTREMO (> 40)", "black"

            st.success("Cálculo Realizado!")
            col_res1, col_res2 = st.columns([1, 2])
            
            with col_res1:
                st.metric(label="Energia Incidente", value=f"{res:.2f} cal/cm²")
            
            with col_res2:
                st.markdown(f"""
                <div style='background-color:{cor};color:white;padding:15px;text-align:center;border-radius:10px;margin-top:5px;'>
                    <h3 style='margin:0'>{cat}</h3>
                </div>
                """, unsafe_allow_html=True)
            
            st.caption(f"Parâmetros utilizados: Gap {g_used}mm | Distância {d_used}mm")

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
        st.info(f"""
        **Detalhamento:**
        *   Corrente Nominal: {dados['nom']:.1f} A
        *   Contribuição do Trafo: {dados['trafo_ka']:.3f} kA
        *   Contribuição Motores: {dados['motor_ka']:.3f} kA
        
        ✅ **Valor enviado automaticamente para a Aba 1.**
        """)
