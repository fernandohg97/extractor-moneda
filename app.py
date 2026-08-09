import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from pypdf import PdfReader
from io import BytesIO
import requests
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
from pdf_generator import generar_pdf_reporte

st.set_page_config(page_title="Finanzas Dayana", layout="wide")

API_KEY = st.secrets["google_picker"].get("api_key", "")
CLIENT_ID = st.secrets["google_picker"].get("client_id", "")

conn = st.connection("gsheets", type=GSheetsConnection)

# LISTAS PREDEFINIDAS PARA LOS MENÚS DESPLEGABLES DE LA TABLA EDITABLE
LISTA_CATEGORIAS = [
    "Produccion Dayana",
    "Pago de Tarjeta",
    "Carro/Transporte",
    "Restaurantes y Comida",
    "Casa y Despensa",
    "Cafe",
    "Ocio",
    "Nomina",
    "Inversiones",
    "Ahorro",
    "Prestamo/Financiamiento",
    "Gastos Operativos",
    "Gasolina",
    "Papeleria",
    "Inversion Dayana",
    "Detalles/Regalos",
    "Uso Personal",
    "Ventas",
    "No informado"
]

LISTA_METODOS_PAGO = [
    "NU (CREDITO)",
    "NU (Transferencia)",
    "Efectivo",
    "No informado",
    "Banamex Priority",
    "TDC Oro Banamex",
    "TDC Mercado Pago",
    "Medio Electronico",
]

