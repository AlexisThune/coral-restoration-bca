import json
import math
import os
import sys
import time
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="BCA Model for coral restoration projects", layout="wide")
st.title("BCA Model for coral restoration projects")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import folium
import geopandas as gpd
import numpy as np
from folium.plugins import PolyLineTextPath
from shapely.geometry import LineString, Polygon
from streamlit_folium import st_folium

from src.config import load_config
from src.data_loading_and_processing.coral_loader import load_coral_for_project
from src.utils.grid_orientation import (
    grid_angle_from_offshore_edge,
    infer_offshore_edge,
    wave_alignment_with_grid,
)
from src.utils.technical_functions import get_epsg
from src.utils.simulation_time_estimator import (
    estimate_runtime_seconds,
    format_runtime,
)
from src.utils.results_export import build_results_archive
from src.utils.ui import InteractiveMap, RestorationProject, Scenario

SESSION_DEFAULTS = {
    "map_center": (-17.5, -150.5),
    "map_zoom": 7,
    "epsg": 32706,
    "location_set": False,
    "project_lat": None,
    "project_lon": None,
    "project_area_set": False,
    "project_area": None,
    "grid_angle_set": False,
    "grid_angle": None,
    "offshore_edge_idx": None,
    "edge_bathy_elevations": None,
    "orientation_requires_manual": False,
    "orientation_error": None,
    "manual_offshore_edge": 0,
    "wave_hm0": 8.0,
    "wave_tp": 11.0,
    "wave_zs0": 0.0,
    "wave_mainang": 270,
    "wave_conditions_set": False,
    "wave_conditions": None,
    "area_value_set": False,
    "area_value": None,
    "original_coral_cover_set": False,
    "restored_coral_zones_init": False,
    "restored_coral_zones_set": False,
    "restored_coral_zones": [],
    "restored_coral_zones_idx": 0,
    "restored_coral_zone_drawn": False,
    "coral_geojsons_saved": False,
    "parameters_validated": False,
    "user_logged_in_copernicus": False,
    "simulation_completed": False,
    "results": [],
    "results_archive": None,
    "simulation_runtime_samples": [],
}


def init_session_state(defaults):
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_project_state(keys_to_save):
    keys_to_save += ["map_center", "map_zoom", "simulation_runtime_samples"]
    for key in SESSION_DEFAULTS.keys():
        if key not in keys_to_save:
            st.session_state[key] = SESSION_DEFAULTS[key]
    st.rerun()


def initialize_geojson(name, epsg):
    return {
        "type": "FeatureCollection",
        "name": name,
        "crs": {
            "type": "name",
            "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg}"},
        },
        "features": [],
    }


@st.cache_data(show_spinner="🔍 Loading coral features in project area...")
def load_project_coral(data_path, project_area_coords, epsg_code):
    return load_coral_for_project(data_path, project_area_coords, epsg_code)


@st.cache_data(show_spinner="Estimating the offshore side from bathymetry...")
def sample_project_edge_bathymetry(bathymetry_path, project_area_coords, epsg_code):
    from src.data_loading_and_processing.bathymetry_loader import BathymetryDataLoader

    return BathymetryDataLoader.sample_project_area_edges(
        bathymetry_path, project_area_coords, epsg_code
    )


def add_map_arrow(coordinates, color, tooltip):
    line = folium.PolyLine(
        coordinates, color=color, weight=4, opacity=0.9, tooltip=tooltip
    ).add_to(imap.map)
    PolyLineTextPath(
        line,
        "➤",
        repeat=False,
        offset=7,
        attributes={"fill": color, "font-weight": "bold", "font-size": "20"},
    ).add_to(imap.map)


def project_line_to_map(coordinates, epsg_code):
    line = gpd.GeoSeries(
        [LineString(coordinates)], crs=f"EPSG:{epsg_code}"
    ).to_crs("EPSG:4326").iloc[0]
    return [(lat, lon) for lon, lat in line.coords]


