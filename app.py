# app.py

import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.features import GeoJsonTooltip
from streamlit_folium import st_folium

# Regenera el .shx si falta
os.environ["SHAPE_RESTORE_SHX"] = "YES"

# Configuración general
st.set_page_config(
    page_title="Indicadores VIH - Unidad 5",
    layout="wide",
    initial_sidebar_state="expanded"
)

def parse_val(x):
    """Convierte sufijos k (miles), m (millones), b (miles de millones)."""
    if pd.isna(x):
        return None
    s = str(x).strip().lower()
    try:
        if s.endswith("k"):
            return float(s[:-1]) * 1e3
        if s.endswith("m"):
            return float(s[:-1]) * 1e6
        if s.endswith("b"):
            return float(s[:-1]) * 1e9
        return float(s)
    except ValueError:
        return None  # en caso de otro formato inesperado

@st.cache_data
def cargar_csv(path_csv: str) -> pd.DataFrame:
    df = pd.read_csv(path_csv)
    for col in df.columns[1:]:
        df[col] = df[col].apply(parse_val)
    df.set_index("country", inplace=True)
    return df

@st.cache_data
def cargar_shapefile(path_shp: str = "ne_110m_admin_0_countries.shp") -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path_shp)
    return gdf.rename(columns={"ADMIN": "country"})[["country", "geometry"]]

# Carga de datasets
df_deaths = cargar_csv("annual_hiv_deaths_number_all_ages.csv")
df_new    = cargar_csv("newly_hiv_infected_number_all_ages.csv")
df_plwh   = cargar_csv("people_living_with_hiv_number_all_ages.csv")
gdf       = cargar_shapefile()

# Diccionario de indicadores
indicadores = {
    "Muertes por VIH": df_deaths,
    "Nuevas infecciones VIH": df_new,
    "Personas viviendo con VIH": df_plwh
}

# Rango de años (se asume idéntico en los 3 CSV)
años = [int(y) for y in df_deaths.columns]
min_año, max_año = min(años), max(años)

# Sidebar
st.sidebar.title("🔍 Navegación")
pagina  = st.sidebar.radio("", ["Gráficas", "Mapa"])
indi_sel = st.sidebar.selectbox("Selecciona indicador", list(indicadores.keys()))
df_sel   = indicadores[indi_sel]

if pagina == "Gráficas":
    st.markdown(f"## 📈 {indi_sel}")
    st.markdown("Explora la serie histórica, compara países y filtra por año.")
    st.markdown("---")

    # Métricas globales
    serie_global = df_sel.sum(axis=0).fillna(0)
    latest_year  = max_año
    total_latest = serie_global[str(latest_year)]
    year_max     = int(serie_global.astype(float).idxmax())
    year_min     = int(serie_global.astype(float).idxmin())

    col1, col2, col3 = st.columns(3)
    col1.metric("Año con más valor", year_max, f"{int(serie_global[str(year_max)]):,}")
    col2.metric("Año con menos valor", year_min, f"{int(serie_global[str(year_min)]):,}")
    col3.metric(f"Valor en {latest_year}", f"{int(total_latest):,}")

    st.markdown("---")

    # Tres pestañas de gráfico
    tab1, tab2, tab3 = st.tabs(["Tendencia Global", "Top 10 Países", "Evolución por País"])

    with tab1:
        st.subheader("Tendencia Global")
        df_plot = pd.DataFrame(serie_global.astype(int), columns=[indi_sel])
        st.line_chart(df_plot, use_container_width=True)

    with tab2:
        st.subheader("Top 10 Países")
        año_top = st.slider("Selecciona año", min_año, max_año, min_año, key="slider_top10")
        top10   = df_sel[str(año_top)].fillna(0).sort_values(ascending=False).head(10).astype(int)
        st.bar_chart(top10, use_container_width=True)

    with tab3:
        st.subheader("Evolución por País")
        opciones    = df_sel.index.tolist()
        paises_sel = st.multiselect("Elige países", opciones, default=opciones[:3], key="multiselect_evo")
        if paises_sel:
            evo          = df_sel.loc[paises_sel].T.fillna(0).astype(int)
            evo.index    = evo.index.astype(int)
            st.line_chart(evo, use_container_width=True)
        else:
            st.info("Selecciona al menos un país.")

elif pagina == "Mapa":
    st.markdown(f"## 🗺️ Mapa de {indi_sel}")
    st.markdown("Mapa coroplético interactivo. Selecciona año y haz clic en un país.")
    st.markdown("---")

    año_map = st.sidebar.slider("Año para el mapa", min_año, max_año, min_año, key="slider_mapa")

    # Unión con shapefile
    gdf_map = gdf.merge(
        df_sel[[str(año_map)]].reset_index(),
        on="country", how="left"
    )

    m = folium.Map(location=[20,0], zoom_start=2, tiles="CartoDB positron")
    folium.Choropleth(
        geo_data=gdf_map.__geo_interface__,
        data=gdf_map,
        columns=["country", str(año_map)],
        key_on="feature.properties.country",
        fill_color="YlOrRd",
        nan_fill_color="lightgray",
        legend_name=f"{indi_sel} ({año_map})"
    ).add_to(m)
    folium.GeoJson(
        gdf_map.__geo_interface__,
        style_function=lambda f: {"fillOpacity":0, "weight":0},
        tooltip=GeoJsonTooltip(
            fields=["country", str(año_map)],
            aliases=["País", indi_sel],
            localize=True
        )
    ).add_to(m)

    st_data = st_folium(m, width=800, height=500)
    click   = st_data.get("last_object_clicked")

    if click:
        # Extraer propiedades
        props = click.get("properties") or click.get("feature", {}).get("properties", {})
        country = props.get("country")
        valor   = props.get(str(año_map))
        if country:
            st.write(f"**{country}**: {int(valor) if pd.notna(valor) else 'Sin datos'}")
        else:
            latlng = click.get("latlng", {})
            if latlng.get("lat") is not None:
                st.write(f"Coordenadas: {latlng['lat']:.4f}, {latlng['lng']:.4f}")
            else:
                st.info("Haz clic en un país para ver sus datos.")
