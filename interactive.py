from pyquadkey2 import quadkey as qk
from OSMPythonTools.cachingStrategy import CachingStrategy, JSON, Pickle
from OSMPythonTools.overpass import overpassQueryBuilder, Overpass
import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

from OSMPythonTools.nominatim import Nominatim
nominatim = Nominatim()
overpass = Overpass()
CachingStrategy.use(Pickle)


connectstring = f"postgresql://{st.secrets['postgres']['user']}:{st.secrets['postgres']['password']}@{st.secrets['postgres']['host']}:{st.secrets['postgres']['port']}/{st.secrets['postgres']['dbname']}"
engine = create_engine(connectstring)
#engine = create_engine('sqlite:///ookla.sqlite')
pd.options.plotting.backend = 'plotly'


countries = ['Brunei', 'Cambodia', 'Cook Islands', 'Fiji', 'Indonesia', 'Kiribati', 'Laos', 'Malaysia', 'Marshall Islands', 'Micronesia', 'Mongolia', 'Myanmar',
             'Nauru', 'Niue', 'Palau', 'Papua New Guinea', 'Philippines', 'Samoa', 'Solomon Islands', 'Thailand', 'Timor Leste', 'Tokelau', 'Tonga', 'Tuvalu', 'Vanuatu', 'Vietnam']


def make_details(element):
    tags = element.tags()
    if 'name' in tags:
        out = dict()
        out['amenity'] = tags['amenity']
        out['name'] = tags['name']
        if 'lat' in tags:
            out['lat'] = tags['lat']
            out['lon'] = tags['lon']
        elif bool(element.centerLat()):
            out['lat'] = element.centerLat()
            out['lon'] = element.centerLon()
        elif bool(element.geometry()):
            out['lat'] = element.geometry()['coordinates'][0][0][1]
            out['lon'] = element.geometry()['coordinates'][0][0][0]
        else:
            out['lat'] = None
            out['lon'] = None
        return out
    else:
        return None
def make_quadkey(row):
    return qk.from_geo((row['lat'], row['lon']), 14)
def merge_with_connectivity(result):
    filtered = filter_elements(result)
    out = pd.DataFrame(filtered)
    out = out[~out.lat.isna()]
    out['quadkey_14'] = out.apply(make_quadkey, axis=1)
    quadkeys = tuple(out.quadkey_14.astype('str').unique())
    sql_query = f"SELECT quadkey_14, avg_d_kbps, avg_u_kbps, devices from ookla where quadkey_14 in {quadkeys}"
    ookla = pd.read_sql_query(sql_query, engine, index_col='quadkey_14')
    tmp = out.set_index('quadkey_14')
    tmp.index = tmp.index.astype('str')
    tmp = tmp.join(ookla, how='left')
    tmp = tmp.reset_index().drop_duplicates(
        subset=['name', 'quadkey_14'],
        keep='last').reset_index(drop=True)
    return tmp
def make_bar(df):
    df.index = df.index.str.slice(stop=20)
    df.index = df.index + '...'
    df = df[~df.index.duplicated(keep='first')]
    plot = df['Avg Download(Mbps)'].plot(kind='barh')
    plot.layout.update(showlegend=False)
    plot.update_xaxes(tickangle=15)
    return plot
def filter_elements(result):
    elements = list()
    for element in result.elements():
        elements.append(make_details(element))
    filtered = [element for element in elements if element is not None]
    return filtered

def unicef_blue(text):
    outstring = f"""<h3 style="color:#1cabe2;">{text}</h1>"""
    return outstring
@st.experimental_memo(show_spinner=False)
def get_overpass_query(area_name):
    areaId = nominatim.query(area_name).areaId()
    query = overpassQueryBuilder(area=areaId, elementType='way', selector='"amenity"="school"',
                                 out='body', includeCenter=True, includeGeometry=True)
    with st.spinner(f"Retrieving schools in {area_name}, may take up to 60 seconds"):
        result = overpass.query(query,timeout=60)
    return result

st.title('OpenConnect')
st.subheader("Connectivity Report for:")
with st.expander("Choose region"):
    boxcols = st.columns([1,2])
    map_zoom = 5
    with boxcols[0]:
        region = st.radio("",['Country','Custom Region','Custom CSV (Coming Soon)'])

    with boxcols[1]:
        if region == 'Country':
            area_name = st.selectbox("",countries,index=19)
            map_zoom = 5
        if region =='Custom Region':
            area_name = st.text_input("Enter a City, Country","Bangkok, Thailand",placeholder="City, Country")
            map_zoom = 9
        if region=='Custom CSV (Coming Soon)':
            area_name = st.selectbox("",countries,index=19)