def draw_zones(zones, color, tooltip_prefix, source_epsg):
    for idx, zone in enumerate(zones):
        # Créer GeoSeries pour reprojection
        gseries = gpd.GeoSeries([zone], crs=f"EPSG:{source_epsg}")
        gseries_4326 = gseries.to_crs("EPSG:4326")
        coords_4326 = [(lat, lon) for lon, lat in gseries_4326.iloc[0].exterior.coords]
        folium.Polygon(
            locations=coords_4326,
            color=color,
            fill=True,
            fill_opacity=0.6,
            tooltip=f"{tooltip_prefix} #{idx+1}",
        ).add_to(imap.map)


def draw_zones_with_validation(
    zones, color_unvalidated, color_validated, tooltip_prefix
):
    for idx, zone in enumerate(zones):
        folium.Polygon(
            locations=[[lat, lon] for lon, lat in zone["coords"]],
            color=color_unvalidated if not zone["validated"] else color_validated,
            fill=True,
            fill_opacity=0.6,
            tooltip=f"{tooltip_prefix} #{idx+1}",
        ).add_to(imap.map)


########## Page configuration ##########
init_session_state(SESSION_DEFAULTS)
config = load_config(config_path="src/config.json")


########## Map initialisation ##########
imap = InteractiveMap(
    start_coords=st.session_state.map_center, start_zoom=st.session_state.map_zoom
)

########## Add bathymetry data limits ##########
folium.Rectangle(
    bounds=[
        [-19.05, -153.1],
        [-15.55, -147.5],
    ],
    color="blue",
    fill=True,
    fill_opacity=0.03,
    popup="Bathymetry data limits",
).add_to(imap.map)

########## Add data mentions ##########
st.sidebar.header("Data sources")
# Coral Allen Atlas
st.sidebar.markdown(
    "Allen Coral Atlas maps, bathymetry and map statistics are © 2018-2023 Allen Coral Atlas Partnership and Arizona State University and licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
)
# NGDC Bathymetry
st.sidebar.markdown(
    "NOAA National Geophysical Data Center. 2006. Society Islands, French Polynesia Digital Elevation Model – 3 arc-second. NOAA National Centers for Environmental Information. Accessed 1 September 2025. URL: https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ngdc.mgg.dem:11511"
)


########## Add drawings to Map & GeoJSONs ##########
if st.session_state.get("location_set"):
    folium.Marker(
        location=[st.session_state.project_lat, st.session_state.project_lon],
        tooltip="Project location",
        icon=folium.Icon(color="blue", icon="map-marker"),
    ).add_to(imap.map)

