from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

# Crear PDF
pdf_path = "/app/frontend/public/downloads/EJEMPLO_REPORTE_CONSOLIDADO_IA.pdf"
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
story = []
styles = getSampleStyleSheet()

# Estilos
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=20,
    textColor=colors.HexColor('#1a202c'),
    spaceAfter=12,
    alignment=1
)

heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=14,
    textColor=colors.HexColor('#2d3748'),
    spaceAfter=10,
    spaceBefore=10
)

# Título
story.append(Paragraph("REPORTE CONSOLIDADO DE PAGO", title_style))
story.append(Paragraph("Lote: ee452ed8", styles['Normal']))
story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
story.append(Spacer(1, 0.3*inch))

# Resumen ejecutivo
story.append(Paragraph("RESUMEN EJECUTIVO", heading_style))

resumen_data = [
    ['Campo', 'Información'],
    ['Tercero/Beneficiario', 'Consultores Tech SAS'],
    ['NIT', '900.123.456-7'],
    ['Valor Total', '$5,000,000 COP'],
    ['Concepto', 'Pago servicios profesionales consultoría TI'],
    ['Referencia Bancaria', '789456123'],
    ['Banco', 'Banco de Bogotá'],
    ['Documentos Incluidos', '4 documentos'],
    ['Estado de Validación', '✓ APROBADO']
]

resumen_table = Table(resumen_data, colWidths=[2.5*inch, 4*inch])
resumen_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 12),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 10),
    ('TOPPADDING', (0, 1), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
]))

story.append(resumen_table)
story.append(Spacer(1, 0.3*inch))

# Detalle de documentos
story.append(Paragraph("DETALLE DE DOCUMENTOS ANALIZADOS POR IA", heading_style))
story.append(Spacer(1, 0.1*inch))

# Documento 1: Comprobante de Egreso
story.append(Paragraph("1. COMPROBANTE DE EGRESO", heading_style))
doc1_data = [
    ['Campo', 'Valor Extraído por GPT-5.2'],
    ['Nombre Archivo', 'comprobante_egreso_001.pdf'],
    ['Número', 'CE-2025-001'],
    ['Fecha Documento', '15 de Enero de 2025'],
    ['Concepto', 'Pago servicios profesionales consultoría TI'],
    ['Tercero', 'Consultores Tech SAS'],
    ['NIT', '900.123.456-7'],
    ['Valor', '$5,000,000 COP'],
    ['Referencia', '789456123'],
    ['Aprobado por', 'María Rodríguez - Gerente Financiero']
]

doc1_table = Table(doc1_data, colWidths=[2.5*inch, 4*inch])
doc1_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc1_table)
story.append(Spacer(1, 0.2*inch))

# Documento 2: Cuenta Por Pagar
story.append(Paragraph("2. CUENTA POR PAGAR", heading_style))
doc2_data = [
    ['Campo', 'Valor Extraído por GPT-5.2'],
    ['Nombre Archivo', 'cuenta_por_pagar_001.pdf'],
    ['Número', 'CPP-2025-001'],
    ['Fecha', '15 de Enero de 2025'],
    ['Proveedor', 'Consultores Tech SAS'],
    ['Concepto', 'Servicios profesionales mes de Enero'],
    ['Valor Total', '$5,000,000 COP'],
    ['Estado', 'Pendiente de Pago'],
    ['Vencimiento', '30 de Enero de 2025']
]

doc2_table = Table(doc2_data, colWidths=[2.5*inch, 4*inch])
doc2_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc2_table)
story.append(Spacer(1, 0.2*inch))

# Nueva página
story.append(PageBreak())

# Documento 3: Factura
story.append(Paragraph("3. FACTURA", heading_style))
doc3_data = [
    ['Campo', 'Valor Extraído por GPT-5.2'],
    ['Nombre Archivo', 'factura_001.pdf'],
    ['Factura No.', 'FV-2025-001'],
    ['Fecha', '10 de Enero de 2025'],
    ['Cliente', 'Su Empresa SAS'],
    ['Proveedor', 'Consultores Tech SAS'],
    ['NIT', '900.123.456-7'],
    ['Detalle', 'Consultoría técnica especializada: $4,200,000'],
    ['IVA (19%)', '$798,000'],
    ['TOTAL', '$5,000,000 COP']
]

