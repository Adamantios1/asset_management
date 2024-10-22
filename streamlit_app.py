import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
import geohash
from geopy.distance import geodesic
import folium
import requests

# API Key for Lightbox
API_KEY = 'j0dWrg4MZT6Glhc7obZCeJrEAAAF6s4B'

# Function to load the CSV or Excel file
@st.cache_data
def load_data(file_path, file_type="csv"):
    if file_type == "csv":
        try:
            data = pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            # If utf-8 fails, try using ISO-8859-1 (Latin-1)
            data = pd.read_csv(file_path, encoding="ISO-8859-1")
    elif file_type == "excel":
        data = pd.read_excel(file_path)
    return data

# Function to geohash the entire dataframe
def add_geohashes(df, lat_col="LAT_DEC", long_col="LONG_DEC", precision=6):
    df["geohash"] = df.apply(lambda row: geohash.encode(row[lat_col], row[long_col], precision=precision), axis=1)
    return df

# Function to call the Lightbox API and extract address, building height, footprint area, and ground elevation
def get_lightbox_info(lat, long):
    try:
        # Create the API URL with reversed coordinates and properly encoded wkt
        url = f"https://api.lightboxre.com/v1/structures/us/geometry?wkt=POINT%28{long}%20{lat}%29&bufferDistance=10&bufferUnit=ft&limit=1&offset=0"
        headers = {
            "accept": "application/json",
            "x-api-key": API_KEY
        }
        
        # Call the Lightbox API
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # Extract address, building height, footprint area, and ground elevation
        if data and "structures" in data and len(data["structures"]) > 0:
            structure = data["structures"][0]
            location = structure["location"]
            street_address = location.get("streetAddress", "N/A")
            city = location.get("locality", "N/A")
            state = location.get("regionCode", "N/A")
            postal_code = location.get("postalCode", "N/A")
            address = f"{street_address}, {city}, {state} {postal_code}"
            
            # Extract and convert building height (meters to feet)
            height_info = structure["physicalFeatures"]["height"]
            building_height_meters = height_info["average"] if height_info else 0
            building_height_feet = round(building_height_meters * 3.28, 2) if building_height_meters else "N/A"
            
            # Extract footprint area and convert to square feet
            footprint_area_m2 = structure["physicalFeatures"]["area"].get("footprintArea", 0)
            footprint_area_sqft = round(footprint_area_m2 * 10.764, 2) if footprint_area_m2 else "N/A"
            
            # Extract ground elevation (average) and convert to feet
            ground_elevation_avg_meters = structure["physicalFeatures"]["groundElevation"].get("average", 0)
            ground_elevation_avg_feet = round(ground_elevation_avg_meters * 3.28, 2) if ground_elevation_avg_meters else "N/A"

            return address, building_height_feet, footprint_area_sqft, ground_elevation_avg_feet
        else:
            return "N/A", "N/A", "N/A", "N/A"
    
    except Exception as e:
        st.error(f"Error calling Lightbox API: {str(e)}")
        return "N/A", "N/A", "N/A", "N/A"

# Function to find neighboring geohashes
def find_sites_within_radius_by_geohash(df, input_lat, input_long, radius, geohash_precision=6):
    # Compute geohash for the input location
    input_geohash = geohash.encode(input_lat, input_long, precision=geohash_precision)
    
    # Find neighbors geohashes for the input location
    geohash_neighbors = geohash.neighbors(input_geohash) + [input_geohash]
    
    # Filter sites that match the geohash or its neighbors
    filtered_df = df[df["geohash"].isin(geohash_neighbors)]
    
    # Filter further by distance within the exact radius
    filtered_rows = []
    input_location = (input_lat, input_long)
    for _, row in filtered_df.iterrows():
        site_location = (row["LAT_DEC"], row["LONG_DEC"])
        distance = geodesic(input_location, site_location).miles
        if distance <= radius:
            filtered_rows.append(row)

    return pd.DataFrame(filtered_rows)

# Streamlit App
st.title("Optimized Site Location Viewer")

# Load the data for nearby site search
file_path = "source_file.csv"  # Adjust this to the actual CSV file name
df = load_data(file_path)

# Ensure LAT_DEC and LONG_DEC columns exist and have valid values in the main data file
if "LAT_DEC" not in df.columns or "LONG_DEC" not in df.columns:
    st.error("Latitude or Longitude columns (LAT_DEC, LONG_DEC) are missing from the data.")