def cargar_datos():
    try:
        df = conn.read(worksheet="Movimientos", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion'])
        
        df.columns = df.columns.str.strip().str.replace('Categoría', 'Categoria').str.replace('Método_Pago', 'Metodo_Pago')
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce').dt.date
        df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        df = df.dropna(subset=['Fecha'])
        return df
    except Exception:
        return pd.DataFrame(columns=['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion'])

df_base = cargar_datos()

def categorizar_nu(descripcion):
    desc_lower = str(descripcion).lower()
    keywords_dayana = ["mayorista", "teip", "guga", "envases", "ley"]
    
    for kw in keywords_dayana:
        if kw in desc_lower:
            return "Produccion Dayana"
    return "Varios"

def procesar_pdf_nu(file_stream, file_name=""):
    reader = PdfReader(file_stream)
    texto_completo = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            texto_completo += txt + "\n"
            
    meses_dict = {
        "ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06",
        "jul": "07", "ago": "08", "sep": "09", "oct": "10", "nov": "11", "dic": "12",
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
        "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
    }

    ano_corte = str(datetime.now().year)
    match_ano = re.search(r"\b(20\d{2})\b", texto_completo)
    if not match_ano and file_name:
        match_ano = re.search(r"\b(20\d{2})\b", file_name)
    if match_ano:
        ano_corte = match_ano.group(1)

    registros = []
    lineas = texto_completo.split("\n")
    
    dentro_de_tabla = False
    
    for linea in lineas:
        l = linea.strip()
        if not l:
            continue
            
        l_upper = l.upper()
        l_lower = l.lower()
        
        if any(h in l_upper for h in ["CARGOS, ABONOS", "COMPRAS REGULARES", "FECHA DE LA OPERACIÓN", "DESCRIPCIÓN DEL MOVIMIENTO"]):
            dentro_de_tabla = True
            continue
            
        if dentro_de_tabla and any(fin in l_upper for fin in ["COMPRAS A MESES", "PLAN DE PAGOS", "ACLARACIONES", "INFORMACIÓN DE INTERESES"]):
            dentro_de_tabla = False
            break

        if dentro_de_tabla:
            if any(ignore in l_lower for ignore in [
                "total de cargos", 
                "total de abonos", 
                "total de compras", 
                "grácias por tu pago", 
                "gracias por tu pago", 
                "abono", 
                "-$"
            ]):
                continue

            match_cargo = re.search(r"\+\$\s*([\d,]+\.\d{2})", l)
            if match_cargo:
                try:
                    monto_val = float(match_cargo.group(1).replace(",", ""))
                    
                    match_fechas = re.search(r"(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?)\s+(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?)", l)
                    
                    if match_fechas:
                        fecha_cargo_raw = match_fechas.group(2).strip()
                        partes_fecha = fecha_cargo_raw.split()
                        
                        dia_cargo = partes_fecha[0].zfill(2)
                        mes_cargo_str = partes_fecha[1].lower()[:3]
                        mes_cargo = meses_dict.get(mes_cargo_str, "01")
                        
                        ano_mov = partes_fecha[2] if len(partes_fecha) > 2 else ano_corte
                        fecha_fmt = f"{ano_mov}-{mes_cargo}-{dia_cargo}"
                    else:
                        fecha_fmt = f"{ano_corte}-01-01"

                    desc = re.sub(r"^\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?\s+\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?", "", l)
                    desc = re.sub(r"\+\$\s*[\d,]+\.\d{2}", "", desc)
                    desc = re.sub(r"\|\s*RFC:.*", "", desc, flags=re.IGNORECASE).strip()
                    
                    if not desc:
                        desc = "Gasto Nu"

                    cat = categorizar_nu(desc)
                    
                    registros.append({
                        "Tipo": "Gasto",
                        "Monto": monto_val,
                        "Categoria": cat,
                        "Metodo_Pago": "NU (CREDITO)",
                        "Fecha": fecha_fmt,
                        "Descripcion": desc
                    })
                except ValueError:
                    continue

    df_res = pd.DataFrame(registros)
    if not df_res.empty:
        df_res = df_res.drop_duplicates(subset=["Monto", "Fecha", "Descripcion"])
        df_res = df_res.sort_values(by="Fecha").reset_index(drop=True)
        df_res = df_res[['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion']]
    return df_res

def procesar_csv_odoo(file_stream):
    df_odoo = pd.read_csv(file_stream)
    registros = []
    for _, row in df_odoo.iterrows():
        cliente = str(row.get("Cliente", "")).strip()
        ref_orden = str(row.get("Referencia de la orden", "")).strip()
        ref_cliente = str(row.get("Referencia del cliente", "")).strip()
        monto = float(row.get("Total", 0))
        fecha_raw = str(row.get("Fecha de entrega", row.get("Fecha de entrega", datetime.now().strftime("%Y-%m-%d"))))
        
        fecha_fmt = fecha_raw.split()[0]
        desc = f"{cliente} - {ref_orden} - {ref_cliente}".strip(" -")
        
        registros.append({
            "Tipo": "Ingreso",
            "Monto": monto,
            "Categoria": "Ventas",
            "Metodo_Pago": "Efectivo",
            "Fecha": fecha_fmt,
            "Descripcion": desc
        })
    df_res = pd.DataFrame(registros)
    if not df_res.empty:
        df_res = df_res.sort_values(by="Fecha").reset_index(drop=True)
        df_res = df_res[['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion']]
    return df_res

def render_drive_picker(mime_type, key_id):
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <script src="https://apis.google.com/js/api.js"></script>
      <script src="https://accounts.google.com/gsi/client"></script>
    </head>
    <body style="margin:0; padding:0; background:transparent;">
      <button id="pickerBtn" style="
        background-color: #2563eb; color: white; border: none; padding: 10px 18px; 
        border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 14px;
        width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;">
        📁 Abrir Explorador de Google Drive
      </button>

      <script>
        const developerKey = '{API_KEY}';
        const clientId = '{CLIENT_ID}';
        const mimeType = '{mime_type}';
        let accessToken = null;

        function tokenCallback(response) {{
          if (response.error !== undefined) {{
            throw (response);
          }}
          accessToken = response.access_token;
          createPicker();
        }}

        const tokenClient = google.accounts.oauth2.initTokenClient({{
          client_id: clientId,
          scope: 'https://www.googleapis.com/auth/drive.readonly',
          callback: tokenCallback,
        }});

        document.getElementById('pickerBtn').addEventListener('click', () => {{
          if (accessToken === null) {{
            tokenClient.requestAccessToken({{prompt: 'consent'}});
          }} else {{
            tokenClient.requestAccessToken({{prompt: ''}});
          }}
        }});

        function createPicker() {{
          gapi.load('picker', () => {{
            const view = new google.picker.View(google.picker.ViewId.DOCS);
            view.setMimeTypes(mimeType);
            const picker = new google.picker.PickerBuilder()
                .enableFeature(google.picker.Feature.NAV_HIDDEN)
                .setAppId(clientId.split('-')[0])
                .setOAuthToken(accessToken)
                .addView(view)
                .setDeveloperKey(developerKey)
                .setOrigin(window.location.protocol + '//' + window.location.host)
                .setCallback(pickerCallback)
                .build();
            picker.setVisible(true);
          }});
        }}

        function pickerCallback(data) {{
          if (data.action === google.picker.Action.PICKED) {{
            const doc = data.docs[0];
            const fileId = doc.id;
            const fileName = doc.name;
            const targetUrl = window.parent.location.pathname + '?drive_file_id=' + fileId + '&auth_token=' + accessToken + '&file_name=' + encodeURIComponent(fileName);
            window.parent.location.href = targetUrl;
          }}
        }}
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=55)

