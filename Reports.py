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

# ADD SOME NOTES
# MORE PROGRAMMING

# Page set up
st.set_page_config(layout="wide")
#st.markdown('![EEW logo](https://github.com/edgi-govdata-archiving/EEW-Image-Assets/blob/main/Jupyter%20instructions/eew.jpg?raw=true) ![EDGI logo](https://github.com/edgi-govdata-archiving/EEW-Image-Assets/blob/main/Jupyter%20instructions/edgi.png?raw=true)')

row1 = st.container()
row2 = st.container()
with row2:
	col1, col2, col3 = st.columns([.2, .4, .4])

if "first_time" not in st.session_state:
	st.session_state["first_time"] = True
if "cds" not in st.session_state:
	st.session_state["cds"] = None
if "cds_shape" not in st.session_state:
	st.session_state["cds_shape"] = None

def grades(value):
	value = value[0]
	if value >= 80:
		grade = "F"
	elif value < 80 and value >=60:
		grade = "D"
	elif value < 60 and value >=40:
		grade = "C"
	elif value < 40 and value >=20:
		grade = "B"
	else:
		grade = "A"
	return grade

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
		"Which Congressional District?",
		cds_tuple
	)
	program = st.selectbox(
		"Which Environmental Legislation?",
		("CWA", "CAA", "RCRA")
	)

with row1:
	st.title("EEW Report Card for " + region.replace(" ", "") + ": " + program)
	st.caption("""The Environmental Protection Agency (EPA) is charged by Congress to enforce laws that protect people from air pollution, water pollution and hazardous waste. Without effective enforcement, these laws are meaningless. Based on data from EPA’s Enforcement and Compliance History Online (ECHO) database this report card reviews violations, inspections and enforcement actions under three laws: Clean Air Act (CAA), Clean Water Act (CWA) and Resource Conservation and Recovery Act (RCRA) for this Congressional District or State since 2001.""")
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
percentiles = pd.read_sql_query('SELECT * FROM "cd_per_1000" WHERE "CD.State" = \'' + region.replace(" ", "") + '\'', con)


con.close()

with col1:
	this_active_facilities = active_facilities.loc[active_facilities["program"] == program]
	this_per_fac = per_fac.loc[per_fac["program"] == program] # inspection and violation rates per facility 2022
	this_enf_per_fac = enf_per_fac.loc[enf_per_fac["program"] == program] # enforcements per facility 2022
	#c1, c2, c3, c4 = st.columns(4)
col1.metric("Number of Active Facilities Regulated under " + program + " in 2022", str(this_active_facilities["count"].values[0]))
col1.info(
	"""A regulated facility in this report is a facility that reports air or water emissions under the Clean Air Act or Clean Water
	Act, or a facility that generates, transports, or disposes of hazardous waste under the Resource Conservation and
	Recovery Act. Regulated facilities can be large-scale e.g. oil refineries, or small-scale e.g. dry cleaners.
	""", 
	icon="ℹ️"
)
grades_help ="""
We look at how this district’s national percentile compares with all U.S. congressional districts on
the number of violations. As an example, a Violations per Facility score of 64 for CWA means that this district has more
CWA violations per regulated facility than 64% of all districts in the United States.
From these scores we might assign letter grades to districts–the top 20%, those districts with more
violations than 80% of all districts, would get an F; the districts scoring between 60% and 80% get a D;
between 40% and 60% get a C; between 20% and 40% get a B; and less than 20% get an A. 
"""
try:
	col1.metric("Violations per Facility in 2022", 
		str(round(this_per_fac.loc[this_per_fac["type"]=="violations"]["count"].values[0], 2)), 
		grades(percentiles[program+"_Viol_Pct"] * 100), 
		delta_color="off",
		help = grades_help)
	
	col1.metric("Inspections per Facility in 2022", 
		str(round(this_per_fac.loc[this_per_fac["type"]=="inspections"]["count"].values[0], 2)), 
		grades(percentiles[program+"_Viol_Pct"] * 100), 
		delta_color="off",
		help = grades_help)
	
	col1.metric("Enforcement Actions per Facility in 2022", 
		str(round(this_enf_per_fac["count"].values[0], 2)), 
		grades(percentiles[program+"_Viol_Pct"] * 100), 
		delta_color="off",
		help = grades_help)
	
	with col2:
		# Visualize CD data
		this_non_compliants = non_compliants.loc[non_compliants["program"] == program] # least compliant facilities
		this_non_compliants = geopandas.GeoDataFrame(this_non_compliants, geometry = geopandas.points_from_xy(this_non_compliants["fac_long"], this_non_compliants["fac_lat"], crs=4269))
		st.markdown("#### 20 facilities most non-compliant with " + program + " over the past 3 years")
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
		trump = this_violations.loc[this_violations["year"].isin(["2017", "2018", "2019", "2020"])][["count"]].mean()
		biden = this_violations.loc[this_violations["year"].isin(["2021", "2022"])][["count"]].mean()
		pct = round(((trump - biden) / trump * 100)["count"], 2)
		col3.metric("Change in Average Violations Per Year Between 2017-2020 and 2021-2022", trump - biden, str(pct)+"%") 

		this_inspections  = inspections.loc[inspections["program"] == program]# Over time
		this_inspections["year"] = this_inspections["year"].astype(str)
		trump = this_inspections.loc[this_inspections["year"].isin(["2017", "2018", "2019", "2020"])][["count"]].mean()
		biden = this_inspections.loc[this_inspections["year"].isin(["2021", "2022"])][["count"]].mean()
		pct = round(((trump - biden) / trump * 100)["count"], 2)

		st.markdown("#### Enforcement: " + program + " inspections and penalties since 2001")
		this_enforcements  = enforcements.loc[enforcements["program"] == program]# Over time
		this_enforcements["year"] = this_enforcements["year"].astype(str)

		combined = this_inspections.merge(this_enforcements, how = "left", right_on="year", left_on="year")
		combined.rename(columns={"count_x": "Inspections", "count_y": "Enforcement Actions"}, inplace=True)
		st.line_chart(combined, x = "year", y = ["Inspections", "Enforcement Actions"])
		col3.metric("Change in Average Inspections Per Year Between 2017-2020 and 2021-2022", trump - biden, str(pct)+"%") 

except:
	with col2:
		st.warning('EPA data isn\'t perfect. The congressional district you selected, ' + region + ', doesn\'t actually exist. Due to errors in EPA\'s database, some facilities may be recorded as part of this imaginary congressional district.', icon="⚠️")





