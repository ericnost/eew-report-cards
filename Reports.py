# streamlit place picker test
# Pick a place and get ECHO facilities
#https://docs.streamlit.io/library/get-started/create-an-app

import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from streamlit_folium import st_folium
import pandas as pd
import urllib.parse
import geopandas
import folium
import json
import requests, zipfile, io
import sqlite3

# Page set up
st.set_page_config(layout="wide")
#st.markdown('![EEW logo](https://github.com/edgi-govdata-archiving/EEW-Image-Assets/blob/main/Jupyter%20instructions/eew.jpg?raw=true) ![EDGI logo](https://github.com/edgi-govdata-archiving/EEW-Image-Assets/blob/main/Jupyter%20instructions/edgi.png?raw=true)')

row1 = st.container()
row2 = st.container()
with row2:
	col1, col2, col3 = st.columns([.25, .5, .25])

if "first_time" not in st.session_state:
	st.session_state["first_time"] = True
if "cds" not in st.session_state:
	st.session_state["cds"] = None
if "cds_shape" not in st.session_state:
	st.session_state["cds_shape"] = None

# Place picker
# Preset list of congressional districts
# Only need to do this once

#@st.cache_data
def cds():
	con = sqlite3.connect("region.db")
	cur = con.cursor()
	cds_df = pd.read_sql_query('SELECT * FROM "regions"', con)
	con.close()

	cds_df["Name"] = cds_df["state"].astype(str) + " " + cds_df["region"].astype(str) 

	cds_gdf = geopandas.read_file("https://raw.githubusercontent.com/edgi-govdata-archiving/ECHO-Geo/main/cb_2013_us_cd113_500k.json")
	cds_gdf.set_crs(4269, inplace=True)

	return cds_df, cds_gdf

if st.session_state["first_time"]:
	st.session_state["cds"], st.session_state["cds_shape"] = cds()
	st.session_state["first_time"] = False

with col1:
	cds_tuple = st.session_state["cds"]["Name"].unique()
	region = st.selectbox(
		"Which CD?",
		cds_tuple
	)
	program = st.selectbox(
		"Which program?",
		("CWA", "CAA", "RCRA")
	)

with row1:
	st.title("EEW Report Card for " + region + ": " + program)
# Load CD data
con = sqlite3.connect("region.db")
cur = con.cursor()
region_id = st.session_state["cds"].loc[st.session_state["cds"]["Name"] == region].index[0] + 1 # Look up region id and add 1 since the db is not zero-indexed
#violations_by_facilities = pd.read_sql_query('SELECT * FROM "violations_by_facilities" WHERE "region_id" = ' + str(region_id), con)
violations = pd.read_sql_query('SELECT * FROM "violations" WHERE "region_id" = ' + str(region_id), con)# ... over time
inspections = pd.read_sql_query('SELECT * FROM "inspections" WHERE "region_id" = ' + str(region_id), con) # Over time
enforcements = pd.read_sql_query('SELECT * FROM "enforcements" WHERE "region_id" = ' + str(region_id), con) # Over time
per_fac = pd.read_sql_query('SELECT * FROM "per_fac" WHERE "region_id" = ' + str(region_id), con)# inspection and violation rates per facility 2022
enf_per_fac  = pd.read_sql_query('SELECT * FROM "enf_per_fac" WHERE "region_id" = ' + str(region_id), con)# enforcements per facility 2022
non_compliants  = pd.read_sql_query('SELECT * FROM "non_compliants" WHERE "region_id" = ' + str(region_id), con)# least compliant facilities
active_facilities = pd.read_sql_query('SELECT * FROM "active_facilities" WHERE "region_id" = ' + str(region_id), con)

con.close()

with col1:
	this_active_facilities = active_facilities.loc[active_facilities["program"] == program]
	this_per_fac = per_fac.loc[per_fac["program"] == program] # inspection and violation rates per facility 2022
	this_enf_per_fac = enf_per_fac.loc[enf_per_fac["program"] == program] # enforcements per facility 2022
	#c1, c2, c3, c4 = st.columns(4)
col1.metric("Number of Active Facilities in 2022", str(this_active_facilities["count"].values[0]))
col1.metric("Violations per Facility in 2022", str(this_per_fac.loc[this_per_fac["type"]=="violations"]["count"].values[0]), "Trend compared to nation...", delta_color="off")
col1.metric("Inspections per Facility in 2022", str(this_per_fac.loc[this_per_fac["type"]=="inspections"]["count"].values[0]), "Trend compared to nation...", delta_color="off")
col1.metric("Enforcement Actions per Facility in 2022", str(this_enf_per_fac["count"].values[0]), "Trend compared to nation...", delta_color="off")
with col2:
	# Visualize CD data
	this_non_compliants = non_compliants.loc[non_compliants["program"] == program] # least compliant facilities
	this_non_compliants = geopandas.GeoDataFrame(this_non_compliants, geometry = geopandas.points_from_xy(this_non_compliants["fac_long"], this_non_compliants["fac_lat"], crs=4269))
	st.markdown("#### X facilities most non-compliant with " + program + " over the past 3 years")
	m = folium.Map(tiles="cartodb positron")
	# Get CD
	contains = st.session_state["cds_shape"].sindex.query(this_non_compliants.geometry, predicate="intersects")
	cd = st.session_state["cds_shape"].loc[st.session_state["cds_shape"].index == contains[1][0]]

	folium.GeoJson(
		cd,
		tooltip = folium.GeoJsonTooltip(fields=['STATEFP',	'CD113FP'])
	).add_to(m)
	nc_markers = [folium.CircleMarker(
		location=[mark["fac_lat"], mark["fac_long"]],
		radius = 5,
    color='blue',
    fill=True,
    fill_color='#3186cc',
    fill_opacity=0.7,
    tooltip=folium.Tooltip(mark["fac_name"]),
    popup=folium.Popup(mark["fac_name"] + "<p>" + mark["dfr_url"])
	) for index, mark in this_non_compliants.iterrows() if mark["fac_lat"]]
	for mark in nc_markers:
		mark.add_to(m)
	m.fit_bounds(m.get_bounds())
	out = st_folium(
		m,
		width = 750,
		returned_objects=[]
	)

with col3:
	this_violations  = violations.loc[violations["program"] == program]# ... over time
	this_violations["year"] = this_violations["year"].astype(str)
	st.markdown("#### Compliance: " + program + " violations since 2001")
	st.line_chart(this_violations, x = "year", y = "count")
	this_inspections  = inspections.loc[inspections["program"] == program]# Over time
	this_inspections["year"] = this_inspections["year"].astype(str)
	st.markdown("#### Enforcement: " + program + " inspections and penalties since 2001")
	this_enforcements  = enforcements.loc[enforcements["program"] == program]# Over time
	this_enforcements["year"] = this_enforcements["year"].astype(str)
	combined = this_inspections.merge(this_enforcements, how = "left", right_on="year", left_on="year")
	combined.rename(columns={"count_x": "Inspections", "count_y": "Enforcement Actions"}, inplace=True)
	st.line_chart(combined, x = "year", y = ["Inspections", "Enforcement Actions"])