if st.session_state.get("project_area_set"):
    # Créer GeoSeries pour reprojection
    gseries = gpd.GeoSeries(
        [Polygon(st.session_state.project_area)],
        crs=f"EPSG:{SESSION_DEFAULTS['epsg']}",
    )
    gseries_4326 = gseries.to_crs("EPSG:4326")
    coords_4326 = [(lat, lon) for lon, lat in gseries_4326.iloc[0].exterior.coords]
    folium.Polygon(
        locations=coords_4326,
        color="grey",
        fill=True,
        fill_opacity=0.5,
        tooltip="Project area",
    ).add_to(imap.map)

    data_path = (
        Path(__file__).parent.parent
        / "data"
        / "coral"
        / "original_benthic_coral.gpkg"
    )
    gdf_coral_filtered = load_project_coral(
        str(data_path),
        tuple(map(tuple, st.session_state.project_area)),
        st.session_state.epsg,
    )

    draw_zones(
        gdf_coral_filtered["geometry"],
        color="green",
        tooltip_prefix="Original coral zone",
        source_epsg=SESSION_DEFAULTS["epsg"],
    )

    st.session_state.friction_before_restoration = gdf_coral_filtered

    draw_zones_with_validation(
        st.session_state.restored_coral_zones,
        color_unvalidated="orange",
        color_validated="purple",
        tooltip_prefix="Restored zone",
    )

    if st.session_state.grid_angle_set:
        area_coords = np.asarray(st.session_state.project_area, dtype=float)[:4]
        offshore_idx = st.session_state.offshore_edge_idx
        offshore_midpoint = (
            area_coords[offshore_idx] + area_coords[(offshore_idx + 1) % 4]
        ) / 2
        opposite_midpoint = (
            area_coords[(offshore_idx + 2) % 4]
            + area_coords[(offshore_idx + 3) % 4]
        ) / 2
        add_map_arrow(
            project_line_to_map(
                [offshore_midpoint, opposite_midpoint], st.session_state.epsg
            ),
            color="#0057b8",
            tooltip=f"Grid X: offshore to land ({st.session_state.grid_angle:.1f}°)",
        )
        folium.PolyLine(
            project_line_to_map(
                [
                    area_coords[offshore_idx],
                    area_coords[(offshore_idx + 1) % 4],
                ],
                st.session_state.epsg,
            ),
            color="#0057b8",
            weight=5,
            opacity=0.9,
            tooltip="Offshore boundary inferred from bathymetry",
        ).add_to(imap.map)

        mainang = st.session_state.wave_mainang
        propagation_bearing = (mainang + 180) % 360
        bearing_radians = math.radians(propagation_bearing)
        center = area_coords.mean(axis=0)
        arrow_length = min(
            np.linalg.norm(opposite_midpoint - offshore_midpoint) * 0.35,
            np.linalg.norm(area_coords[1] - area_coords[0]) * 0.35,
        )
        propagation_vector = np.array(
            [math.sin(bearing_radians), math.cos(bearing_radians)]
        ) * arrow_length / 2
        wave_arrow = [
            center - propagation_vector,
            center + propagation_vector,
        ]
        add_map_arrow(
            project_line_to_map(wave_arrow, st.session_state.epsg),
            color="#d62728",
            tooltip=(
                f"Wave propagation; mainang={mainang}° nautical "
                f"(waves come from {(mainang % 360)}°)"
            ),
        )

########## Drawing tools ##########
imap.add_draw_control()

########## Displaying ##########
st_data = st_folium(
    imap.map,
    width=800,
    height=600,
    returned_objects=["last_active_drawing", "center", "zoom"],
)

# --- Step 1 : Restoration Project Design ---

st.sidebar.header("1️⃣ Restoration Project Design")

with st.sidebar.expander("📌 Select location", expanded=True):
    if not st.session_state.location_set:
        if st_data.get("last_active_drawing") is None:
            st.write(
                "Please select the location of your restoration project. You must use a marker and place it on the interactive map on the left."
            )
        elif st_data["last_active_drawing"]["geometry"]["type"] == "Point":
            st.session_state.project_lon, st.session_state.project_lat = st_data[
                "last_active_drawing"
            ]["geometry"]["coordinates"]
            utm_zone = f"{int((st.session_state.project_lon + 180) / 6) + 1}{'N' if st.session_state.project_lat >= 0 else 'S'}"
            st.session_state.epsg = get_epsg(utm_zone)
            st.session_state.location_set = True
            st.success("Location validated")
            st.info(
                f"📍 Latitude : {st.session_state.project_lat:.5f}\n📍 Longitude : {st.session_state.project_lon:.5f}\n📍 UTM Zone : {utm_zone}"
            )
            if st_data.get("center"):
                st.session_state.map_center = (
                    st_data["center"]["lat"],
                    st_data["center"]["lng"],
                )
            if st_data.get("zoom"):
                st.session_state.map_zoom = st_data["zoom"]
            st.rerun()
        else:
            st.warning(
                "You must place a marker. Please clear all drawings using the bin tool."
            )

    else:
        st.success("Location validated")
        st.info(
            f"📍 Latitude : {st.session_state.project_lat:.5f}\n"
            f"📍 Longitude : {st.session_state.project_lon:.5f}"
        )
        if st.button("🔄 Reset location", key="reset_location"):
            reset_project_state(keys_to_save=[])


