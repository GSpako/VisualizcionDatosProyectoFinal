import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
import altair as alt
from folium.features import GeoJsonTooltip
from folium.plugins import MeasureControl, Fullscreen
from streamlit_folium import st_folium

# Debe ser el primer comando de Streamlit
st.set_page_config(page_title="Indicadores VIH - Unidad 5", layout="wide")

# Para regenerar .shx si falta
os.environ["SHAPE_RESTORE_SHX"] = "YES"

def parse_val(x):
    if pd.isna(x): return None
    s = str(x).strip().lower()
    mul = {"k":1e3, "m":1e6, "b":1e9}
    return float(s[:-1]) * mul[s[-1]] if s and s[-1] in mul else float(s)

@st.cache_data
def cargar_csv(path):
    df = pd.read_csv(path)
    for col in df.columns[1:]:
        df[col] = df[col].apply(parse_val)
    df.set_index("country", inplace=True)
    return df

@st.cache_data
def cargar_shp(path="ne_110m_admin_0_countries.shp"):
    g = gpd.read_file(path)
    return g.rename(columns={"ADMIN":"country","CONTINENT":"continent"})[["country","continent","geometry"]]

# Carga de datos
df_deaths = cargar_csv("annual_hiv_deaths_number_all_ages.csv")
df_new    = cargar_csv("newly_hiv_infected_number_all_ages.csv")
df_plwh   = cargar_csv("people_living_with_hiv_number_all_ages.csv")
gdf       = cargar_shp()

indicadores = {
    "Muertes por VIH": df_deaths,
    "Nuevas infecciones VIH": df_new,
    "Personas viviendo con VIH": df_plwh
}

años = sorted(int(y) for y in df_deaths.columns)
min_año, max_año = años[0], años[-1]

# -- Funciones de gráfico --

def metricas_globales(df):
    s = df.sum(axis=0).fillna(0)
    mxy, mny = int(s.idxmax()), int(s.idxmin())
    ly = max_año
    c1, c2, c3 = st.columns(3)
    c1.metric("Año con más valor", mxy, f"{int(s[str(mxy)]):,}")
    c2.metric("Año con menos valor", mny, f"{int(s[str(mny)]):,}")
    c3.metric(f"Valor en {ly}", f"{int(s[str(ly)]):,}")
    st.markdown("---")

def plot_tendencia(df, key):
    st.subheader("Tendencia Global")
    col1, col2 = st.columns([1, 4], gap="small")
    with col1:
        t = st.radio("", ["Línea", "Área"], key=key + "_tp", horizontal=True)
    with col2:
        r = st.slider("", min_año, max_año, (min_año, max_año), key=key + "_rng")
    serie = df.sum(axis=0).loc[str(r[0]):str(r[1])].astype(int)
    dfp = pd.DataFrame({"Año": serie.index.astype(int), "Valor": serie.values})
    chart = alt.Chart(dfp).mark_line() if t=="Línea" else alt.Chart(dfp).mark_area(opacity=0.3)
    chart = chart.encode(x="Año:O", y="Valor:Q").properties(width=700, height=350).configure_view(strokeOpacity=0)
    st.altair_chart(chart, use_container_width=True)

def plot_top(df, key):
    st.subheader("Top N Países")
    col1, col2 = st.columns(2, gap="small")
    with col1:
        y = st.slider("", min_año, max_año, min_año, key=key + "_yr")
    with col2:
        n = st.number_input("", 5, 20, 10, key=key + "_n")
    topn = df[str(y)].fillna(0).sort_values(ascending=False).head(n).astype(int)
    dfp = topn.reset_index().rename(columns={str(y): "Valor", "country": "País"})
    chart = alt.Chart(dfp).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5) \
        .encode(x=alt.X("País:N", sort="-y"), y="Valor:Q") \
        .properties(width=700, height=350).configure_axis(labelAngle=-45)
    st.altair_chart(chart, use_container_width=True)

def plot_evolucion(df, key):
    st.subheader("Evolución por País")
    col1, col2 = st.columns([1, 4], gap="small")
    with col1:
        t = st.radio("", ["Línea", "Área"], key=key + "_t2", horizontal=True)
    with col2:
        ps = st.multiselect("", df.index, df.index[:3], key=key + "_ps")
    if not ps:
        st.info("Selecciona al menos un país.")
        return
    evo = df.loc[ps].T.fillna(0).astype(int)
    dfm = evo.reset_index().melt(id_vars="index", var_name="País", value_name="Valor").rename(columns={"index":"Año"})
    mark = "line" if t=="Línea" else "area"
    opacity = 1 if t=="Línea" else 0.3
    chart = alt.Chart(dfm).mark_line(opacity=opacity) if mark=="line" else alt.Chart(dfm).mark_area(opacity=opacity)
    chart = chart.encode(x="Año:O", y="Valor:Q", color="País:N").properties(width=700, height=350)
    st.altair_chart(chart, use_container_width=True)

