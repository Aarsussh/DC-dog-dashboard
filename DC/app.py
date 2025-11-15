import base64
import io
import pandas as pd
import dash
from dash import Dash, dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP]) #creating the dash setup
server = app.server #server is used after being deployed



# --------------------------------------------------------
#   File Upload UI
# --------------------------------------------------------
app.layout = dbc.Container([        #making a simple layout for the entire page
    html.H2("📊 Physiological Dashboard with Animated GPS Map",  #title of the dasboard
            className="text-center my-4"),

    dcc.Upload(  #creating a area for drag and drop of datasets
        id='upload-data',
        children=html.Div(['📁 Drag & Drop or ', html.A('Select File (.csv/.xlsx)')]),
        style={
            'width': '100%', 'height': '80px', 'lineHeight': '80px',
            'borderWidth': '2px', 'borderStyle': 'dashed',
            'borderRadius': '10px', 'textAlign': 'center', 'margin': '20px'
        },
        multiple=False
    ),

    html.Div(id='file-info', className='text-center fw-bold my-3'), #shows the file name(dataset)
    html.Hr(),

    html.Div(id='data-preview', className='my-3'), #shows the first ten rows of data

    html.Div(id='indicator-cards', className='d-flex flex-wrap justify-content-center'), #box for average value health indication

    dcc.Graph(id='time-series-graph') #just the graph which was made earlier
])

#parseing the uploaded file
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',') #splits it into type plus actual data
    decoded = base64.b64decode(content_string) #jus decoding the contents of the file

    try:
        if filename.endswith('.csv'):     #finding the type of file from filename and reading it accrodingly
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None, f"❌ Unsupported file type: {filename}"
    except Exception as e:
        return None, f"⚠️ Error reading file: {e}"

    return df, None


# --------------------------------------------------------
#   Helper: Traffic signal logic
# --------------------------------------------------------
def get_indicator(param, value): #decides the color of the marker and health status based on the data
    if "temp" in param:
        if 36 <= value <= 37.5: return "green", "Normal"
        elif 37.5 < value <= 38.5: return "orange", "Caution"
        else: return "red", "Critical"

    elif "heart" in param or "hr" in param or "bpm" in param or "pulse" in param:
        if 60 <= value <= 100: return "green", "Normal"
        elif 100 < value <= 120 or 50 <= value < 60: return "orange", "Caution"
        else: return "red", "Critical"

    elif "spo2" in param or "oxygen" in param or "o2" in param:
        if value >= 95: return "green", "Normal"
        elif 90 <= value < 95: return "orange", "Caution"
        else: return "red", "Critical"

    return "gray", "Unknown"

#   MAIN CALLBACK

@app.callback(
    [Output('file-info', 'children'),
     Output('data-preview', 'children'),
     Output('indicator-cards', 'children'),
     Output('time-series-graph', 'figure')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)

def update_dashboard(contents, filename):

    if contents is None:    
        return "", "", "", px.scatter()          #if no file show nothing

    df, err = parse_contents(contents, filename)
    if err:
        return err, "", "", px.scatter()

    df.columns = [c.lower().strip() for c in df.columns] #making the names simpler

    # ------------------ Data Preview ------------------
    table = dash_table.DataTable(       #shows first 10 rows
        data=df.head(10).to_dict('records'),
        columns=[{"name": i, "id": i} for i in df.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'padding': '8px'},
        page_size=10
    )

    # ------------------ Indicator Cards ------------------
    cards = []
    for col in df.columns: #iterating through each column
        if any(x in col for x in ['temp', 'heart', 'hr', 'spo2', 'oxygen','o2','pulse','bpm']):
            mean_val = df[col].mean() #taking the mean
            color, status = get_indicator(col, mean_val)   #checking color
            cards.append(
                dbc.Card(            #creating the card with the color and status and mean value
                    dbc.CardBody([
                        html.H4(col.capitalize(), className='card-title'),
                        html.H2(f"{mean_val:.1f}", className='card-text'),
                        html.P(status, style={'color': color, 'fontWeight': 'bold'})
                    ]),
                    className="m-2 text-center shadow",
                    style={'width': '18rem', 'borderLeft': f'8px solid {color}'}
                )
            )

    # Animated GPS Map Logic
    #if these three cols exist then only the map will be made else a graph will be made
    time_col = next((c for c in df.columns if 'time' in c or 'timestamp' in c), None)
    lat_col  = next((c for c in df.columns if c in ['lat', 'latitude']), None)
    lon_col  = next((c for c in df.columns if c in ['lon', 'long', 'longitude', 'lng']), None)

    # find physiological column for color
    param_cols = [c for c in df.columns if any(x in c for x in ['temp', 'heart', 'hr', 'spo2', 'oxygen','o2','bpm','pulse'])]
    color_col = param_cols[0] if param_cols else None

    # -------- Animated Map --------
    if lat_col and lon_col and time_col and color_col:

        df["signal_color"], df["signal_status"] = zip(*df.apply(
            lambda row: get_indicator(color_col, row[color_col]), #calulating color for every row
            axis=1
        ))

        fig = px.scatter_mapbox(  #makes a map
            df,
            lat=lat_col,
            lon=lon_col,
            color="signal_color",
            animation_frame=time_col,
            hover_name=time_col,
            hover_data={color_col: True, "signal_status": True},
            zoom=11,
            height=550,
            title="🌍 Animated GPS Movement with Health Status",
            color_discrete_map={
                "green": "green",
                "orange": "orange",
                "red": "red",
                "gray": "gray"
            }
        )
        fig.update_traces(marker=dict(size=20)) #setting the size of the marker
        '''
        fig.add_trace(              #had added a trail earlier
            go.Scattermapbox(
                lat=df[lat_col],
                lon=df[lon_col],
                mode="lines",
                line=dict(width=4,color="blue"),
                name="Trail"
            )
        )'''
        for frame in fig.frames:  #centering the map at the first coordinate for every dataset
            frame.layout = go.Layout(
            mapbox=dict(
                center=dict(
                    lat=float(df[lat_col].iloc[0]),
                    lon=float(df[lon_col].iloc[0])
                ),
                zoom=11,
            )
        )

        fig.update_layout(
            mapbox_style="open-street-map", #style of map
            mapbox=dict(
                center={"lat": df[lat_col].iloc[0], "lon": df[lon_col].iloc[0]},
                zoom=11
            ),
            uirevision = 'constant'
        )

        fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 300  #setting the frame and time duration
        fig.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 200


    else:
        # fallback to time-series            #if map cant be made then graph
        y_cols = [c for c in df.columns if c != time_col]
        fig = px.line(df, x=time_col, y=y_cols,
                      title="📈 Time-Series Data") if time_col else px.line(df[y_cols])

    return (
        f"✅ Uploaded: {filename}",
        table,
        dbc.Row(cards, justify='center'),
        fig
    )


# --------------------------------------------------------
#   Run Server
# --------------------------------------------------------
if __name__ == '__main__':  #start the local server
    app.run(debug=True)