########## Project area definition ##########
if st.session_state.location_set:
    with st.sidebar.expander("🌊 Define the Project area", expanded=True):
        last_drawing = st_data.get("last_active_drawing")
        if not st.session_state.project_area_set:
            if last_drawing is None or last_drawing["geometry"]["type"] != "Polygon":
                st.write(
                    "Please draw the project area with the polygon tool. You must draw a rectangle, and double-click when placing the fourth point to finish the polygon creation."
                )
                st.info(
                    "The area should include all the corals to be restored, and the land which is to be protected from flooding. \n"
                    "We recommend keeping 2 opposing sides of the area roughly parallel to the coast\n"
                    "and including at least 1 km of inland depth, and the full coral reef until the reef drop-off."
                )
            else:
                coords = last_drawing["geometry"]["coordinates"][0]

                if len(coords) - 1 == 4:  # closed polygon, 5 points (last = first)
                    # Get projected coordinates
                    polyg_gdf = gpd.GeoDataFrame(
                        geometry=[Polygon(coords)], crs="EPSG:4326"
                    )
                    polyg_gdf_proj = polyg_gdf.to_crs(f"EPSG:{st.session_state.epsg}")
                    proj_coords = list(polyg_gdf_proj.geometry.iloc[0].exterior.coords)
                    proj_polyg = Polygon(proj_coords)

                    # Force the area to be a rectangle
                    min_rect = proj_polyg.minimum_rotated_rectangle
                    project_area_coords = np.array(min_rect.exterior.coords)
                    st.session_state.project_area_set = True
                    st.session_state.project_area = project_area_coords
                    st.success("✅ Project area set")

                    if st_data.get("center"):
                        st.session_state.map_center = (
                            st_data["center"]["lat"],
                            st_data["center"]["lng"],
                        )
                    if st_data.get("zoom"):
                        st.session_state.map_zoom = st_data["zoom"]
                    st.rerun()
                else:
                    st.warning("Please draw a 4 sides polygon.")

        else:
            st.success("✅ Project area set.")
            st.info("You can now proceed to the next step.")
            if st.button("🔄 Reset project area zone", key="reset_project_area"):
                reset_project_state(
                    keys_to_save=[
                        "location_set",
                        "project_lat",
                        "project_lon",
                        "epsg",
                    ]
                )

##########  Grid orientation ##########
if st.session_state.project_area_set:
    with st.sidebar.expander("🗺️ Grid orientation", expanded=True):
        if not st.session_state.grid_angle_set and not st.session_state.orientation_requires_manual:
            bathymetry_path = config["module_path"]["bathymetry_input_path"]
            try:
                edge_elevations = sample_project_edge_bathymetry(
                    bathymetry_path,
                    tuple(map(tuple, st.session_state.project_area)),
                    st.session_state.epsg,
                )
                st.session_state.edge_bathy_elevations = edge_elevations
                offshore_edge = infer_offshore_edge(edge_elevations)
            except ValueError as error:
                st.session_state.edge_bathy_elevations = None
                st.session_state.orientation_error = str(error)
                offshore_edge = None

            if offshore_edge is None:
                st.session_state.orientation_requires_manual = True
                st.rerun()
            else:
                st.session_state.offshore_edge_idx = offshore_edge
                st.session_state.grid_angle = grid_angle_from_offshore_edge(
                    st.session_state.project_area, offshore_edge
                )
                st.session_state.grid_angle_set = True
                st.rerun()

        if st.session_state.orientation_requires_manual:
            if st.session_state.edge_bathy_elevations is None:
                st.warning(
                    "Bathymetry did not identify the offshore side. Choose it "
                    "manually; no automatic orientation was assumed."
                )
                if st.session_state.get("orientation_error"):
                    st.caption(st.session_state.orientation_error)
            else:
                values = ", ".join(
                    f"side {index + 1}: {elevation:.1f} m"
                    for index, elevation in enumerate(
                        st.session_state.edge_bathy_elevations
                    )
                )
                st.warning(
                    "Bathymetry gives similar elevations for multiple sides. "
                    f"Choose the offshore side. Edge medians: {values}."
                )
            selected_edge = st.selectbox(
                "Offshore side",
                options=[0, 1, 2, 3],
                format_func=lambda edge: f"Side {edge + 1}",
                key="manual_offshore_edge",
            )
            if st.button("✅ Use selected offshore side", key="set_offshore_side"):
                st.session_state.offshore_edge_idx = selected_edge
                st.session_state.grid_angle = grid_angle_from_offshore_edge(
                    st.session_state.project_area, selected_edge
                )
                st.session_state.grid_angle_set = True
                st.session_state.orientation_requires_manual = False
                st.rerun()

        if st.session_state.grid_angle_set:
            st.success(
                f"Grid aligned from offshore to land at "
                f"{st.session_state.grid_angle:.1f}°."
            )

