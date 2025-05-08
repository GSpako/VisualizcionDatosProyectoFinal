# app.py

import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.features import GeoJsonTooltip
from folium.plugins import MeasureControl, Fullscreen
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
        return None

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

# Carga de datos
df_deaths = cargar_csv("annual_hiv_deaths_number_all_ages.csv")
df_new    = cargar_csv("newly_hiv_infected_number_all_ages.csv")
df_plwh   = cargar_csv("people_living_with_hiv_number_all_ages.csv")
gdf       = cargar_shapefile()

indicadores = {
    "Muertes por VIH": df_deaths,
    "Nuevas infecciones VIH": df_new,
    "Personas viviendo con VIH": df_plwh
}

# Rango de años (se asume idéntico en los tres CSVs)
años = [int(y) for y in df_deaths.columns]
min_año, max_año = min(años), max(años)

# Barra lateral
st.sidebar.title("🔍 Navegación")
pagina = st.sidebar.radio(
    "Página",
    ["Gráficas", "Mapa"],
    label_visibility="collapsed"
)
indi_sel = st.sidebar.selectbox("Selecciona indicador", list(indicadores.keys()))
df_sel   = indicadores[indi_sel]

if pagina == "Gráficas":
    st.markdown(f"## 📈 {indi_sel}")
    st.markdown("Interactúa con los widgets para explorar distintos enfoques.")
    st.markdown("---")

    # Métricas globales
    serie_global = df_sel.sum(axis=0).fillna(0)
    latest_year  = max_año
    total_latest = serie_global[str(latest_year)]
    year_max     = int(serie_global.idxmax())
    year_min     = int(serie_global.idxmin())

    c1, c2, c3 = st.columns(3)
    c1.metric("Año con más valor", year_max, f"{int(serie_global[str(year_max)]):,}")
    c2.metric("Año con menos valor", year_min, f"{int(serie_global[str(year_min)]):,}")
    c3.metric(f"Valor en {latest_year}", f"{int(total_latest):,}")

    st.markdown("---")

    # Pestañas de gráficas
    tabs = st.tabs([
        "Tendencia Global",
        "Top N Países",
        "Evolución por País",
        "Comparación Indicadores"
    ])

    # 1) Tendencia Global
    with tabs[0]:
        st.subheader("Tendencia Global")
        rango = st.slider(
            "Rango de años",
            min_value=min_año, max_value=max_año,
            value=(min_año, max_año),
            step=1,
            key="rango_global"
        )
        chart_type = st.radio(
            "Tipo de gráfico", ["Línea", "Área"], index=0, key="tipo_global"
        )
        df_plot = pd.DataFrame(
            serie_global.loc[str(rango[0]):str(rango[1])].astype(int),
            columns=[indi_sel]
        )
        if chart_type == "Línea":
            st.line_chart(df_plot, use_container_width=True, height=300)
        else:
            st.area_chart(df_plot, use_container_width=True, height=300)

    # 2) Top N Países
    with tabs[1]:
        st.subheader("Top N Países")
        año_top = st.slider(
            "Año", min_value=min_año, max_value=max_año,
            value=min_año, key="slider_top10"
        )
        n = st.number_input(
            "Número de países a mostrar",
            min_value=5, max_value=20,
            value=10, step=1, key="num_top"
        )
        topn = df_sel[str(año_top)].fillna(0).sort_values(ascending=False).head(n).astype(int)
        st.bar_chart(topn, use_container_width=True)

    # 3) Evolución por País
    with tabs[2]:
        st.subheader("Evolución por País")
        opciones = df_sel.index.tolist()
        paises = st.multiselect(
            "Países", opciones, default=opciones[:3], key="multiselect_evo"
        )
        chart_type2 = st.radio(
            "Tipo de gráfico", ["Línea", "Área"], index=0, key="tipo_evo"
        )
        if paises:
            evo = df_sel.loc[paises].T.fillna(0).astype(int)
            evo.index = evo.index.astype(int)
            if chart_type2 == "Línea":
                st.line_chart(evo, use_container_width=True)
            else:
                st.area_chart(evo, use_container_width=True)
        else:
            st.info("Selecciona al menos un país.")

    # 4) Comparación Indicadores
    with tabs[3]:
        st.subheader("Comparación de Indicadores")
        sel_inds = st.multiselect(
            "Selecciona indicadores a comparar",
            list(indicadores.keys()),
            default=list(indicadores.keys()), key="compare_inds"
        )
        comp = pd.DataFrame({
            name: indicadores[name].sum(axis=0).fillna(0).astype(int)
            for name in sel_inds
        })
        st.line_chart(comp, use_container_width=True)

elif pagina == "Mapa":
    # Mapa sin textos descriptivos ni slider de opacidad
    año_map = st.sidebar.slider(
        "Año para el mapa", min_value=min_año,
        max_value=max_año, value=min_año, key="slider_mapa"
    )
    palette = st.sidebar.selectbox(
        "Paleta de color", ["YlOrRd", "Blues", "PuRd", "Greens"], index=0
    )

    # Prepara GeoDataFrame para el año seleccionado
    gdf_map = gdf.merge(
        df_sel[[str(año_map)]].reset_index(),
        on="country", how="left"
    )

    # Crea mapa Folium centrado
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron", control_scale=True)
    folium.Choropleth(
        geo_data=gdf_map.__geo_interface__,
        data=gdf_map,
        columns=["country", str(año_map)],
        key_on="feature.properties.country",
        fill_color=palette,
        fill_opacity=0.7,
        line_opacity=0.2,
        nan_fill_color="lightgray",
        legend_name=f"{indi_sel} ({año_map})"
    ).add_to(m)

    folium.GeoJson(
        gdf_map.__geo_interface__,
        style_function=lambda f: {"fillOpacity": 0, "weight": 0},
        tooltip=GeoJsonTooltip(
            fields=["country", str(año_map)],
            aliases=["País", indi_sel],
            localize=True
        )
    ).add_to(m)

    # Controles de mapa
    MeasureControl(position="bottomleft", primary_length_unit="kilometers").add_to(m)
    Fullscreen(position="topright").add_to(m)
    folium.LayerControl().add_to(m)

    # Centrar el componente de mapa en la interfaz
    col1, col2, col3 = st.columns([1, 8, 1])
    with col2:
        st_folium(
            m,
            width=900,
            height=600,
            key=f"map_{año_map}_{palette}"
        )