def plot_comp_ind(_df, key):
    st.subheader("Comparación Indicadores (1990–2011)")
    sis = st.multiselect("", list(indicadores), list(indicadores), key=key+"_inds")
    comp = pd.DataFrame({i: indicadores[i].sum(axis=0).astype(int) for i in sis}).loc["1990":"2011"]
    dfm = comp.reset_index().melt(id_vars="index", var_name="Indicador", value_name="Valor").rename(columns={"index":"Año"})
    chart = alt.Chart(dfm).mark_line(point=True).encode(x="Año:O", y="Valor:Q", color="Indicador:N") \
                        .properties(width=700, height=350)
    st.altair_chart(chart, use_container_width=True)

def plot_tasa(df, key):
    st.subheader("Tasas de Variación Anual")
    ps = st.multiselect("Países", df.index, df.index[:3], key=key+"_ps")
    r = st.slider("", min_año, max_año, (min_año, max_año), key=key + "_rng")
    sub = df.loc[ps, [str(y) for y in range(r[0], r[1]+1)]].T
    pct = (sub.pct_change().dropna() * 100).astype(float).reset_index().melt(id_vars="index", var_name="País", value_name="% Cambio").rename(columns={"index":"Año"})
    chart = alt.Chart(pct).mark_bar().encode(x="Año:O", y="% Cambio:Q", color="País:N") \
                         .properties(width=700, height=350)
    st.altair_chart(chart, use_container_width=True)

def render_comparacion():
    vistas = [
        ("Tendencia", plot_tendencia),
        ("Top N Países", plot_top),
        ("Evolución", plot_evolucion),
        ("Comparación Ind.", plot_comp_ind),
        ("Tasas Anual", plot_tasa)
    ]
    c1, c2 = st.columns(2)
    for col, prefix in zip([c1, c2], ["A", "B"]):
        with col:
            st.markdown(f"### Gráfica {prefix}")
            indi = st.selectbox("Indicador", list(indicadores), key=f"cmp_ind_{prefix}")
            df_orig = indicadores[indi].copy(); df_orig.name = indi
            title, fn = st.selectbox("Vista", vistas, format_func=lambda x: x[0], key=f"cmp_v_{prefix}")
            fn(df_orig, f"cmp_{prefix}")

# -- Sidebar y navegación --

st.sidebar.title("🔍 Navegación")
page = st.sidebar.radio("", ["Gráficas", "Mapa", "Comparación Gráficas"])

if page in ["Gráficas", "Mapa"]:
    sel = st.sidebar.selectbox("Indicador", list(indicadores))
    df_sel = indicadores[sel]; df_sel.name = sel

if page == "Gráficas":
    st.header(f"📈 Indicador: {sel}")
    metricas_globales(df_sel)
    tabs = st.tabs(["Tendencia","Top N","Evolución","Comparación","Tasas"])
    funcs = [plot_tendencia, plot_top, plot_evolucion, plot_comp_ind, plot_tasa]
    keys  = ["tg","tn","ep","ci","tv"]
    for tab, fn, key in zip(tabs, funcs, keys):
        with tab:
            fn(df_sel, key)

elif page == "Mapa":
    st.sidebar.markdown("### Configuración de Mapa")
    mcol1, mcol2 = st.sidebar.columns(2, gap="small")
    with mcol1:
        map_type = st.radio("", ["Anual", "Incremento"], index=0)
    with mcol2:
        palette = st.selectbox("", ["YlOrRd","Blues","PuRd","Greens"], index=0)

    if map_type == "Anual":
        year    = st.sidebar.slider("Año", min_año, max_año, min_año)
        gdf_map = gdf.merge(df_sel[[str(year)]].reset_index(), on="country", how="left")
        legend, data_col = f"{sel} ({year})", str(year)
    else:
        start, end = st.sidebar.slider("Rango años", min_value=min_año, max_value=max_año, value=(min_año, min_año+1))
        diff       = df_sel[str(end)] - df_sel[str(start)]
        diff.name  = f"Δ {start}→{end}"
        gdf_map    = gdf.merge(diff.reset_index().rename(columns={diff.name:str(diff.name)}), on="country", how="left")
        legend, data_col = diff.name, str(diff.name)

    m = folium.Map(location=[0,0], zoom_start=2, tiles=None, control_scale=True)
    folium.Choropleth(geo_data=gdf_map.__geo_interface__, data=gdf_map,
                      columns=["country", data_col], key_on="feature.properties.country",
                      fill_color=palette, fill_opacity=0.9, line_opacity=0.3,
                      nan_fill_color="lightgray", legend_name=legend).add_to(m)
    folium.GeoJson(gdf_map.__geo_interface__,
                   style_function=lambda f: {"fillOpacity": 0, "weight": 0},
                   tooltip=GeoJsonTooltip(fields=["country", data_col], aliases=["País", legend], localize=True)
    ).add_to(m)
    MeasureControl(position="bottomleft", primary_length_unit="kilómetros").add_to(m)
    Fullscreen(position="topright").add_to(m)
    st_folium(m, width=1080, height=800, key=f"map_{map_type}_{palette}")

else:
    st.header("🔀 Comparación de Gráficas")
    render_comparacion()
