import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generar_pdf_reporte(df_filtrado, fecha_inicio, fecha_fin, total_ingresos, total_egresos, balance):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Estilos de texto
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E293B'))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#64748B'))
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=14, leading=18, textColor=colors.HexColor('#0F172A'))
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10)
    header_cell_style = ParagraphStyle('HeaderCellStyle', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.white, fontName='Helvetica-Bold')

    # Encabezado
    story.append(Paragraph("Reporte Financiero - Dayana", title_style))
    story.append(Paragraph(f"Período: {fecha_inicio} a {fecha_fin}", subtitle_style))
    story.append(Spacer(1, 15))
    
    # Tarjetas Resumen (Totales)
    resumen_data = [
        [Paragraph("<b>Ingresos Totales</b>", cell_style), Paragraph("<b>Egresos Totales</b>", cell_style), Paragraph("<b>Balance del Período</b>", cell_style)],
        [f"${total_ingresos:,.2f}", f"${total_egresos:,.2f}", f"${balance:,.2f}"]
    ]
    t_resumen = Table(resumen_data, colWidths=[180, 180, 180])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor('#166534')), # Verde
        ('TEXTCOLOR', (1,1), (1,1), colors.HexColor('#991B1B')), # Rojo
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,1), (-1,1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1'))
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 20))

    # Resumen por Categoría (Egresos)
    if not df_filtrado.empty and 'Gasto' in df_filtrado['Tipo'].values:
        story.append(Paragraph("Egresos por Categoría", h2_style))
        story.append(Spacer(1, 8))
        
        df_egresos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']
        cat_summary = df_egresos.groupby('Categoria')['Monto'].sum().reset_index()
        total_exp = cat_summary['Monto'].sum()
        cat_summary['%'] = (cat_summary['Monto'] / total_exp) * 100
        cat_summary = cat_summary.sort_values(by='Monto', ascending=False)

        cat_table_data = [[Paragraph("<b>Categoría</b>", header_cell_style), Paragraph("<b>Total</b>", header_cell_style), Paragraph("<b>% Egresos</b>", header_cell_style)]]
        for _, r in cat_summary.iterrows():
            cat_table_data.append([
                Paragraph(str(r['Categoria']), cell_style),
                f"${r['Monto']:,.2f}",
                f"{r['%']:.1f}%"
            ])

        t_cat = Table(cat_table_data, colWidths=[240, 150, 150])
        t_cat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_cat)
        story.append(Spacer(1, 20))

    # Detalle de Transacciones (Paginado automático)
    story.append(Paragraph("Detalle de Transacciones", h2_style))
    story.append(Spacer(1, 8))

    headers = ["Fecha", "Tipo", "Descripción", "Método", "Categoría", "Valor"]
    tx_table_data = [[Paragraph(f"<b>{h}</b>", header_cell_style) for h in headers]]

    for _, r in df_filtrado.iterrows():
        tx_table_data.append([
            Paragraph(str(r['Fecha']), cell_style),
            Paragraph(str(r['Tipo']), cell_style),
            Paragraph(str(r['Descripcion'])[:30], cell_style),
            Paragraph(str(r['Metodo_Pago']), cell_style),
            Paragraph(str(r['Categoria']), cell_style),
            f"${r['Monto']:,.2f}"
        ])

    t_tx = Table(tx_table_data, colWidths=[65, 50, 165, 85, 90, 85], repeatRows=1)
    t_tx.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tx)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