result = get_overpass_query(area_name)
out = merge_with_connectivity(result)
out['Avg Download(Mbps)'] = round((out.avg_d_kbps / 1000), 1)
out['Avg Upload(Mbps)'] = round((out.avg_u_kbps / 1000), 1)
out['Total Devices'] = round((out.devices * 4), 0)
total = len(out)
has_connectivity = len(out[pd.notnull(out.avg_d_kbps)])
no_connectivity = len(out[pd.isnull(out.avg_d_kbps)])
pct_below_10mbps = len(out[out.avg_d_kbps < 10000]) / len(out)
average_speed = out['Avg Download(Mbps)'].mean()


@st.cache
def download_data(viz):
    return viz.to_csv(index=False)
#st.markdown(f"**{area_name}** has around **{total}** schools in the OpenStreetMap database")
#st.markdown(f"Of those, **{has_connectivity / total:.0%}** have connectivity scores, **{no_connectivity / total:.0%}** had no connectivity in the Ookla dataset")
#st.markdown(f"Average speeds are around **{average_speed:.1f}Mbps**, with {pct_below_10mbps:.0%} of schools reporting speeds below 10Mbps")
st.markdown(unicef_blue(area_name), unsafe_allow_html=True)
metrics = list()
metrics.append(["Total Schools", total])
metrics.append(["With Connectivity", f'{has_connectivity / total:.0%}'])
metrics.append(["Without Connectivity", f'{no_connectivity / total:.0%}'])
metrics.append(["Below 10Mbps", f'{pct_below_10mbps:.0%}'])
metrics.append(["Average speed (Mbps)", f"{average_speed:.0f}"])

metric_cols = st.columns(len(metrics))
i = 0
for col in metric_cols:
    col.metric(metrics[i][0], metrics[i][1])
    i += 1


viz = out[['amenity', 'name', 'lat', 'lon', 'Avg Download(Mbps)', 'Avg Upload(Mbps)',
           'Total Devices']].copy()
viz['connectivity_rank'] = viz['Avg Download(Mbps)'].rank(pct=True)
viz_has_connectivity = viz[pd.notna(viz['Avg Download(Mbps)'])]
average = out['Avg Download(Mbps)'].plot(kind='hist')

st.download_button("Download CSV", download_data(viz),
                   file_name=f'{area_name}.csv')
map_1 = px.scatter_mapbox(viz,
                          lat="lat", lon="lon",
                          color="connectivity_rank",
                          color_continuous_scale=px.colors.colorbrewer.RdYlGn,
                          size_max=15,
                          zoom=map_zoom,
                          mapbox_style='carto-positron',
                          hover_data=['name', 'Avg Download(Mbps)'],
                          height=700)
map_1.layout.update(showlegend=False)
st.plotly_chart(map_1, use_container_width=True)


with st.expander("Schools without connectivity"):
    map_2 = px.scatter_mapbox(viz[pd.isnull(viz['Avg Download(Mbps)'])],
                              lat="lat", lon="lon",
                              color="connectivity_rank",
                              color_continuous_scale=px.colors.colorbrewer.RdYlGn,
                              size_max=15,
                              zoom=map_zoom,
                              mapbox_style='carto-positron',
                              hover_data=['name'],
                              height=700)
    map_2.layout.update(showlegend=False)
    st.plotly_chart(map_2, use_container_width=True)


with st.expander("Summary statistics"):
    st.subheader(f"All schools in {area_name} by speed")
    st.plotly_chart(average, use_container_width=True)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader('10 Fastest Schools')
        top20 = viz.sort_values('Avg Download(Mbps)', ascending=False)[0:10]
        top20 = top20.set_index('name').drop_duplicates()
        top20_plot = make_bar(top20)
        st.plotly_chart(top20_plot, use_container_width=True)
    with col2:
        st.subheader('10 slowest schools')
        bottom20 = viz.sort_values('Avg Download(Mbps)', ascending=True)[0:10]
        bottom20 = bottom20.set_index('name').drop_duplicates()
        bottom20_plot = make_bar(bottom20)
        st.plotly_chart(bottom20_plot, use_container_width=True)


#top10[['name','Average Download Speed (Mbps)']].plot()
