import streamlit as st
import pypdf
import pandas as pd
import re

st.set_page_config(page_title="Extractor Nu & Odoo -> Moneda.pro & Sheets", page_icon="💳", layout="centered")

st.title("💳 Extractor Financiero (Nu / Odoo)")
st.write("Sube tu **PDF de Estado de Cuenta NU** o **CSV de Ventas Odoo**, revisa/edita las categorías y métodos de pago, y copia los resultados.")

# ==========================================
# LISTAS PREDEFINIDAS
# ==========================================
LISTA_CATEGORIAS = [
    "Produccion Dayana",
    "Ventas",
    "Varios",
    "Alimentos y Bebidas",
    "Servicios / Publicidad",
    "Transporte / Gasolina",
    "Insumos / Materiales",
    "Nómina / Honorarios"
]

LISTA_METODOS_PAGO = [
    "NU (CREDITO)",
    "Efectivo",
    "Transferencia",
    "Tarjeta de Débito",
    "Tarjeta de Crédito"
]

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

uploaded_file = st.file_uploader("Arrastra o selecciona aquí tu archivo (PDF o CSV)", type=["pdf", "csv"])

if uploaded_file is not None:
    file_type = uploaded_file.name.split('.')[-1].lower()
    data_rows = []
    encabezado_contexto = ""

    # ------------------------------------------
    # 1. PARSEAR PDF DE NU
    # ------------------------------------------
    if file_type == "pdf":
        reader = pypdf.PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        corte_match = re.search(r'Fecha de corte:?\s*\|?\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', full_text, re.IGNORECASE)
        
        if corte_match:
            dia_corte = corte_match.group(1)
            mes_corte_str = corte_match.group(2).upper()
            anio_corte = corte_match.group(3)
            mes_num = MONTHS_MAP.get(mes_corte_str, '01')
            nombre_mes = MONTHS_NAME.get(mes_num, mes_corte_str)
            
            st.success(f"📄 **PDF NU Detectado** | Fecha de corte: {dia_corte} {mes_corte_str} {anio_corte} | Gastos de **{nombre_mes}**")
            encabezado_contexto = f"Hola Moneda, registra los siguientes gastos correspondientes a mi tarjeta NU de {nombre_mes} {anio_corte}:\n\n"

            pattern = re.compile(r'(\d{2}\s+[A-Z]{3}\s+\d{4})\s+(\d{2}\s+[A-Z]{3}\s+\d{4})\s+(.*?)\s+([\+\-]\$[\d,]+\.\d{2})')
            matches = pattern.findall(full_text)

            for m in matches:
                fecha_op, fecha_cargo, desc, monto = m
                desc_clean = desc.split('|')[0].strip()
                
                if monto.startswith('+$'):
                    d, mon, y = fecha_op.split()
                    if mon.upper() == mes_corte_str:
                        formatted_date = f"{y}-{MONTHS_MAP.get(mon.upper(), '01')}-{d}"
                        d_clean = re.sub(r'^(88\s*|Ztl\*|Sgt\*)', '', desc_clean).strip()
                        d_lower = d_clean.lower()
                        
                        has_cat = any(kw in d_lower for kw in PROD_DAYANA_KEYWORDS)
                        categoria = "Produccion Dayana" if has_cat else "Varios"
                        monto_val = float(monto.replace('+$', '').replace(',', '').strip())

                        data_rows.append({
                            "Tipo": "Gasto",
                            "Monto": monto_val,
                            "Categoría": categoria,
                            "Método de Pago": "NU (CREDITO)",
                            "Fecha": formatted_date,
                            "Descripción": d_clean
                        })
        else:
            st.error("No se pudo detectar la Fecha de Corte en el PDF subido.")

    # ------------------------------------------
    # 2. PARSEAR CSV DE ODOO
    # ------------------------------------------
    elif file_type == "csv":
        try:
            df_in = pd.read_csv(uploaded_file)
            required_cols = ["Referencia de la orden", "Fecha de entrega", "Cliente", "Total", "Referencia del cliente"]
            missing_cols = [col for col in required_cols if col not in df_in.columns]

            if not missing_cols:
                st.success("📊 **CSV de Odoo Detectado Correctamente**")
                encabezado_contexto = "Hola Moneda, registra los siguientes ingresos correspondientes a mis ventas de Odoo:\n\n"

                for index, row in df_in.iterrows():
                    raw_date = str(row["Fecha de entrega"])
                    try:
                        formatted_date = pd.to_datetime(raw_date).strftime('%Y-%m-%d')
                    except:
                        formatted_date = raw_date

                    monto_raw = str(row["Total"]).replace('$', '').replace(',', '').strip()
                    try:
                        monto_val = float(monto_raw)
                    except:
                        monto_val = 0.0

                    cliente = str(row["Cliente"]).strip() if pd.notna(row["Cliente"]) else ""
                    ref_orden = str(row["Referencia de la orden"]).strip() if pd.notna(row["Referencia de la orden"]) else ""
                    ref_cliente = str(row["Referencia del cliente"]).strip() if pd.notna(row["Referencia del cliente"]) else ""

                    partes_desc = [p for p in [cliente, ref_orden, ref_cliente] if p]
                    desc_completa = " - ".join(partes_desc)

                    data_rows.append({
                        "Tipo": "Ingreso",
                        "Monto": monto_val,
                        "Categoría": "Ventas",
                        "Método de Pago": "Efectivo",
                        "Fecha": formatted_date,
                        "Descripción": desc_completa
                    })
            else:
                st.error(f"Faltan columnas requeridas en el CSV: {', '.join(missing_cols)}")
        except Exception as e:
            st.error(f"Error leyendo el archivo CSV: {e}")

    # ------------------------------------------
    # 3. TABLA EDITABLE Y RESULTADOS CON BOTÓN DE COPIAR
    # ------------------------------------------
    if data_rows:
        df_editor = pd.DataFrame(data_rows)

        st.subheader("✏️ Revisa y Modifica los Registros")
        st.caption("Puedes cambiar la Categoría o el Método de Pago seleccionando de la lista desplegable:")

        edited_df = st.data_editor(
            df_editor,
            column_config={
                "Categoría": st.column_config.SelectboxColumn(
                    "Categoría",
                    options=LISTA_CATEGORIAS,
                    required=True,
                ),
                "Método de Pago": st.column_config.SelectboxColumn(
                    "Método de Pago",
                    options=LISTA_METODOS_PAGO,
                    required=True,
                ),
                "Monto": st.column_config.NumberColumn(
                    "Monto ($)",
                    format="$%.2f"
                )
            },
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True
        )

        gastos_moneda = []
        gastos_sheets = []

        for _, row in edited_df.iterrows():
            m_val = f"{row['Monto']:.2f}"
            
            # Moneda.pro (comas)
            line_mon = f"{row['Tipo']}, ${m_val}, {row['Categoría']}, {row['Método de Pago']}, {row['Fecha']}, {row['Descripción']}"
            gastos_moneda.append(line_mon)

            # Sheets (tabulaciones)
            line_sh = f"{row['Tipo']}\t{m_val}\t{row['Categoría']}\t{row['Método de Pago']}\t{row['Fecha']}\t{row['Descripción']}"
            gastos_sheets.append(line_sh)

        st.divider()

        # Pestañas de salida con botón de copia integrado
        tab1, tab2 = st.tabs(["📲 Para Moneda.pro (WhatsApp)", "📊 Para Google Sheets"])

        with tab1:
            st.caption("📋 Haz clic en el **ícono de copiar** en la esquina superior derecha del recuadro:")
            mensaje_moneda = encabezado_contexto + "\n".join(gastos_moneda)
            st.code(mensaje_moneda, language="text")

        with tab2:
            st.caption("📋 Haz clic en el **ícono de copiar** en la esquina superior derecha del recuadro:")
            header_sheets = "Tipo\tMonto\tCategoría\tMétodo de Pago\tFecha\tDescripción\n"
            mensaje_sheets = header_sheets + "\n".join(gastos_sheets)
            st.code(mensaje_sheets, language="text")