##########  Wave boundary conditions ##########
if st.session_state.grid_angle_set:
    with st.sidebar.expander("🗺️ Wave boundary conditions", expanded=True):
        st.write("Adjust values and inspect both direction arrows on the map.")
        hm0 = st.slider(
            "Significant wave height Hm0 (m)",
            0.0,
            14.0,
            step=0.1,
            key="wave_hm0",
        )
        tp = st.slider(
            "Peak wave period Tp (s)", 1.0, 21.0, step=0.1, key="wave_tp"
        )
        zs0 = st.slider(
            "Initial sea level zs0 (m; tide + sea-level rise)",
            0.0,
            2.0,
            step=0.01,
            key="wave_zs0",
        )
        mainang = st.slider(
            "mainang (nautical degrees; direction waves come from)",
            0,
            360,
            step=1,
            key="wave_mainang",
        )
        st.session_state.wave_conditions = {
            "Hm0": hm0,
            "Tp": tp,
            "zs0": zs0,
            "mainang": mainang,
        }
        if not st.session_state.wave_conditions_set:
            if st.button(
                "✅ Set wave boundary conditions", key="set_wave_conditions"
            ):
                st.session_state.wave_conditions_set = True
                st.success("✅ Wave boundary conditions set")
        else:
            st.success(
                "Wave boundary conditions set; current slider values are used."
            )

        alignment = wave_alignment_with_grid(
            mainang, st.session_state.grid_angle
        )
        if hm0 <= 0:
            st.warning("Hm0 is zero: this run has no imposed wave energy.")
        if alignment < 0:
            st.warning(
                "The wave arrow points away from the landward grid direction. "
                "Check that mainang and the selected offshore side describe the "
                "intended wave approach."
            )
        if st.session_state.edge_bathy_elevations is not None:
            offshore_bed = st.session_state.edge_bathy_elevations[
                st.session_state.offshore_edge_idx
            ]
            offshore_depth = max(zs0 - offshore_bed, 0)
            st.caption(
                f"Offshore-edge median bed: {offshore_bed:.1f} m; "
                f"water depth at zs0: {offshore_depth:.1f} m."
            )
            if hm0 > offshore_depth:
                st.warning(
                    "Hm0 exceeds the estimated water depth at the offshore edge. "
                    "Review the project boundary, bathymetry datum, and wave input."
                )
        st.caption(
            "These checks flag inconsistencies visible in the inputs; they cannot "
            "guarantee numerical stability for every XBeach run."
        )

##########  Area value ($/m2) ##########
if st.session_state.wave_conditions_set:
    with st.sidebar.expander("🗺️ Area value ($/m2)", expanded=True):
        if not st.session_state.area_value_set:
            st.write("Define the area value for the simulation.")
            st.session_state.area_value = st.slider(
                "Area value ($/m2)", 100, 300, 200, 1
            )  # Programme ARAI 2 Caractérisation de la submersion marine liée aux houles cycloniques en Polynésie française
            if st.button("✅ Set area value", key="set_area_value"):
                st.session_state.area_value_set = True
                st.success("✅ Area value set")

        else:
            st.success("Area value set.")

