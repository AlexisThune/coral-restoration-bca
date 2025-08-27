import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shapely.geometry import Point, Polygon
from streamlit_folium import st_folium

from src.config import load_config
from src.models.benefit_cost_analysis import CoralRestorationBCA
from src.utils.technical_functions import get_epsg, n_closest_points
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
}


def init_session_state(defaults):
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_project_state(keys_to_save):
    keys_to_save += ["map_center", "map_zoom"]
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


@st.cache_data(show_spinner="🔍 Loading coral benthic map...")
def load_benthic_map(data_path, epsg_code):
    with open(data_path) as f:
        data = json.load(f)
        gdf = gpd.GeoDataFrame.from_features(data["features"])
        gdf.crs = "EPSG:4326"
        gdf_proj = gdf.to_crs(f"EPSG:{epsg_code}")
        gdf_coral = gdf_proj[gdf_proj["class"] == "Coral/Algae"]
        return gdf_coral


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
st.set_page_config(page_title="BCA Model for coral restoration projects", layout="wide")
st.title("BCA Model for coral restoration projects")
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

########## Initialize GeoJSONs with loading spinner ##########
if "original_coral_geojson_loaded" not in st.session_state:
    data_path = (
        Path(__file__).parent.parent / "data" / "coral" / "original_benthic_map.geojson"
    )
    gdf_coral = load_benthic_map(data_path, st.session_state.epsg)
    st.session_state.original_coral_geojson = gdf_coral

    st.session_state.original_coral_geojson_loaded = True
    st.rerun()  # Sort du spinner proprement
else:
    gdf_coral = st.session_state.original_coral_geojson

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

    ### Filter the coral cover GeoDataFrame to the project area
    project_area = Polygon(st.session_state.project_area)
    gdf_coral_filtered = gdf_coral[gdf_coral.intersects(project_area)].copy()

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
        if not st.session_state.grid_angle_set:
            if st_data.get("last_active_drawing") is None:
                st.write(
                    "Place a marker on the middle of the offshore side of the grey rectangle."
                )

            elif st_data["last_active_drawing"]["geometry"]["type"] == "Point":
                # User estimation
                user_lon, user_lat = st_data["last_active_drawing"]["geometry"][
                    "coordinates"
                ]

                user_point = gpd.GeoDataFrame(
                    geometry=[Point(user_lon, user_lat)], crs="EPSG:4326"
                )
                user_point_proj = user_point.to_crs(f"EPSG:{st.session_state.epsg}")
                proj_coords = user_point_proj.geometry.iloc[0].coords[0]

                # Deduction of the offshore side
                offshore_points = n_closest_points(
                    proj_coords, st.session_state.project_area[:4], n=2
                )
                offshore_midpoint = np.mean(offshore_points, axis=0)

                # Computation of grid angle
                area_center = np.mean(st.session_state.project_area[:4], axis=0)
                dx, dy = (
                    area_center[0] - offshore_midpoint[0],
                    area_center[1] - offshore_midpoint[1],
                )
                st.session_state.grid_angle = math.degrees(math.atan2(dy, dx))

                st.success("Grid oriented")
                st.session_state.grid_angle_set = True
        else:
            st.success("Grid oriented.")


##########  Wave boundary conditions ##########
if st.session_state.grid_angle_set:
    with st.sidebar.expander("🗺️ Wave boundary conditions", expanded=True):
        if not st.session_state.wave_conditions_set:
            st.write("Define the wave boundary conditions for the simulation.")
            st.session_state.wave_conditions = {
                "Hm0": st.slider("Significant wave height (Hm0)", 0.0, 14.0, 8.0, 0.1),
                "Tp": st.slider("Peak wave period (Tp)", 1.0, 21.0, 11.0, 0.1),
                "zs0": st.slider(
                    "Initial sea level (zs0). Include both tide and Sea Level Rise",
                    0.0,
                    2.0,
                    0.0,
                    0.01,
                ),
                "mainang": st.slider(
                    "Main angle of wave direction (mainang) in nautical degrees",
                    0,
                    360,
                    270,
                    1,
                ),
            }
            if st.button("✅ Set wave boundary conditions", key="set_wave_conditions"):
                st.session_state.wave_conditions_set = True
                st.success("✅ Wave boundary conditions set")

        else:
            st.success("Wave boundary conditions set.")

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

            if all(zone["validated"] for zone in st.session_state.restored_coral_zones):
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
    if st.sidebar.button("Launch simulation", key="launch_simulation"):
        with st.spinner("Simulation running..."):
            simulation = CoralRestorationBCA(
                config=config,
                scenario=Scenario(discount_rate=0.1),
                restoration_project=RestorationProject(
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
                ),
            )
            simulation.load_data()
            simulation.run()

        st.session_state.simulation_completed = True
        st.balloons()
if st.session_state.simulation_completed:
    st.success("Simulation completed !")
    for result in st.session_state.results:
        if result["type"] == "writable":
            st.write(result["data"])
        elif result["type"] == "plottable":
            st.pyplot(result["data"])
