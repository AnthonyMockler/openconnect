import os
from dotenv import load_dotenv
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
CachingStrategy.use(JSON)
import sqlite3



ookla = pd.read_parquet('ookla.parquet')
pd.options.plotting.backend = 'plotly'


countries = ['Brunei', 'Cambodia', 'Cook Islands', 'Fiji', 'Indonesia', 'Kiribati', 'Laos', 'Malaysia', 'Marshall Islands', 'Micronesia', 'Mongolia', 'Myanmar',
             'Nauru', 'Niue', 'Palau', 'Papua New Guinea', 'Philippines', 'Samoa', 'Solomon Islands', 'Thailand', 'Timor Leste', 'Tokelau', 'Tonga', 'Tuvalu', 'Vanuatu', 'Vietnam']
amenities = dict()
amenities['Schools'] = 'school'
amenities['Hospitals'] = 'hospital'
def unicef_blue(text,size='h3'):
    outstring = f"""<{size} style="color:#1cabe2;">{text}</h1>"""
    return outstring

def set_font():
    return """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@100;300;400;500;700&display=swap');
        html, body, [class*="css"]  {
        font-family: "Roboto", sans-serif !important;
        font-weight: 300;
        };
        .st-ae {
            font-family: "Roboto", sans-serif !important;
        }
    </style>

    """
st.markdown(set_font(),unsafe_allow_html=True)
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

def merge_with_connectivity(out):
    out = out[~out.lat.isna()]
    out['quadkey_14'] = out.apply(make_quadkey, axis=1)
    tmp = out.set_index('quadkey_14')
    tmp.index = tmp.index.astype('str')
    ookla.index = ookla.index.astype('str')
    tmp = tmp.join(ookla, how='left')
    tmp = tmp.reset_index().drop_duplicates(
        subset=['name', 'quadkey_14'],
        keep='last').reset_index(drop=True)
    return tmp
def make_bar(df):
    df.index = df.index.str.slice(stop=20)
    df.index = df.index + '...'
    df = df[~df.index.duplicated(keep='first')]
    plot = df['Avg Download(Mbps)'].plot(kind='barh', color_discrete_sequence=["#1CABE2"])
    plot.layout.update(showlegend=False)
    plot.update_xaxes(tickangle=15)
    plot.update_layout({'plot_bgcolor': 'rgba(0, 0, 0, 0)','paper_bgcolor': 'rgba(0, 0, 0, 0)'})
    return plot
def filter_elements(result):
    elements = list()
    for element in result.elements():
        elements.append(make_details(element))
    filtered = [element for element in elements if element is not None]
    return filtered


@st.cache
def download_data(viz):
    return viz.to_csv(index=False)


@st.experimental_memo(show_spinner=False)
def get_overpass_query(area_name,facility):
    areaId = nominatim.query(area_name).areaId()
    query = overpassQueryBuilder(area=areaId, elementType='way', selector=f'"amenity"="{amenities[facility]}"',
                                 out='body', includeCenter=True, includeGeometry=True)
    with st.spinner(f"Retrieving {facility} in {area_name}, may take up to 60 seconds"):
        result = overpass.query(query,timeout=120)
    return result

st.markdown(unicef_blue('OpenConnect Connectivity Report for:','h3'),unsafe_allow_html=True)
with st.expander("Choose region",expanded=True):
    boxcols = st.columns([1,2])
    map_zoom = 5
    with boxcols[0]:
        facility = st.radio("Facility Type:",['Schools','Hospitals'])
        

    with boxcols[1]:
        region = st.radio("Region Type",['Country','Custom Region','Custom CSV (Beta)'])
        if region == 'Country':
            area_name = st.selectbox("",countries,index=19)
            map_zoom = 5
        if region =='Custom Region':
            area_name = st.text_input("Enter a City, Country","",placeholder="City, Country (e.g. Bangkok, Thailand)")
            map_zoom = 9
        if region=='Custom CSV (Beta)':
            area_name = ''
            out = None
            infile_amenity = st.radio('This is a list of',['Schools','Hospitals'])
            amenity_type = amenities[infile_amenity]
            infile = st.file_uploader('Upload a CSV. Must have columns named "name", "lat" and "lon"')
            if infile is not None:
                out = pd.read_csv(infile)
                if not "lat" in out.columns:
                    latcol = st.radio('Latitude in column:',out.columns)
                    loncol = st.radio('Longitude in column',out.columns)
                    namecol = st.radio('Facility Name in column',out.columns)
                    out = out.rename(columns={latcol:'lat',loncol:'lon',namecol:'name'})
                out['amenity'] = amenity_type
                area_name = 'Custom Area'