else:
    # Remove rows with missing lat/long values
    df = df.dropna(subset=["LAT_DEC", "LONG_DEC"])
    
    # Geohash the dataset
    df = add_geohashes(df)

    if df.empty:
        st.warning("No valid latitude and longitude data found in the file.")
    else:
        # Feature 1: Batch Search (moved first)
        st.header("Batch Search for Multiple Locations")

        # Add a radius input field for the batch search
        batch_radius = st.number_input("Radius for Batch Search (miles)", min_value=0.1, value=0.1, step=0.1, format="%.1f")

        # File upload widget
        uploaded_file = st.file_uploader("Upload a CSV or Excel file with lat/long for batch search", type=["csv", "xlsx"])
        if uploaded_file is not None:
            # Determine the file type
            file_type = "csv" if uploaded_file.name.endswith(".csv") else "excel"
            
            # Load the uploaded data
            uploaded_data = load_data(uploaded_file, file_type)

            # Check if required columns exist
            if "LAT_DEC" not in uploaded_data.columns or "LONG_DEC" not in uploaded_data.columns:
                st.error("The uploaded file must contain 'LAT_DEC' and 'LONG_DEC' columns.")
            else:
                # Process batch search
                st.write(f"Processing batch search for {len(uploaded_data)} locations...")

                results = []
                for index, row in uploaded_data.iterrows():
                    input_lat = row["LAT_DEC"]
                    input_long = row["LONG_DEC"]
                    nearby_sites_count = len(find_sites_within_radius_by_geohash(df, input_lat, input_long, batch_radius))
                    
                    # Call Lightbox API for address, building height, footprint area, and ground elevation
                    address, building_height, footprint_area, ground_elevation = get_lightbox_info(input_lat, input_long)
                    
                    results.append({
                        "Latitude": input_lat,
                        "Longitude": input_long,
                        "Nearby Sites Count": nearby_sites_count,
                        "Address": address,
                        "Building Height (ft)": building_height,
                        "Footprint Area (sq ft)": footprint_area,
                        "Ground Elevation (avg, ft)": ground_elevation
                    })

                # Convert results to a DataFrame
                results_df = pd.DataFrame(results)
                
                # Display the results as a table
                st.write("Batch Search Results:")
                st.dataframe(results_df)

        # Feature 2: Single Location Search (moved second)
        st.header("Single Location Search")
        if "lat_long" not in st.session_state:
            st.session_state["lat_long"] = ""
        if "radius" not in st.session_state:
            st.session_state["radius"] = 0.2  # Initialize as float

        # Create a form for single-location search input
        with st.form(key="input_form"):
            st.write("Enter Latitude and Longitude (separated by comma) and a radius (in miles):")
            user_input = st.text_input("Enter Latitude, Longitude", st.session_state["lat_long"])
            radius = st.number_input("Radius (miles)", min_value=0.1, value=float(st.session_state["radius"]), step=0.1, format="%.1f")
            submit_button = st.form_submit_button(label="Search")

        # Process form submission for single location search
        if submit_button and ',' in user_input:
            input_lat_long = user_input.split(',')
            try:
                input_lat = float(input_lat_long[0].strip())
                input_long = float(input_lat_long[1].strip())

                st.session_state["lat_long"] = user_input
                st.session_state["radius"] = radius

                # Find nearby sites using geohashing
                nearby_sites = find_sites_within_radius_by_geohash(df, input_lat, input_long, radius)
                nearby_sites_count = len(nearby_sites)

                st.success(f"Found {nearby_sites_count} nearby sites within {radius} miles.")

                # Call Lightbox API for address and building height
                address, building_height, footprint_area, ground_elevation = get_lightbox_info(input_lat, input_long)
                st.write(f"Address: {address}")
                st.write(f"Building Height: {building_height} feet")
                st.write(f"Footprint Area: {footprint_area} sq ft")
                st.write(f"Ground Elevation (average): {ground_elevation} meters")

                # Display the map for the single location search
                if nearby_sites_count > 0:
                    # Create the map
                    m = leafmap.Map(center=[input_lat, input_long], zoom=10)

                    # Add user location marker (green icon)
                    user_icon = folium.Icon(icon="user", prefix="fa", color="green")
                    m.add_marker(location=(input_lat, input_long), popup="User Location", icon=user_icon)

                    # Add nearby site markers (blue antenna icon)
                    for _, row in nearby_sites.iterrows():
                        lat, long = row["LAT_DEC"], row["LONG_DEC"]
                        popup_info = f"""
                        <strong>Site Name:</strong> {row["SITE_NAME"]}<br>
                        <strong>Owner:</strong> {row["OWNER"]}<br>
                        <strong>FCC ASR:</strong> {row["FCC_ASR"]}<br>
                        <strong>Structure Type:</strong> {row["STRUCTURE TYPE"]}<br>
                        <strong>Status:</strong> {row["STATUS"]}<br>
                        <strong>Address:</strong> {row["ADDRESS"]}, {row["CITY"]}, {row["STATE"]}, {row["ZIP"]}
                        """
                        site_icon = folium.Icon(icon="wifi", prefix="fa", color="blue")
                        m.add_marker(location=(lat, long), popup=popup_info, icon=site_icon)

                    # Display the map
                    m.to_streamlit(height=600)

                    # Display the filtered data in a table
                    st.write("Nearby Sites:")
                    st.dataframe(nearby_sites)

            except ValueError:
                st.error("Invalid input. Please enter valid latitude and longitude.")