##########  Original coral cover estimation ##########
if st.session_state.area_value_set:
    with st.sidebar.expander("🪸 Original coral cover estimation", expanded=True):
        st.write("Estimate the original coral cover within the project area.")
        original_coral_cover = st.slider(
            "Original coral cover (%)",
            min_value=0,
            max_value=100,
            value=50,
            step=10,
        )
        if st.button("✅ Set original coral cover", key="set_original_coral_cover"):
            st.session_state.original_coral_cover_set = True
            st.session_state.original_coral_cover = original_coral_cover

            st.success(f"✅ Original coral cover set to {original_coral_cover}%")

########## Future restored coral zones ##########
if st.session_state.original_coral_cover_set:
    with st.sidebar.expander(
        "🪸🔧 Define the future restored coral zones", expanded=True
    ):
        last_drawing = st_data.get("last_active_drawing")

        if not st.session_state.restored_coral_zones_set:
            if not st.session_state.restored_coral_zones_init:
                st.write(
                    "You can draw the future restored coral zones with the polygon tool, and specify the associated coral cover."
                )

                if not st.session_state.restored_coral_zone_drawn:
                    if last_drawing and last_drawing["geometry"]["type"] == "Polygon":
                        coords = last_drawing["geometry"]["coordinates"][0]
                        st.session_state.restored_coral_zones.append(
                            {
                                "coords": coords,
                                "coverage": 50,  # Default value
                                "validated": False,
                            }
                        )
                        st.session_state.restored_coral_zones_init = True
                        st.session_state.restored_coral_zone_drawn = True
                        if st_data.get("center"):
                            st.session_state.map_center = (
                                st_data["center"]["lat"],
                                st_data["center"]["lng"],
                            )
                        if st_data.get("zoom"):
                            st.session_state.map_zoom = st_data["zoom"]
                        st.rerun()
            else:
                if not st.session_state.restored_coral_zone_drawn:
                    if last_drawing and last_drawing["geometry"]["type"] == "Polygon":
                        coords = last_drawing["geometry"]["coordinates"][0]
                        st.session_state.restored_coral_zones.append(
                            {
                                "coords": coords,
                                "coverage": 50,  # Default value
                                "validated": False,
                            }
                        )
                        st.session_state.restored_coral_zone_drawn = True
                        if st_data.get("center"):
                            st.session_state.map_center = (
                                st_data["center"]["lat"],
                                st_data["center"]["lng"],
                            )
                        if st_data.get("zoom"):
                            st.session_state.map_zoom = st_data["zoom"]
                        st.rerun()
                else:
                    st.write(
                        f"🔹 Future restored coral zone {1 + st.session_state.restored_coral_zones_idx}"
                    )
                    coverage = st.selectbox(
                        f"Coverage (%)",
                        [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                    )
                    height = st.slider("Height (m)", 0.0, 2.0, 0.01)

                    if st.button(f"✅ Validate zone", key="validate_new_coral_zone"):
                        st.session_state.restored_coral_zones[
                            st.session_state.restored_coral_zones_idx
                        ]["coverage"] = coverage

                        st.session_state.restored_coral_zones[
                            st.session_state.restored_coral_zones_idx
                        ]["height"] = height

                        st.session_state.restored_coral_zones[
                            st.session_state.restored_coral_zones_idx
                        ]["validated"] = True
                        st.session_state.restored_coral_zones_idx += 1
                        st.session_state.restored_coral_zone_drawn = False
                        st.rerun()

            if st.session_state.restored_coral_zones and all(
                zone["validated"] for zone in st.session_state.restored_coral_zones
            ):
                st.info(
                    "Draw the next zone, or go to the next step with the current ones."
                )
                if st.button(
                    "✅ Confirm future restored coral zones",
                    key="confirm_new_coral_zone",
                ):
                    st.session_state.restored_coral_zones_set = True
                    st.success("All coral zones confirmed.")
                    st.rerun()

        else:
            st.success("✅ Future restored coral zones set.")
            st.info("You can now proceed to the next step.")
            if st.button(
                "🔄 Reset future restored coral zones", key="reset_new_coral_zone"
            ):
                reset_project_state(
                    keys_to_save=[
                        "location_set",
                        "project_lat",
                        "project_lon",
                        "epsg",
                        "project_area_set",
                        "project_area",
                    ]
                )


# --- Step 2 : After all zones are validated ---
if st.session_state.restored_coral_zones_set:

    # Generate the GeoJSON for the restored coral zones
    with st.spinner("🔍 Generating restored coral zones GeoJSON..."):
        st.session_state.friction_from_restoration = initialize_geojson(
            "Restored Coral Zones Frictions",
            st.session_state.epsg,
        )
        st.session_state.height_from_restoration = initialize_geojson(
            "Restored Coral Zones Heights",
            st.session_state.epsg,
        )
        for zone in st.session_state.restored_coral_zones:
            polyg_gdf = gpd.GeoDataFrame(
                geometry=[Polygon(zone["coords"])], crs="EPSG:4326"
            )
            polyg_gdf_proj = polyg_gdf.to_crs(f"EPSG:{st.session_state.epsg}")
            proj_coords = list(polyg_gdf_proj.geometry.iloc[0].exterior.coords)

            friction_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [proj_coords],
                },
                "properties": {
                    "class": "restored",
                    "friction": config[
                        "Coral cover to friction coefficient (% to dimensionless)"
                    ][str(zone["coverage"])],
                },
            }

            height_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [proj_coords],
                },
                "properties": {
                    "class": "restored",
                    "height": zone["height"],
                },
            }

            st.session_state.friction_from_restoration["features"].append(
                friction_feature
            )
            st.session_state.height_from_restoration["features"].append(height_feature)

    # Save GeoJSONs
    output_dir = Path(__file__).parent.parent / "src/models/benefits/xbeach_module"

    st.session_state.friction_before_restoration["friction"] = config[
        "Coral cover to friction coefficient (% to dimensionless)"
    ][str(st.session_state.original_coral_cover)]

    file_path = os.path.join(
        output_dir, "before_restoration", "input", "friction_before_restoration.geojson"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(
            st.session_state.friction_before_restoration[
                ["geometry", "class", "friction"]
            ].to_json(),
            f,
            indent=2,
        )

    file_path = os.path.join(
        output_dir, "after_restoration", "input", "friction_before_restoration.geojson"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(
            st.session_state.friction_before_restoration[
                ["geometry", "class", "friction"]
            ].to_json(),
            f,
            indent=2,
        )

    file_path = os.path.join(
        output_dir, "after_restoration", "input", "friction_from_restoration.geojson"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(st.session_state.friction_from_restoration, f, indent=2)

    file_path = os.path.join(
        output_dir, "after_restoration", "input", "height_from_restoration.geojson"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(st.session_state.height_from_restoration, f, indent=2)

    st.session_state.coral_geojsons_saved = True


if st.session_state.coral_geojsons_saved:
    ########## Interactions ##########
    grid_nx, grid_ny = RestorationProject.grid_dimensions(
        st.session_state.project_area,
        st.session_state.grid_angle,
    )
    grid_cells = grid_nx * grid_ny
    runtime_samples = st.session_state.simulation_runtime_samples
    estimated_seconds = estimate_runtime_seconds(grid_cells, runtime_samples)

    st.sidebar.markdown("### Simulation time estimate")
    st.sidebar.caption(
        f"Grid: {grid_nx:,} × {grid_ny:,} cells = {grid_cells:,} cells at 10 m; "
        f"{len(st.session_state.restored_coral_zones)} restored zone(s)."
    )
    st.sidebar.caption(
        "Both scenarios are computed over the full grid, so cell count is the "
        "main runtime driver; restored-zone size is not a solver shortcut."
    )
    if estimated_seconds is None:
        st.sidebar.info(
            "No completed simulation in this browser session yet, so there is not "
            "enough measured data for a reliable time estimate. The first "
            "successful run will calibrate it."
        )
    else:
        st.sidebar.info(
            f"Estimated end-to-end time: about {format_runtime(estimated_seconds)} "
            f"(scaled from {len(runtime_samples)} completed run(s) in this "
            "browser session). Treat this as an order-of-magnitude estimate; "
            "actual solver time can vary."
        )

    if st.sidebar.button("Launch simulation", key="launch_simulation"):
        st.session_state.simulation_completed = False
        st.session_state.results = []
        st.session_state.results_archive = None
        with st.status("Preparing simulation...", expanded=True) as simulation_status:
            simulation_start_time = time.monotonic()

            def report_simulation_progress(message):
                elapsed = time.monotonic() - simulation_start_time
                progress_message = f"+{elapsed:.0f}s — {message}"
                print(f"[simulation] {progress_message}", flush=True)
                simulation_status.write(progress_message)
                simulation_status.update(label=message, state="running")

            report_simulation_progress("Building the structured XBeach project grid")
            project = RestorationProject(
                start_year=2025,
                duration=10,
                location=(
                    st.session_state.project_lat,
                    st.session_state.project_lon,
                ),
                oriented_rect_coords=st.session_state.project_area,
                grid_angle=st.session_state.grid_angle,
                epsg=st.session_state.epsg,
                height=1,
                Hm0=st.session_state.wave_conditions["Hm0"],
                Tp=st.session_state.wave_conditions["Tp"],
                zs0=st.session_state.wave_conditions["zs0"],
                mainang=st.session_state.wave_conditions["mainang"],
                area_value=st.session_state.area_value,
            )
            report_simulation_progress("Loading simulation and XBeach modules")
            from src.models.benefit_cost_analysis import CoralRestorationBCA

            simulation = CoralRestorationBCA(
                config=config,
                scenario=Scenario(discount_rate=0.1),
                restoration_project=project,
            )
            simulation.load_data(progress_callback=report_simulation_progress)
            simulation.run(progress_callback=report_simulation_progress)

            report_simulation_progress("Simulation workflow completed")
            completed_runtime = time.monotonic() - simulation_start_time
            st.session_state.simulation_runtime_samples = [
                *runtime_samples,
                {
                    "grid_cells": grid_cells,
                    "runtime_seconds": completed_runtime,
                },
            ]
            report_simulation_progress("Packaging simulation results for download")
            output_paths = config["module_path"]["xbeach_paths"]
            st.session_state.results_archive = build_results_archive(
                results=st.session_state.results,
                output_paths=[
                    ("before_restoration", output_paths[0]),
                    ("after_restoration", output_paths[1]),
                ],
                metadata={
                    "runtime_seconds": completed_runtime,
                    "grid_shape_cells": [grid_nx, grid_ny],
                    "grid_cell_size_m": 10,
                    "project_location_lat_lon": [
                        st.session_state.project_lat,
                        st.session_state.project_lon,
                    ],
                    "epsg": st.session_state.epsg,
                    "grid_angle_degrees": st.session_state.grid_angle,
                    "project_area_coordinates_m": st.session_state.project_area,
                    "wave_conditions": st.session_state.wave_conditions,
                    "restored_coral_zones": st.session_state.restored_coral_zones,
                    "area_value_per_m2": st.session_state.area_value,
                },
            )
            report_simulation_progress(
                "Recorded this run to calibrate future time estimates"
            )
        st.session_state.simulation_completed = True
        st.balloons()
if st.session_state.simulation_completed:
    st.success("Simulation completed !")
    if st.session_state.results_archive is not None:
        st.download_button(
            "Download simulation results (ZIP)",
            data=st.session_state.results_archive,
            file_name="coral_restoration_simulation_results.zip",
            mime="application/zip",
            key="download_simulation_results",
        )
        st.caption(
            "The archive includes the summary, result charts, XBeach inputs, logs, "
            "and NetCDF outputs for both scenarios."
        )
    for result in st.session_state.results:
        if result["type"] == "writable":
            st.write(result["data"])
        elif result["type"] == "plottable":
            st.pyplot(result["data"])
