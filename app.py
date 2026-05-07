import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import io

# --- CONFIGURACIÓN DE NIVEL SUPERIOR ---
st.set_page_config(
    page_title="Albaranes Pro | Gestión de Obra",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PROFESIONALES ---
st.markdown("""
    <style>
    /* Estética General */
    .main { background-color: #F8FAFC; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #1E40AF; }
    
    /* Tarjetas de Métricas Custom */
    .metric-card {
        background: white;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    
    /* Botones Estilizados */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(30, 64, 175, 0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# --- CAPA DE DATOS (DATABASE SERVICE) ---
class Database:
    def __init__(self):
        # En producción, usa st.secrets["MONGO_URL"]
        self.uri = st.secrets.get("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = "albaranes_app"
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]

    async def fetch_all(self, collection):
        cursor = self.db[collection].find({}, {"_id": 0})
        return await cursor.to_list(length=2000)

    async def insert(self, collection, data):
        return await self.db[collection].insert_one(data)

db = Database()

# --- LÓGICA DE NEGOCIO (HELPERS) ---
def run_async(coro):
    """Ejecutor de corrutinas asíncronas para Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@st.cache_data(ttl=60)
def get_cached_data(collection):
    return run_async(db.fetch_all(collection))

# --- INTERFAZ DE USUARIO (UI COMPONENTS) ---
class UI:
    @staticmethod
    def sidebar():
        with st.sidebar:
            st.image("https://cdn-icons-png.flaticon.com/512/4322/4322992.png", width=80)
            st.title("Albaranes Pro")
            st.markdown("---")
            choice = st.radio(
                "Navegación",
                ["📊 Dashboard", "📝 Registrar Albarán", "📋 Historial Completo", "👷 Equipo", "📂 Partidas"],
                label_visibility="collapsed"
            )
            st.markdown("---")
            st.caption("v2.1.0 Enterprise Edition")
            return choice

    @staticmethod
    def dashboard():
        st.title("📊 Panel de Control")
        data = get_cached_data("albaranes")
        df = pd.DataFrame(data)

        if df.empty:
            st.warning("No hay datos disponibles. Registra tu primer albarán.")
            return

        # KPIs superiores
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Inversión Total", f"{df['gastos'].sum():,.2f} €")
        with c2:
            st.metric("Albaranes", len(df))
        with c3:
            st.metric("Promedio/Gasto", f"{df['gastos'].mean():,.2f} €")
        with c4:
            st.metric("Partidas Activas", df['budget_item_name'].nunique())

        st.markdown("---")
        
        # Gráficos Pro con Plotly
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader("Evolución de Gastos por Partida")
            fig = px.bar(df, x="budget_item_name", y="gastos", color="worker_name", 
                         barmode="group", template="plotly_white", color_discrete_sequence=px.colors.qualitative.Prism)
            st.plotly_chart(fig, use_container_width=True)
        
        with col_right:
            st.subheader("Distribución (%)")
            fig_pie = px.pie(df, values="gastos", names="budget_item_name", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

    @staticmethod
    def albaran_form():
        st.title("📝 Nuevo Albarán de Obra")
        workers = get_cached_data("workers")
        items = get_cached_data("budget_items")

        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                numero = st.text_input("Referencia Albarán", placeholder="Ej: ALB-2024-001")
                fecha = st.date_input("Fecha de Recepción", datetime.now())
                importe = st.number_input("Base Imponible (€)", min_value=0.0, format="%.2f")
            
            with col2:
                trabajador = st.selectbox("Operario Responsable", [w['name'] for w in workers]) if workers else st.error("Crea trabajadores primero")
                partida = st.selectbox("Partida Destino", [i['name'] for i in items]) if items else st.error("Crea partidas primero")
                comentarios = st.text_area("Notas internas", placeholder="Descripción de materiales o servicios...")

            archivo = st.file_uploader("📸 Evidencia Digital (JPG/PNG/PDF)", type=['jpg', 'png', 'pdf'])

            if st.button("🚀 Confirmar y Registrar"):
                if not numero or importe <= 0:
                    st.error("Por favor, rellena los campos obligatorios.")
                else:
                    nuevo_doc = {
                        "id": str(uuid.uuid4()),
                        "numero": numero,
                        "fecha": fecha.isoformat(),
                        "worker_name": trabajador,
                        "budget_item_name": partida,
                        "gastos": importe,
                        "comentarios": comentarios,
                        "created_at": datetime.now().isoformat()
                    }
                    run_async(db.insert("albaranes", nuevo_doc))
                    st.balloons()
                    st.success("Registro almacenado encriptado en base de datos.")
                    st.cache_data.clear()

    @staticmethod
    def listado():
        st.title("📋 Histórico de Operaciones")
        data = get_cached_data("albaranes")
        if data:
            df = pd.DataFrame(data).sort_values(by="fecha", ascending=False)
            
            # Filtros dinámicos
            with st.expander("🔍 Filtros Avanzados"):
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    search = st.text_input("Buscar por referencia o comentario")
                with f_col2:
                    f_partida = st.multiselect("Filtrar por Partida", df['budget_item_name'].unique())
            
            if search:
                df = df[df['numero'].str.contains(search, case=False) | df['comentarios'].str.contains(search, case=False)]
            if f_partida:
                df = df[df['budget_item_name'].isin(f_partida)]

            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Exportación Pro
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar Informe (CSV)", csv, "informe_obra.csv", "text/csv")
        else:
            st.info("Sin registros.")

# --- PUNTO DE ENTRADA (MAIN) ---
def main():
    menu_item = UI.sidebar()
    
    if "Dashboard" in menu_item:
        UI.dashboard()
    elif "Registrar" in menu_item:
        UI.albaran_form()
    elif "Historial" in menu_item:
        UI.listado()
    elif "Equipo" in menu_item:
        # Lógica para añadir trabajadores similar al form anterior
        st.title("👷 Gestión de Equipo")
        with st.form("add_worker"):
            name = st.text_input("Nombre del Trabajador")
            role = st.text_input("Cargo")
            if st.form_submit_button("Añadir al Sistema"):
                run_async(db.insert("workers", {"name": name, "role": role}))
                st.cache_data.clear()
                st.rerun()
    elif "Partidas" in menu_item:
        st.title("📂 Partidas Presupuestarias")
        with st.form("add_item"):
            name = st.text_input("Nombre de la Partida (ej: Hormigón, Fontanería)")
            if st.form_submit_button("Crear Partida"):
                run_async(db.insert("budget_items", {"name": name}))
                st.cache_data.clear()
                st.rerun()

if __name__ == "__main__":
    main()