st.sidebar.title("📌 Navegación")
pagina = st.sidebar.radio("Ir a:", ["📊 Dashboard Financiero", "📄 Extractor Nu / Odoo"])

# ==========================================
# PÁGINA 1: DASHBOARD FINANCIERO
# ==========================================
if pagina == "📊 Dashboard Financiero":
    st.title("Analiza tus finanzas con reportes detallados")
    st.caption("Visualiza todas tus transacciones organizadas por fecha, categoría y tipo")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        atajo = st.selectbox("Atajo de Período", ["Personalizado", "Hoy", "Esta semana", "Este mes", "Últimos 3 meses"])
        hoy = datetime.now().date()
        if atajo == "Hoy":
            f_ini, f_fin = hoy, hoy
        elif atajo == "Esta semana":
            f_ini = hoy - timedelta(days=hoy.weekday())
            f_fin = f_ini + timedelta(days=6)
        elif atajo == "Este mes":
            f_ini = hoy.replace(day=1)
            f_fin = hoy
        elif atajo == "Últimos 3 meses":
            f_ini = hoy - timedelta(days=90)
            f_fin = hoy
        else:
            f_ini = hoy.replace(day=1)
            f_fin = hoy

    with col_f2:
        f_inicio = st.date_input("Fecha Inicio", value=f_ini)
        f_final = st.date_input("Fecha Fin", value=f_fin)

    with col_f3:
        filtro_tipo = st.selectbox("Tipo de Registro", ["TODOS", "Ingreso", "Gasto"])

    categorias_opts = ["TODAS"] + sorted(list(df_base['Categoria'].dropna().unique())) if not df_base.empty else ["TODAS"]
    with col_f4:
        filtro_cat = st.selectbox("Categoría", categorias_opts)

    df_filtrado = df_base.copy()
    if not df_filtrado.empty:
        df_filtrado = df_filtrado[(df_filtrado['Fecha'] >= f_inicio) & (df_filtrado['Fecha'] <= f_final)]
        if filtro_tipo != "TODOS":
            df_filtrado = df_filtrado[df_filtrado['Tipo'] == filtro_tipo]
        if filtro_cat != "TODAS":
            df_filtrado = df_filtrado[df_filtrado['Categoria'] == filtro_cat]

    # CÁLCULO DE INDICADORES Y PORCENTAJE
    ingresos = df_filtrado[df_filtrado['Tipo'] == 'Ingreso']['Monto'].sum() if not df_filtrado.empty else 0.0
    egresos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']['Monto'].sum() if not df_filtrado.empty else 0.0
    balance = ingresos - egresos
    porcentaje_balance = (balance / ingresos * 100) if ingresos > 0 else 0.0

    col_exp1, col_exp2 = st.columns(2)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with col_exp1:
        csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar CSV", data=csv_data, file_name=f"reporte_{f_inicio}_a_{f_final}_{timestamp}.csv", mime="text/csv", use_container_width=True)

    with col_exp2:
        if not df_filtrado.empty:
            pdf_bytes = generar_pdf_reporte(df_filtrado, f_inicio, f_final, ingresos, egresos, balance, porcentaje_balance)
            st.download_button("📄 Exportar PDF", data=pdf_bytes, file_name=f"reporte_{f_inicio}_a_{f_final}_{timestamp}.pdf", mime="application/pdf", use_container_width=True)

    st.markdown("---")

    # SCORECARDS CON EL NUEVO PORCENTAJE DISCRETO
    c_ing, c_egr, c_bal = st.columns(3)
    c_ing.metric("TOTAL DE INGRESOS", f"${ingresos:,.2f}")
    c_egr.metric("TOTAL DE EGRESOS", f"-${egresos:,.2f}")
    
    with c_bal:
        st.metric("BALANCE DEL PERÍODO", f"${balance:,.2f}")
        if ingresos > 0:
            st.caption(f"_{porcentaje_balance:.2f}% de los ingresos_")
        else:
            st.caption("_0.00% de los ingresos_")

    st.markdown(f"### Lista de Transacciones ({len(df_filtrado)} registros)")
    st.dataframe(df_filtrado, use_container_width=True)