doc3_table = Table(doc3_data, colWidths=[2.5*inch, 4*inch])
doc3_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc3_table)
story.append(Spacer(1, 0.2*inch))

# Documento 4: Soporte de Pago
story.append(Paragraph("4. SOPORTE DE PAGO", heading_style))
doc4_data = [
    ['Campo', 'Valor Extraído por GPT-5.2'],
    ['Nombre Archivo', 'soporte_pago_001.pdf'],
    ['Tipo', 'Comprobante Bancario'],
    ['Fecha Transacción', '15 de Enero de 2025'],
    ['Banco', 'Banco de Bogotá'],
    ['Cuenta Origen', '****1234'],
    ['Beneficiario', 'Consultores Tech SAS'],
    ['Cuenta Destino', '****5678'],
    ['Valor', '$5,000,000 COP'],
    ['Referencia', '789456123'],
    ['Estado', 'APROBADO']
]

doc4_table = Table(doc4_data, colWidths=[2.5*inch, 4*inch])
doc4_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc4_table)
story.append(Spacer(1, 0.3*inch))

# Nueva página para validaciones
story.append(PageBreak())

# Validaciones
story.append(Paragraph("VALIDACIONES Y VERIFICACIONES AUTOMÁTICAS", heading_style))
story.append(Spacer(1, 0.1*inch))

validaciones = [
    ['Estado', 'Validación', 'Detalle'],
    ['✓', 'Consistencia de Valores', 'Todos los documentos reportan el mismo valor: $5,000,000 COP'],
    ['✓', 'Consistencia de Tercero', 'Todos los documentos corresponden al mismo beneficiario: Consultores Tech SAS'],
    ['✓', 'Completitud', 'El lote incluye los 4 tipos de documentos requeridos (CE, CPP, Factura, Soporte)'],
    ['✓', 'Correlación Bancaria', 'La referencia bancaria 789456123 coincide entre CE y Soporte de Pago'],
    ['✓', 'Validación de Fechas', 'Las fechas son consistentes y están dentro del período esperado'],
    ['✓', 'Validación de NIT', 'El NIT 900.123.456-7 coincide en todos los documentos aplicables']
]

val_table = Table(validaciones, colWidths=[0.6*inch, 2.4*inch, 3.5*inch])
val_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#48bb78')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
    ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0fff4')),
    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#48bb78')),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(val_table)
story.append(Spacer(1, 0.3*inch))

# Conclusión
story.append(Paragraph("CONCLUSIÓN Y RECOMENDACIÓN", heading_style))
conclusion_text = """
<b>Resultado del Análisis Automático:</b><br/>
Los 4 documentos han sido analizados exitosamente mediante Inteligencia Artificial (GPT-5.2). 
Todas las validaciones han sido superadas satisfactoriamente. El pago a Consultores Tech SAS 
por valor de $5,000,000 COP cuenta con la documentación completa y consistente requerida.<br/><br/>
<b>Recomendación:</b> APROBAR PAGO<br/>
<b>Motivo:</b> Documentación completa, valores consistentes, beneficiario verificado.
"""
story.append(Paragraph(conclusion_text, styles['Normal']))
story.append(Spacer(1, 0.3*inch))

# Pie de página
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("_" * 90, styles['Normal']))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("<b>Generado por:</b> Administrador (admin@docflow.com)", styles['Normal']))
story.append(Paragraph("<b>Sistema:</b> DocFlow - Gestión Documental Inteligente", styles['Normal']))
story.append(Paragraph("<b>Tecnología:</b> Este documento fue generado automáticamente mediante análisis de IA (GPT-5.2)", styles['Normal']))
story.append(Paragraph(f"<b>Fecha y hora:</b> {datetime.now().strftime('%d de %B de %Y, %H:%M:%S')}", styles['Normal']))

# Construir PDF
doc.build(story)

print(f"✓ PDF de ejemplo generado: {pdf_path}")
print(f"  Este es un EJEMPLO de cómo se vería el reporte final con")
print(f"  información REAL extraída por GPT-5.2 de los documentos.")
