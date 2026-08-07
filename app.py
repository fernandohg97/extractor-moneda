import streamlit as st
import pypdf
import re

st.set_page_config(page_title="Extractor Nu -> Moneda.pro & Sheets", page_icon="💳", layout="centered")

st.title("💳 Extractor Nu")
st.write("Sube tu estado de cuenta en PDF para generar los datos para **Moneda.pro** y **Google Sheets**.")

PROD_DAYANA_KEYWORDS = [
    "abts el mayorista", 
    "teip impresiones", 
    "abts ctrl mayorista pr", 
    "envases y plasticos", 
    "abts el mayorista mark", 
    "abts guga ensenada", 
    "ley ensenada"
]

MONTHS_MAP = {
    'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06',
    'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
}

MONTHS_NAME = {
    '01': 'ENERO', '02': 'FEBRERO', '03': 'MARZO', '04': 'ABRIL', '05': 'MAYO', '06': 'JUNIO',
    '07': 'JULIO', '08': 'AGOSTO', '09': 'SEPTIEMBRE', '10': 'OCTUBRE', '11': 'NOVIEMBRE', '12': 'DICIEMBRE'
}

uploaded_file = st.file_uploader("Arrastra o selecciona aquí tu PDF de NU", type=["pdf"])

if uploaded_file is not None:
    reader = pypdf.PdfReader(uploaded_file)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    # 1. Identificar Fecha de Corte
    corte_match = re.search(r'Fecha de corte:?\s*\|?\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', full_text, re.IGNORECASE)
    
    if corte_match:
        dia_corte = corte_match.group(1)
        mes_corte_str = corte_match.group(2).upper()
        anio_corte = corte_match.group(3)
        
        mes_num = MONTHS_MAP.get(mes_corte_str, '01')
        nombre_mes = MONTHS_NAME.get(mes_num, mes_corte_str)
        
        st.success(f"📅 **Fecha de corte:** {dia_corte} {mes_corte_str} {anio_corte} | Filtrando gastos de **{nombre_mes}**")

        # 2. Extraer transacciones
        pattern = re.compile(r'(\d{2}\s+[A-Z]{3}\s+\d{4})\s+(\d{2}\s+[A-Z]{3}\s+\d{4})\s+(.*?)\s+([\+\-]\$[\d,]+\.\d{2})')
        matches = pattern.findall(full_text)

        gastos_moneda = []
        gastos_sheets = []

        for m in matches:
            fecha_op, fecha_cargo, desc, monto = m
            desc_clean = desc.split('|')[0].strip()
            
            # Solo cargos / egresos (+)
            if monto.startswith('+$'):
                d, mon, y = fecha_op.split()
                if mon.upper() == mes_corte_str:
                    formatted_date = f"{y}-{MONTHS_MAP.get(mon.upper(), '01')}-{d}"
                    
                    d_clean = re.sub(r'^(88\s*|Ztl\*|Sgt\*)', '', desc_clean).strip()
                    d_lower = d_clean.lower()
                    
                    has_cat = any(kw in d_lower for kw in PROD_DAYANA_KEYWORDS)
                    categoria = "Produccion Dayana" if has_cat else "Varios"
                    
                    monto_val = monto.replace('+$', '').replace(',', '').strip()
                    
                    # 1. Formato Moneda.pro (delimitado por comas)
                    line_moneda = f"Gasto, ${monto_val}, {categoria}, NU (CREDITO), {formatted_date}, {d_clean}"
                    gastos_moneda.append(line_moneda)
                    
                    # 2. Formato Google Sheets (delimitado por tabulaciones \t para columnas en Excel/Sheets)
                    line_sheets = f"Gasto\t{monto_val}\t{categoria}\tNU (CREDITO)\t{formatted_date}\t{d_clean}"
                    gastos_sheets.append(line_sheets)

        if gastos_moneda:
            st.info(f"💡 Total de egresos procesados: **{len(gastos_moneda)}**")

            # Crear Pestañas para cada formato
            tab1, tab2 = st.tabs(["📲 Para Moneda.pro (WhatsApp)", "📊 Para Google Sheets"])

            with tab1:
                encabezado_moneda = f"Hola Moneda, registra los siguientes gastos correspondientes a mi tarjeta NU de {nombre_mes} {anio_corte}:\n\n"
                mensaje_moneda = encabezado_moneda + "\n".join(gastos_moneda)
                st.write("Copia y pega este bloque directo en WhatsApp:")
                st.text_area("Formato Moneda.pro:", mensaje_moneda, height=350, key="txt_moneda")

            with tab2:
                # Encabezado de columnas para Google Sheets
                header_sheets = "Tipo\tMonto\tCategoría\tMétodo de Pago\tFecha\tDescripción\n"
                mensaje_sheets = header_sheets + "\n".join(gastos_sheets)
                st.write("Copia el texto de abajo, ve a Google Sheets, selecciona la celda **A1** y presiona **Pegar (Ctrl + V)**:")
                st.text_area("Formato celdas Google Sheets:", mensaje_sheets, height=350, key="txt_sheets")

        else:
            st.warning(f"No se encontraron gastos pertenecientes al mes de {nombre_mes}.")
    else:
        st.error("No se pudo detectar la Fecha de Corte en el PDF subido.")