if len(area_name) > 3:
    if area_name == 'Custom Area':
        pass
    else:
        result = get_overpass_query(area_name,facility)
        filtered = filter_elements(result)
        out = pd.DataFrame(filtered)
    with st.spinner(f'Getting connectivity estimates for {area_name}'):
        out = merge_with_connectivity(out)
    out['Avg Download(Mbps)'] = round((out.avg_d_kbps / 1000), 1)
    out['Avg Upload(Mbps)'] = round((out.avg_u_kbps / 1000), 1)
    out['Total Devices'] = round((out.devices * 4), 0)
    total = len(out)
    has_connectivity = len(out[pd.notnull(out.avg_d_kbps)])
    no_connectivity = len(out[pd.isnull(out.avg_d_kbps)])
    pct_below_10mbps = len(out[out.avg_d_kbps < 10000]) / len(out)
    average_speed = out['Avg Download(Mbps)'].mean()

    st.markdown(unicef_blue(f'{facility} in {area_name}'), unsafe_allow_html=True)
    metrics = list()
    metrics.append([f"Total {facility}", total])
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
    average = out['Avg Download(Mbps)'].plot(kind='hist', color_discrete_sequence=["#1CABE2"])
    average.update_layout({'plot_bgcolor': 'rgba(0, 0, 0, 0)','paper_bgcolor': 'rgba(0, 0, 0, 0)'})
    

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
    map_1.update_layout(
    mapbox=dict(
        accesstoken='pk.eyJ1IjoidG9vbHNmb3JyYWRpY2FscyIsImEiOiJjazF0Mzd2bWgwa3kzM2hsaWxnbHhwc211In0.UeliSBmRYh9nUQPc3E1UfQ',
          style = 'mapbox://styles/toolsforradicals/ckodxjrer0bjc17mt4d1ez8nv'
    ),
)
    st.plotly_chart(map_1, use_container_width=True)


    with st.expander(f"{facility} without connectivity"):
        if len(viz[pd.isnull(viz['Avg Download(Mbps)'])]):
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
            map_2.update_layout(
    mapbox=dict(
        accesstoken='pk.eyJ1IjoidG9vbHNmb3JyYWRpY2FscyIsImEiOiJjazF0Mzd2bWgwa3kzM2hsaWxnbHhwc211In0.UeliSBmRYh9nUQPc3E1UfQ',
          style = 'mapbox://styles/toolsforradicals/ckodxjrer0bjc17mt4d1ez8nv'
    ),
)
            st.plotly_chart(map_2, use_container_width=True)
        else:
            st.write(f"No {facility} in dataset without connectivity")


    with st.expander("Summary statistics"):
        st.subheader(f"All {str.lower(facility)} in {area_name} by speed")
        st.plotly_chart(average, use_container_width=True)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f'10 fastest {str.lower(facility)}')
            top20 = viz.sort_values('Avg Download(Mbps)', ascending=False)[0:10]
            top20 = top20.set_index('name').drop_duplicates()
            top20_plot = make_bar(top20)
            st.plotly_chart(top20_plot, use_container_width=True)
        with col2:
            st.subheader(f'10 slowest {str.lower(facility)}')
            bottom20 = viz.sort_values('Avg Download(Mbps)', ascending=True)[0:10]
            bottom20 = bottom20.set_index('name').drop_duplicates()
            bottom20_plot = make_bar(bottom20)
            st.plotly_chart(bottom20_plot, use_container_width=True)

with st.expander("About this app"):
    with open('README.md', 'r') as f:
        st.markdown(f.read())
        st.plotly_chart(top20_plot, use_container_width=True)
        with col2:
            st.subheader(f'10 slowest {str.lower(facility)}')
            bottom20 = viz.sort_values('Avg Download(Mbps)', ascending=True)[0:10]
            bottom20 = bottom20.set_index('name').drop_duplicates()
            bottom20_plot = make_bar(bottom20)
            st.plotly_chart(bottom20_plot, use_container_width=True)

with st.expander("About this app"):
    with open('README.md', 'r') as f:
        st.markdown(f.read())
