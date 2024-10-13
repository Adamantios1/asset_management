import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
from geopy.distance import geodesic
import folium  # Import folium for Icon support

# Function to load the CSV file
@st.cache_data
def load_data(file_path):
    # Load the data from the CSV file
    try:
        data = pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        # If utf-8 fails, try using ISO-8859-1 (Latin-1)
        data = pd.read_csv(file_path, encoding="ISO-8859-1")
    return data

# Function to filter data by radius
def filter_data_by_radius(df, input_lat, input_long, radius):
    filtered_rows = []  # Create an empty list to store filtered rows
    input_location = (input_lat, input_long)

    for index, row in df.iterrows():
        site_location = (row["LAT_DEC"], row["LONG_DEC"])
        distance = geodesic(input_location, site_location).miles

        if distance <= radius:
            filtered_rows.append(row)

    # Create a new DataFrame from the filtered rows
    filtered_df = pd.DataFrame(filtered_rows)

    return filtered_df

# Streamlit App
st.title("Site Location Viewer")

# Path to the CSV file (assuming it's in the same directory as this script)
file_path = "source_file.csv"  # Adjust this to the actual CSV file name

# Load the data
df = load_data(file_path)

# Ensure LAT_DEC and LONG_DEC columns exist and have valid values
if "LAT_DEC" not in df.columns or "LONG_DEC" not in df.columns:
    st.error("Latitude or Longitude columns (LAT_DEC, LONG_DEC) are missing from the data.")
else:
    # Remove rows with missing lat/long values
    df = df.dropna(subset=["LAT_DEC", "LONG_DEC"])

    if df.empty:
        st.warning("No valid latitude and longitude data found in the file.")
    else:
        # Initialize session state for user inputs
        if "lat_long" not in st.session_state:
            st.session_state["lat_long"] = ""
        if "radius" not in st.session_state:
            st.session_state["radius"] = 0.2

        # Create a form for user input
        with st.form(key="input_form"):
            st.write("Enter Latitude and Longitude (separated by comma) and a radius (in miles):")
            user_input = st.text_input("Enter Latitude, Longitude", st.session_state["lat_long"])
            radius = st.number_input("Radius (miles)", min_value=0.1, value=float(st.session_state["radius"]), step=0.1, format="%.1f")
           
            submit_button = st.form_submit_button(label="Search")

        # Process form submission
        if submit_button:
            # Parse user input
            if ',' in user_input:
                input_lat_long = user_input.split(',')
                try:
                    input_lat = float(input_lat_long[0].strip())
                    input_long = float(input_lat_long[1].strip())

                    # Store in session state
                    st.session_state["lat_long"] = user_input
                    st.session_state["radius"] = radius

                    # Filter the data based on input
                    filtered_df = filter_data_by_radius(df, input_lat, input_long, radius)

                    if filtered_df.empty:
                        st.warning("No sites found within the specified radius.")
                    else:
                        # Create a `leafmap` map
                        map_center = [input_lat, input_long]
                        m = leafmap.Map(center=map_center, zoom=10)

                        # Add user location marker (green icon)
                        user_icon = folium.Icon(icon="user", prefix="fa", color="green")
                        m.add_marker(location=(input_lat, input_long), popup="User Location", icon=user_icon)

                        # Loop through the dataframe and add each location to the map (blue icons for cell sites)
                        for _, row in filtered_df.iterrows():
                            lat, long = row["LAT_DEC"], row["LONG_DEC"]
                            # Detailed popup information for each site
                            popup_info = f"""
                            <strong>Site Name:</strong> {row["SITE_NAME"]}<br>
                            <strong>Owner:</strong> {row["OWNER"]}<br>
                            <strong>FCC ASR:</strong> {row["FCC_ASR"]}<br>
                            <strong>FAA Study:</strong> {row["FAA_STUDY"]}<br>
                            <strong>Structure Type:</strong> {row["STRUCTURE TYPE"]}<br>
                            <strong>Status:</strong> {row["STATUS"]}<br>
                            <strong>Address:</strong> {row["ADDRESS"]}, {row["CITY"]}, {row["STATE"]}, {row["ZIP"]}<br>
                            <strong>Built Date:</strong> {row["BUILT_DATE"]}<br>
                            <strong>Site Elevation (ft):</strong> {row["SITE_EL_FT"]}<br>
                            <strong>AMSL (ft):</strong> {row["AMSL_FT"]}<br>
                            <strong>Height (ft):</strong> {row["STR_HT_FT"]}
                            """
                            site_icon = folium.Icon(icon="wifi", prefix="fa", color="blue")
                            m.add_marker(location=(lat, long), popup=popup_info, icon=site_icon)

                        # Display the map in Streamlit
                        m.to_streamlit(height=600)

                        # Display the filtered data
                        st.write("Nearby Cell Sites:")
                        st.dataframe(filtered_df)

                except ValueError:
                    st.error("Invalid input. Please enter valid latitude and longitude.")
            else:
                st.error("Please enter both latitude and longitude separated by a comma.")
