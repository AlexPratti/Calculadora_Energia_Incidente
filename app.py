import streamlit as st
import numpy as np
import io
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# --- [Omiti as funções técnicas calc_ia, calc_en, calc_dla para focar no Relatório, mas elas devem permanecer iguais] ---

with tab3:
    if 'res' in st.session_state:
        r = st.session_state['res']
        st.subheader("📄 Geração de Relatório Técnico Detalhado")
        st.write("O relatório incluirá a fundamentação da NBR 17227 e recomendações de EPI.")

        def gerar_pdf_detalhado():
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            elementos = []

            # Cabeçalho
            elementos.append(Paragraph("<b>LAUDO TÉCNICO DE ESTUDO DE ARCO ELÉTRICO</b>", styles['Title']))
            elementos.append(Paragraph(f"Data de Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
            elementos.append(Spacer(1, 1*cm))

            # 1. Identificação do Equipamento
            elementos.append(Paragraph("<b>1. IDENTIFICAÇÃO DO EQUIPAMENTO</b>", styles['Heading2']))
            elementos.append(Paragraph(f"Equipamento Analisado: {r['Equip']}", styles['Normal']))
            elementos.append(Spacer(1, 0.5*cm))

            # 2. Resumo dos Resultados
            elementos.append(Paragraph("<b>2. RESULTADOS DO CÁLCULO</b>", styles['Heading2']))
            dados_resumo = [
                ["Corrente de Arco (Iarc)", f"{r['I']:.3f} kA"],
                ["Energia Incidente", f"{r['E']:.4f} cal/cm²"],
                ["Fronteira de Arco (DLA)", f"{r['D']:.1f} mm"],
                ["Categoria da Vestimenta", f"{r['Cat']}"]
            ]
            t = Table(dados_resumo, colWidths=[6*cm, 6*cm])
            t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')]))
            elementos.append(t)
            elementos.append(Spacer(1, 0.5*cm))

            # 3. Fundamentação Teórica (Solicitado)
            elementos.append(Paragraph("<b>3. MEMORIAL DE CÁLCULO E REFERÊNCIAS</b>", styles['Heading2']))
            texto_norma = (
                "Os cálculos acima foram realizados rigorosamente conforme a <b>NBR 17227:2025</b>. "
                "Foram aplicados modelos matemáticos de propagação de calor para arco em espaços confinados, "
                "considerando: Interpolação de tensão (Voc), Efeito de borda do invólucro (Fator Cf), "
                "Geometria do GAP entre condutores e Tempo de atuação da proteção."
            )
            elementos.append(Paragraph(texto_norma, styles['Normal']))
            elementos.append(Spacer(1, 0.5*cm))

            # 4. Esclarecimento sobre Classificação (Solicitado)
            elementos.append(Paragraph("<b>4. ESCLARECIMENTOS SOBRE A CATEGORIA</b>", styles['Heading2']))
            texto_esclarecimento = (
                f"A energia de {r['E']:.4f} cal/cm² foi classificada como <b>{r['Cat']}</b>. "
                "Conforme normas de segurança, valores acima de 1,2 cal/cm² (limite de queimadura de 2º grau) "
                "exigem vestimentas ignífugas (FR). A classificação visa garantir que o trabalhador não sofra "
                "lesões permanentes em caso de falha de arco no ponto de trabalho estipulado."
            )
            elementos.append(Paragraph(texto_esclarecimento, styles['Normal']))
            elementos.append(Spacer(1, 0.5*cm))

            # 5. EPIs Recomendados (Solicitado)
            elementos.append(Paragraph("<b>5. EQUIPAMENTOS DE PROTEÇÃO (EPIs) OBRIGATÓRIOS</b>", styles['Heading2']))
            
            # Lógica de EPIs baseada no resultado
            epi_lista = "• Capacete de segurança com protetor facial (Arc Rating adequado)\n"
            epi_lista += "• Protetor auricular (tipo plug ou abafador)\n"
            epi_lista += "• Luvas isolantes de borracha (classe compatível com a tensão)\n"
            epi_lista += "• Luvas de cobertura em couro (proteção mecânica)\n"
            epi_lista += "• Calçados de segurança (sem componentes metálicos expostos)\n"
            
            if "CAT 2" in r['Cat'] or "CAT 4" in r['Cat']:
                epi_lista += f"• <b>Vestimenta AR/FR {r['Cat']}</b> (calça e camisa ou macacão de peça única)\n"
                epi_lista += "• Balaclava para proteção do pescoço e cabeça"
            
            elementos.append(Paragraph(epi_lista.replace("\n", "<br/>"), styles['Normal']))

            doc.build(elementos)
            return buffer.getvalue()

        pdf = gerar_pdf_detalhado()
        st.download_button(
            label="📩 Baixar Relatório Técnico Completo (PDF)",
            data=pdf,
            file_name=f"Laudo_Arco_{r['Equip']}.pdf",
            mime="application/pdf",
            key="dl_relatorio_final"
        )
    else:
        st.info("⚠️ Realize o cálculo na Aba 'Cálculos' para gerar este laudo técnico.")
