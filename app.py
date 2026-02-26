# --- 6. ABA 2: CÁLCULOS E RESULTADOS (RESTAURADA E CONECTADA) ---
with tabs[1]:
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        v_oc = st.number_input("Tensão Voc (kV)", value=13.80, format="%.2f")
        i_bf = st.number_input("Curto Ibf (kA)", value=4.85, format="%.2f")
        t_ms = st.number_input("Tempo T (ms)", value=488.0, format="%.2f")
    with col_c2:
        # Busca o GAP e Distância definidos no equipamento da Aba 1
        gap_g = st.number_input("Gap G (mm)", value=float(info['gap']), format="%.2f")
        dist_d = st.number_input("Distância D (mm)", value=float(info['dist']), format="%.2f")
    
    if st.button("Calcular Resultados"):
        # Coeficientes Técnicos
        k_ia = {
            600: [-0.04287, 1.035, -0.083, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092], 
            2700: [0.0065, 1.001, -0.024, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729], 
            14300: [0.005795, 1.015, -0.011, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729]
        }
        k_en = {
            600: [0.753364, 0.566, 1.752636, 0, 0, -4.783e-9, 1.962e-6, -0.000229, 0.003141, 1.092, 0, -1.598, 0.957], 
            2700: [2.40021, 0.165, 0.354202, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.569, 0.9778], 
            14300: [3.825917, 0.11, -0.999749, -1.557e-12, 4.556e-10, -4.186e-8, 8.346e-7, 5.482e-5, -0.003191, 0.9729, 0, -1.568, 0.99]
        }
        
        # Fator CF usando as dimensões (Manuais ou Automáticas) da Aba 1
        ees = (alt/25.4 + larg/25.4) / 2.0
        cf = -0.0003*ees**2 + 0.03441*ees + 0.4325
        
        # Cálculos intermediários para os 3 níveis de tensão (0.6, 2.7 e 14.3 kV)
        v_niveis = [0.6, 2.7, 14.3]
        ia_n = [calc_ia_step(i_bf, gap_g, k_ia[int(v*1000 if v > 0.6 else 600)]) for v in v_niveis]
        en_n = [calc_en_step(ia, i_bf, gap_g, dist_d, t_ms, k_en[int(v*1000 if v > 0.6 else 600)], cf) for ia, v in zip(ia_n, v_niveis)]
        dl_n = [calc_dla_step(ia, i_bf, gap_g, t_ms, k_en[int(v*1000 if v > 0.6 else 600)], cf) for ia, v in zip(ia_n, v_niveis)]
        
        # --- INTERPOLAÇÃO FINAL ---
        ia_final = interpolar(v_oc, ia_n[0], ia_n[1], ia_n[2])
        en_cal = interpolar(v_oc, en_n[0], en_n[1], en_n[2])
        en_joule = en_cal * 4.184
        dla_final = interpolar(v_oc, dl_n[0], dl_n[1], dl_n[2])
        
        # --- LÓGICA DE VESTIMENTA (EPI) ---
        if en_cal <= 1.2: vest = "Mínimo: Roupa comum (Algodão)"
        elif en_cal <= 4: vest = "Categoria 1 (Mín. 4 cal/cm²)"
        elif en_cal <= 8: vest = "Categoria 2 (Mín. 8 cal/cm²)"
        elif en_cal <= 25: vest = "Categoria 3 (Mín. 25 cal/cm²)"
        elif en_cal <= 40: vest = "Categoria 4 (Mín. 40 cal/cm²)"
        else: vest = "PERIGO: Acima de 40 cal/cm²"

        # --- EXIBIÇÃO DOS RESULTADOS ---
        st.markdown("---")
        st.subheader("📊 Resultados Finais")
        r1, r2, r3 = st.columns(3)
        r1.metric("Iarc Final (kA)", f"{ia_final:.2f}")
        r2.metric("Energia (cal/cm²)", f"{en_cal:.2f}")
        r3.metric("Energia (J/cm²)", f"{en_joule:.2f}")
        
        r4, r5 = st.columns(2)
        r4.metric("DLA (Fronteira mm)", f"{dla_final:.0f}")
        r5.info(f"**Vestimenta Recomendada:**\n\n{vest}")
