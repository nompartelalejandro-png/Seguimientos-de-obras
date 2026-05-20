import streamlit as st
import pandas as pd
from datetime import date
import os

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

st.set_page_config(
    page_title="Sistema Inteligente de Seguimiento de Obra",
    page_icon="🏗️",
    layout="wide"
)

# =========================================================
# ESTILOS
# =========================================================

st.markdown("""
<style>

.main {
    background-color: #f4f6f9;
}

h1, h2, h3 {
    color: #1a4a7a;
}

.stButton>button {
    width: 100%;
    border-radius: 8px;
    height: 3em;
    background-color: #1a4a7a;
    color: white;
    font-weight: bold;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# LOGO
# =========================================================

if os.path.exists("logo.png"):
    st.image("logo.png", width=220)

st.title("🏗️ Sistema Inteligente de Seguimiento de Obra")

st.markdown("""
Aplicación desarrollada con Python + Streamlit + IA para centralizar automáticamente
los reportes enviados por trabajadores y generar un único Excel global de seguimiento.
""")

# =========================================================
# ARCHIVO GLOBAL
# =========================================================

ARCHIVO_GLOBAL = "seguimiento_global_obra.xlsx"

# =========================================================
# CARGA DATOS EXISTENTES
# =========================================================

if os.path.exists(ARCHIVO_GLOBAL):
    df_global = pd.read_excel(ARCHIVO_GLOBAL)
else:
    df_global = pd.DataFrame(columns=[
        "Fecha",
        "Trabajador",
        "Tarea",
        "Estado",
        "Porcentaje",
        "Observaciones",
        "Archivo_Origen"
    ])

# =========================================================
# SUBIDA DE ARCHIVOS EXCEL
# =========================================================

st.divider()

st.header("📂 Subir archivos Excel de trabajadores")

st.info("""
Puedes subir uno o varios archivos Excel enviados por los trabajadores.
La aplicación unificará automáticamente toda la información.
""")

archivos_subidos = st.file_uploader(
    "Selecciona archivos Excel",
    type=["xlsx"],
    accept_multiple_files=True
)

if archivos_subidos:

    lista_dataframes = []

    for archivo in archivos_subidos:

        try:

            df_temp = pd.read_excel(archivo)

            # Añadir nombre archivo
            df_temp["Archivo_Origen"] = archivo.name

            lista_dataframes.append(df_temp)

        except Exception as e:
            st.error(f"❌ Error leyendo {archivo.name}: {e}")

    if lista_dataframes:

        df_unificado = pd.concat(
            lista_dataframes,
            ignore_index=True
        )

        # Unir con datos existentes
        df_global = pd.concat(
            [df_global, df_unificado],
            ignore_index=True
        )

        # Eliminar duplicados
        df_global = df_global.drop_duplicates()

        # Guardar automáticamente
        df_global.to_excel(
            ARCHIVO_GLOBAL,
            index=False
        )

        st.success("✅ Archivos unificados correctamente")

# =========================================================
# LISTADO TAREAS
# =========================================================

tareas = [
    "Trazado y marcado de cajas, tubos y cuadros",
    "Ejecución rozas en paredes y techos",
    "Montaje de soportes",
    "Colocación tubos y conductos",
    "Tendido de cables",
    "Identificación y etiquetado",
    "Conexionado de cables",
    "Instalación de mecanismos",
    "Montaje cuadro eléctrico",
    "Cableado interno del cuadro",
    "Configuración domótica",
    "Conexionado sensores y actuadores",
    "Pruebas de continuidad",
    "Pruebas de aislamiento",
    "Verificación de tierras",
    "Programación automatismos",
    "Pruebas de funcionamiento"
]

# =========================================================
# ESTADOS
# =========================================================

estados = {
    "25%": 25,
    "50%": 50,
    "75%": 75,
    "Finalizado": 100,
    "Finalizado con errores": 90,
    "Corregido y finalizado": 100
}

# =========================================================
# FORMULARIO MANUAL
# =========================================================

st.divider()

st.header("➕ Registrar avance manual")

with st.form("registro_manual"):

    col1, col2 = st.columns(2)

    with col1:
        trabajador = st.text_input("👷 Trabajador")

    with col2:
        fecha = st.date_input(
            "📅 Fecha",
            date.today()
        )

    tarea = st.selectbox(
        "📌 Selecciona la tarea",
        tareas
    )

    estado = st.selectbox(
        "📈 Estado",
        list(estados.keys())
    )

    observaciones = st.text_area(
        "📝 Observaciones"
    )

    guardar = st.form_submit_button(
        "Guardar Registro"
    )

if guardar:

    if trabajador.strip() == "":
        st.warning("⚠️ Debes introducir el nombre del trabajador")

    else:

        nuevo_registro = {
            "Fecha": fecha.strftime("%d/%m/%Y"),
            "Trabajador": trabajador,
            "Tarea": tarea,
            "Estado": estado,
            "Porcentaje": estados[estado],
            "Observaciones": observaciones,
            "Archivo_Origen": "Registro Manual"
        }

        df_global = pd.concat(
            [df_global, pd.DataFrame([nuevo_registro])],
            ignore_index=True
        )

        # Guardar automáticamente
        df_global.to_excel(
            ARCHIVO_GLOBAL,
            index=False
        )

        st.success("✅ Registro guardado correctamente")

# =========================================================
# DASHBOARD
# =========================================================

st.divider()

st.header("📊 Dashboard Global de la Obra")

if not df_global.empty:

    total_registros = len(df_global)

    trabajadores_activos = df_global["Trabajador"].nunique()

    avance_medio = round(
        df_global["Porcentaje"].mean(),
        2
    )

    tareas_finalizadas = len(
        df_global[df_global["Porcentaje"] >= 100]
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "📋 Registros Totales",
        total_registros
    )

    col2.metric(
        "👷 Trabajadores",
        trabajadores_activos
    )

    col3.metric(
        "📈 Avance Medio",
        f"{avance_medio}%"
    )

    col4.metric(
        "✅ Finalizadas",
        tareas_finalizadas
    )

# =========================================================
# FILTROS
# =========================================================

st.divider()

st.header("🔍 Filtrar Información")

if not df_global.empty:

    col1, col2 = st.columns(2)

    with col1:

        trabajadores_lista = sorted(
            df_global["Trabajador"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        filtro_trabajador = st.selectbox(
            "Filtrar por trabajador",
            ["Todos"] + trabajadores_lista
        )

    with col2:

        filtro_estado = st.selectbox(
            "Filtrar por estado",
            ["Todos"] + list(estados.keys())
        )

    df_filtrado = df_global.copy()

    if filtro_trabajador != "Todos":

        df_filtrado = df_filtrado[
            df_filtrado["Trabajador"] == filtro_trabajador
        ]

    if filtro_estado != "Todos":

        df_filtrado = df_filtrado[
            df_filtrado["Estado"] == filtro_estado
        ]

else:

    df_filtrado = df_global.copy()

# =========================================================
# TABLA PRINCIPAL
# =========================================================

st.divider()

st.header("📑 Registros Unificados")

st.dataframe(
    df_filtrado,
    use_container_width=True,
    height=500
)

# =========================================================
# GRÁFICOS
# =========================================================

st.divider()

st.header("📊 Visualización del Estado de la Obra")

if not df_global.empty:

    st.subheader("Estado de tareas")

    grafico_estado = df_global["Estado"].value_counts()

    st.bar_chart(grafico_estado)

    st.subheader("Registros por trabajador")

    grafico_trabajadores = (
        df_global["Trabajador"]
        .value_counts()
    )

    st.bar_chart(grafico_trabajadores)

# =========================================================
# EXPORTACIÓN FINAL
# =========================================================

st.divider()

st.header("📥 Descargar Informe Global")

if os.path.exists(ARCHIVO_GLOBAL):

    with open(ARCHIVO_GLOBAL, "rb") as f:

        st.download_button(
            label="📥 Descargar Excel Global Unificado",
            data=f,
            file_name=ARCHIVO_GLOBAL,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =========================================================
# INFORMACIÓN FINAL
# =========================================================

st.divider()

st.success("""
Sistema de unificación automática de partes de obra desarrollado con IA.
""")

st.caption("""
Aplicación desarrollada con Streamlit + Python + Pandas para la automatización
de reportes y seguimiento técnico de obra.
""")