# ==========================================
# PÁGINA 2: EXTRACTOR NU / ODOO
# ==========================================
else:
    st.title("Extracción y Registro de Gastos e Ingresos")
    st.caption("Importa archivos desde Google Drive o tu almacenamiento local para procesar movimientos.")

    query_params = st.query_params
    if "drive_file_id" in query_params and "auth_token" in query_params:
        file_id = query_params["drive_file_id"]
        token = query_params["auth_token"]
        file_name = query_params.get("file_name", "Archivo de Drive")
        
        st.info(f"📥 Cargando desde Google Drive: **{file_name}**")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media", headers=headers)
            
            if response.status_code == 200:
                file_bytes = BytesIO(response.content)
                
                if file_name.lower().endswith(".pdf"):
                    df_extracted = procesar_pdf_nu(file_bytes, file_name)
                else:
                    df_extracted = procesar_csv_odoo(file_bytes)

                if not df_extracted.empty:
                    primer_reg = df_extracted['Fecha'].iloc[0]
                    ultimo_reg = df_extracted['Fecha'].iloc[-1]
                    st.success(f"✅ Se extrajeron **{len(df_extracted)} registros**. Período detectado: del **{primer_reg}** al **{ultimo_reg}**.")
                    
                    df_edited = st.data_editor(
                        df_extracted, 
                        num_rows="dynamic", 
                        use_container_width=True,
                        column_config={
                            "Categoria": st.column_config.SelectboxColumn("Categoría", options=LISTA_CATEGORIAS, required=True),
                            "Metodo_Pago": st.column_config.SelectboxColumn("Método de Pago", options=LISTA_METODOS_PAGO, required=True)
                        }
                    )
                    
                    tsv_data = df_edited.to_csv(index=False, sep='\t', header=False)
                    st.markdown("#### Formato TSV para copiar y pegar en Google Sheets:")
                    st.code(tsv_data, language="text")
                    
                    if st.button("🚀 Guardar estos registros en Google Sheets"):
                        df_total = pd.concat([df_base, df_edited], ignore_index=True)
                        conn.update(worksheet="Movimientos", data=df_total)
                        st.success("¡Base de datos actualizada correctamente!")
                        st.query_params.clear()
                        st.rerun()
            else:
                st.error("No se pudo descargar el archivo de Google Drive. Inténtalo de nuevo.")
        except Exception as ex:
            st.error(f"Error procesando el archivo de Drive: {ex}")
            
        if st.button("Limpiar selección de Drive"):
            st.query_params.clear()
            st.rerun()
        st.markdown("---")

    tab1, tab2 = st.tabs(["💳 Estado de Cuenta Nu (PDF)", "🛍️ Ventas Odoo (CSV)"])
    
    with tab1:
        st.subheader("Importar Estado de Cuenta Nu")
        col_drive, col_local = st.columns(2)
        
        with col_drive:
            st.markdown("**Opción A: Desde Google Drive**")
            render_drive_picker("application/pdf", "nu_picker")
            
        with col_local:
            st.markdown("**Opción B: Desde dispositivo Local / Móvil**")
            pdf_file = st.file_uploader("Subir PDF local", type=["pdf"], key="pdf_nu_local")

        st.markdown("---")

        if pdf_file is not None:
            try:
                df_extracted_nu = procesar_pdf_nu(pdf_file, pdf_file.name)
                if not df_extracted_nu.empty:
                    primer_reg = df_extracted_nu['Fecha'].iloc[0]
                    ultimo_reg = df_extracted_nu['Fecha'].iloc[-1]
                    
                    st.success(f"✅ Se extrajeron **{len(df_extracted_nu)} egresos**. Primer registro: **{primer_reg}** | Último registro: **{ultimo_reg}**.")
                    
                    df_edited_nu = st.data_editor(
                        df_extracted_nu, 
                        num_rows="dynamic", 
                        use_container_width=True, 
                        key="editor_nu_local",
                        column_config={
                            "Categoria": st.column_config.SelectboxColumn("Categoría", options=LISTA_CATEGORIAS, required=True),
                            "Metodo_Pago": st.column_config.SelectboxColumn("Método de Pago", options=LISTA_METODOS_PAGO, required=True)
                        }
                    )
                    
                    tsv_data_nu = df_edited_nu.to_csv(index=False, sep='\t', header=False)
                    st.markdown("#### Formato TSV para copiar y pegar en la pestaña Movimientos:")
                    st.code(tsv_data_nu, language="text")
                    
                    if st.button("🚀 Guardar directamente en Google Sheets", key="btn_nu_local"):
                        df_total = pd.concat([df_base, df_edited_nu], ignore_index=True)
                        conn.update(worksheet="Movimientos", data=df_total)
                        st.success("¡Egresos guardados con éxito en Google Sheets!")
                        st.rerun()
                else:
                    st.error("No se detectaron transacciones de egreso en el PDF subido.")
            except Exception as e:
                st.error(f"Error procesando el PDF local: {e}")

    with tab2:
        st.subheader("Importar Ventas Odoo")
        col_drive_csv, col_local_csv = st.columns(2)
        
        with col_drive_csv:
            st.markdown("**Opción A: Desde Google Drive**")
            render_drive_picker("text/csv", "odoo_picker")
            
        with col_local_csv:
            st.markdown("**Opción B: Desde dispositivo Local / Móvil**")
            csv_file = st.file_uploader("Subir CSV local", type=["csv"], key="csv_odoo_local")

        st.markdown("---")

        if csv_file is not None:
            try:
                df_extracted_odoo = procesar_csv_odoo(csv_file)
                if not df_extracted_odoo.empty:
                    primer_reg = df_extracted_odoo['Fecha'].iloc[0]
                    ultimo_reg = df_extracted_odoo['Fecha'].iloc[-1]
                    st.success(f"✅ Se extrajeron **{len(df_extracted_odoo)} ventas**. Primer registro: **{primer_reg}** | Último registro: **{ultimo_reg}**.")
                    
                    df_edited_odoo = st.data_editor(
                        df_extracted_odoo, 
                        num_rows="dynamic", 
                        use_container_width=True, 
                        key="editor_odoo_local",
                        column_config={
                            "Categoria": st.column_config.SelectboxColumn("Categoría", options=LISTA_CATEGORIAS, required=True),
                            "Metodo_Pago": st.column_config.SelectboxColumn("Método de Pago", options=LISTA_METODOS_PAGO, required=True)
                        }
                    )
                    
                    tsv_data_odoo = df_edited_odoo.to_csv(index=False, sep='\t', header=False)
                    st.markdown("#### Formato TSV para copiar y pegar en la pestaña Movimientos:")
                    st.code(tsv_data_odoo, language="text")
                    
                    if st.button("🚀 Guardar directamente en Google Sheets", key="btn_odoo_local"):
                        df_total = pd.concat([df_base, df_edited_odoo], ignore_index=True)
                        conn.update(worksheet="Movimientos", data=df_total)
                        st.success("¡Ventas guardadas con éxito en Google Sheets!")
                        st.rerun()
                else:
                    st.error("No se detectaron transacciones de ventas en el CSV.")
            except Exception as e:
                st.error(f"Error procesando el CSV local: {e}")
