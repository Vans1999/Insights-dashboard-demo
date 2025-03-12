import dash
from dash import dcc, html, callback, Input, Output, State, ctx, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import pymongo
from datetime import datetime, timedelta
import json
import os
import uuid
import base64
from dash.exceptions import PreventUpdate
import flask
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
import dash_auth
import boto3
import hmac
import hashlib
# Import Dash Draggable
import dash_draggable

# Initialize the Dash app with Bootstrap styling and suppress callback exceptions
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True  # Add this to handle dynamic layouts
)
server = app.server

# Set up Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)

# Configure these values from your Cognito setup (same as Streamlit version)
COGNITO_USER_POOL_ID = "ap-southeast-2_Zezx8S9cn"
COGNITO_CLIENT_ID = "578tc1t3a5gmfe7fqqju3hdopj"
COGNITO_CLIENT_SECRET = "1mlhgcqhtihirabgrm3pal3etc3huh86errlc7spr7k6qhkafou4"

# Create a User class for Flask-Login
class User(UserMixin):
    def __init__(self, username):
        self.id = username

# User loader callback for Flask-Login
@login_manager.user_loader
def load_user(username):
    return User(username)

# MongoDB connection
client = pymongo.MongoClient("mongodb+srv://vans1:Vans123456789!@insights.3jr7t.mongodb.net/?retryWrites=true&w=majority&appName=Insights",
    tls=True,
    tlsAllowInvalidCertificates=False,
    serverSelectionTimeoutMS=5000
)
db = client["insights_live"]

# Define color palettes (same as before)
COLOR_PALETTES = {
    "vibrant": ["#FF9E00", "#12A4D9", "#9B4DCA", "#DD4124", "#7CB518"],
    "pastel": ["#FFD3B5", "#B5DEFF", "#D5C5FC", "#BCDFC9", "#FEBFB3"],
    "corporate": ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD"]
}
if not os.path.exists("client_dashboards.json"):
    with open("client_dashboards.json", "w") as f:
        f.write('{"dashboards": [], "graphs": [], "layouts": []}')
    print("Created empty client_dashboards.json file")

if not os.path.exists("user_permissions.json"):
    with open("user_permissions.json", "w") as f:
        f.write('{"users": {}}')
    print("Created empty user_permissions.json file")
# Helper function to create secret hash (from Streamlit version)
def get_secret_hash(username):
    msg = username + COGNITO_CLIENT_ID
    if COGNITO_CLIENT_SECRET:
        dig = hmac.new(
            bytes(COGNITO_CLIENT_SECRET, 'utf-8'), 
            msg=bytes(msg, 'utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    return None

# Login function (from Streamlit version)
def login_user_cognito(username, password):
    try:
        # Create Cognito client
        cognito_client = boto3.client('cognito-idp', region_name='ap-southeast-2')
        
        auth_params = {
            'USERNAME': username,
            'PASSWORD': password,
        }
        
        # Add secret hash if client secret is configured
        if COGNITO_CLIENT_SECRET:
            auth_params['SECRET_HASH'] = get_secret_hash(username)
        
        response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters=auth_params
        )
        return True, "Login successful"
    except Exception as e:
        return False, str(e)

# Load client dashboards from file or create default
def load_client_data():
    try:
        if os.path.exists("client_dashboards.json"):
            with open("client_dashboards.json", "r") as f:
                return json.load(f)
        return {"dashboards": [], "graphs": [], "layouts": []}
    except Exception as e:
        print(f"Error loading dashboards: {e}")
        return {"dashboards": [], "graphs": [], "layouts": []}

def save_client_data(data):
    try:
        with open("client_dashboards.json", "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print(f"Error saving dashboards: {e}")
        return False

# Date parsing function (improved from previous code)
def parse_date(date_str):
    """Parse a date string in various formats."""
    if not date_str:
        return None
        
    if not isinstance(date_str, str):
        return date_str  # If it's already a datetime or date object
    
    try:
        # Try ISO format first (most common in web apps)
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Try simple YYYY-MM-DD format
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            try:
                # If there's a 'T' separator, extract just the date part
                if 'T' in date_str:
                    return datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
                raise ValueError("Unrecognized date format")
            except ValueError:
                print(f"Failed to parse date: {date_str}")
                return None

# Create a new dashboard
def create_dashboard(name, description=""):
    dashboard_id = str(uuid.uuid4())
    
    dashboard = {
        "id": dashboard_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "items": []
    }
    
    # Load existing data
    client_data = load_client_data()
    client_data["dashboards"].append(dashboard)
    save_client_data(client_data)
    
    return dashboard_id

# Update dashboard metadata
def update_dashboard(dashboard_id, name=None, description=None):
    client_data = load_client_data()
    
    for dashboard in client_data["dashboards"]:
        if dashboard["id"] == dashboard_id:
            if name is not None:
                dashboard["name"] = name
            if description is not None:
                dashboard["description"] = description
            dashboard["updated_at"] = datetime.now().isoformat()
            break
    
    save_client_data(client_data)
    return True

# Add a graph to a dashboard
def add_to_dashboard(graph_data, dashboard_id, heading=None, description=None, size="medium"):
    graph_id = str(uuid.uuid4())
    graph_data["id"] = graph_id
    
    if heading:
        graph_data["heading"] = heading
    if description:
        graph_data["description"] = description
    
    # Add size property for resizing functionality
    graph_data["size"] = size
    
    graph_data["created_at"] = datetime.now().isoformat()
    graph_data["updated_at"] = datetime.now().isoformat()
    
    # Load existing data
    client_data = load_client_data()
    
    # Add graph to graphs list
    client_data["graphs"].append(graph_data)
    
    # Add graph ID to dashboard items
    for dashboard in client_data["dashboards"]:
        if dashboard["id"] == dashboard_id:
            dashboard["items"].append(graph_id)
            dashboard["updated_at"] = datetime.now().isoformat()
            break
    
    # Add to layout
    layout_item = {
        "id": graph_id,
        "type": "graph",
        "order": len(client_data.get("layouts", [])),
        "dashboard_id": dashboard_id
    }
    
    if "layouts" not in client_data:
        client_data["layouts"] = []
    
    client_data["layouts"].append(layout_item)
    
    # Save changes
    save_client_data(client_data)
    
    return graph_id

# Remove an item from dashboard
def remove_from_dashboard(item_id):
    client_data = load_client_data()
    
    # Remove from graphs if it's a graph
    client_data["graphs"] = [g for g in client_data["graphs"] if g["id"] != item_id]
    
    # Remove from layout
    client_data["layouts"] = [l for l in client_data["layouts"] if l["id"] != item_id]
    
    # Remove from dashboard items
    for dashboard in client_data["dashboards"]:
        if "items" in dashboard and item_id in dashboard["items"]:
            dashboard["items"].remove(item_id)
            dashboard["updated_at"] = datetime.now().isoformat()
    
    # Reorder remaining items
    for i, item in enumerate(sorted(client_data["layouts"], key=lambda x: x.get("order", 0))):
        item["order"] = i
    
    # Save changes
    save_client_data(client_data)
    return True

# Update the layout order based on drag-and-drop
def update_layout_order_from_drag(dashboard_id, layout_order):
    client_data = load_client_data()
    layouts = [item for item in client_data.get("layouts", []) 
              if "dashboard_id" in item and item["dashboard_id"] == dashboard_id]
    
    # Update order based on the new layout
    for item_id, new_order in layout_order.items():
        for layout in layouts:
            if layout["id"] == item_id:
                layout["order"] = new_order
                break
    
    # Save changes
    save_client_data(client_data)
    return True

# Update graph metadata
def update_graph_metadata(graph_id, heading=None, description=None, size=None):
    client_data = load_client_data()
    
    for graph in client_data["graphs"]:
        if graph["id"] == graph_id:
            if heading is not None:
                graph["heading"] = heading
            if description is not None:
                graph["description"] = description
            if size is not None:
                graph["size"] = size
                
            graph["updated_at"] = datetime.now().isoformat()
            break
    
    # Save changes
    save_client_data(client_data)
    return True

# Add a metric to a dashboard
def add_metric_to_dashboard(metric_data, dashboard_id, heading=None, description=None):
    graph_id = str(uuid.uuid4())
    metric_data["id"] = graph_id
    metric_data["type"] = "metric"
    
    if heading:
        metric_data["heading"] = heading
    if description:
        metric_data["description"] = description
    
    metric_data["created_at"] = datetime.now().isoformat()
    metric_data["updated_at"] = datetime.now().isoformat()
    
    # Load existing data
    client_data = load_client_data()
    
    # Add metric to graphs list
    client_data["graphs"].append(metric_data)
    
    # Add graph ID to dashboard items
    for dashboard in client_data["dashboards"]:
        if dashboard["id"] == dashboard_id:
            dashboard["items"].append(graph_id)
            dashboard["updated_at"] = datetime.now().isoformat()
            break
    
    # Add to layout
    layout_item = {
        "id": graph_id,
        "type": "graph",
        "order": len(client_data.get("layouts", [])),
        "dashboard_id": dashboard_id
    }
    
    if "layouts" not in client_data:
        client_data["layouts"] = []
    
    client_data["layouts"].append(layout_item)
    
    # Save changes
    save_client_data(client_data)
    
    return graph_id

# Create a metric card
def create_metric_card(title, value, previous_value=None, is_percentage=False):
    delta = None
    delta_color = "normal"
    
    if previous_value is not None and previous_value != 0:
        delta = ((value - previous_value) / previous_value) * 100
        delta_color = "normal" if delta >= 0 else "inverse"
    
    if is_percentage:
        format_value = f"{value:.2f}%"
        delta_suffix = "%"
    else:
        format_value = format(int(value), ',') if isinstance(value, (int, float)) else value
        delta_suffix = "%"
    
    delta_value = f"{delta:.2f}{delta_suffix}" if delta is not None else None
    
    return {
        "title": title,
        "value": format_value,
        "delta": delta_value,
        "delta_color": delta_color
    }

# Helper functions to work with MongoDB
def get_experience_id_field(test_document):
    """Determine which field contains the experienceId"""
    if test_document and "device" in test_document and isinstance(test_document["device"], dict) and "experienceId" in test_document["device"]:
        return "device.experienceId"
    else:
        return "experienceId"

def get_item_name_field(test_document):
    """Determine which field contains the itemName"""
    if test_document and "item" in test_document and isinstance(test_document["item"], dict) and "itemName" in test_document["item"]:
        return "item.itemName"
    else:
        return "itemName"

def get_event_name_field(test_document):
    """Determine which field contains the event name"""
    if test_document and "location" in test_document and isinstance(test_document["location"], dict) and "name" in test_document["location"]:
        return "location.name"
    else:
        return "name"

# Build MongoDB query based on selected filters
def build_query(org_id, app_id, exp_id=None, selected_items=None, event_type=None, start_date=None, end_date=None):
    """Build a MongoDB query based on selected filters"""
    # Start with basic query
    query = {"orgId": org_id, "appId": app_id}
    
    # Get a sample document to determine field locations
    test_document = db.events.find_one({"orgId": org_id, "appId": app_id})
    
    # Add experienceId if provided
    if exp_id:
        exp_field = get_experience_id_field(test_document)
        if exp_id == "No Experience":
            # Look for events with null experienceId
            query["$or"] = [
                {exp_field: None},
                {exp_field: {"$exists": False}}
            ]
        else:
            query[exp_field] = exp_id
    
    # Add event type if provided
    if event_type:
        event_field = get_event_name_field(test_document)
        query[event_field] = event_type
    
    # Add items if provided
    if selected_items and len(selected_items) > 0:
        item_field = get_item_name_field(test_document)
        query[item_field] = {"$in": selected_items}
    
    # Add date filters with improved parsing
    if start_date:
        start_date_obj = parse_date(start_date)
        if start_date_obj:
            if hasattr(start_date_obj, 'date'):
                start_date_obj = start_date_obj.date()
            query["createdAt"] = {"$gte": datetime.combine(start_date_obj, datetime.min.time())}
    
    if end_date:
        end_date_obj = parse_date(end_date)
        if end_date_obj:
            if hasattr(end_date_obj, 'date'):
                end_date_obj = end_date_obj.date()
            
            if "createdAt" in query:
                query["createdAt"]["$lte"] = datetime.combine(end_date_obj, datetime.max.time())
            else:
                query["createdAt"] = {"$lte": datetime.combine(end_date_obj, datetime.max.time())}
    
    return query, test_document

# Filter graph data by date range
def filter_graph_by_dates(graph_data, start_date, end_date):
    """Filter graph data based on date range"""
    # Only filter if the graph type supports date filtering
    if graph_data["type"] not in ["time_series", "timeline", "bar_chart", "pie_chart"]:
        return graph_data
    
    # Create a copy to avoid modifying the original
    filtered_data = graph_data.copy()
    
    # Convert string dates to datetime objects if needed
    try:
        if "dates" in filtered_data and filtered_data["dates"]:
            # Check if dates are already datetime objects or need conversion
            dates = []
            for date in filtered_data["dates"]:
                if isinstance(date, str):
                    dates.append(datetime.strptime(date, '%Y-%m-%d').date())
                elif isinstance(date, datetime):
                    dates.append(date.date())
                else:
                    dates.append(date)  # Keep as is if we can't process
            
            # Filter by date range
            date_indexes = [i for i, date in enumerate(dates) 
                        if start_date <= date <= end_date]
            
            if date_indexes:
                # Filter dates and corresponding counts
                filtered_data["dates"] = [filtered_data["dates"][i] for i in date_indexes]
                if "counts" in filtered_data:
                    filtered_data["counts"] = [filtered_data["counts"][i] for i in date_indexes]
    except Exception as e:
        print(f"Error filtering graph data: {e}")
    
    return filtered_data

# Fetch location data for mapping
def get_location_data(query):
    """Extract location data from MongoDB for mapping"""
    try:
        location_pipeline = [
            {"$match": query},
            {"$project": {
                "location_device": "$device.location",
                "coordinates_device": "$device.coordinates",
                "location_direct": "$location",
                "loc_coordinates": "$location.loc.coordinates",
                "count": 1
            }},
            {"$group": {
                "_id": {
                    "city": {
                        "$ifNull": ["$location_device.city", "$location_direct.city"]
                    },
                    "region": {
                        "$ifNull": ["$location_device.region", "$location_direct.region"]
                    },
                    "country": {
                        "$ifNull": ["$location_device.country", "$location_direct.country"]
                    },
                    "countryCode": {
                        "$ifNull": ["$location_device.countryCode", "$location_direct.countryCode"]
                    },
                    "coordinates": {
                        "$ifNull": ["$coordinates_device", "$loc_coordinates"]
                    }
                },
                "count": {"$sum": 1}
            }}
        ]
        
        location_results = list(db.events.aggregate(location_pipeline))
        
        # Process location data for mapping
        location_data = []
        for loc in location_results:
            location_info = {
                'city': loc['_id'].get('city', 'Unknown'),
                'region': loc['_id'].get('region', 'Unknown'),
                'country': loc['_id'].get('country', loc['_id'].get('countryCode', 'Unknown')),
                'count': loc['count'],
                'coordinates': loc['_id'].get('coordinates')
            }
            
            # Handle coordinates
            coordinates = location_info['coordinates']
            if coordinates and isinstance(coordinates, list) and len(coordinates) >= 2:
                # Check if coordinates are in correct format [lat, lon]
                lat, lon = coordinates[0], coordinates[1]
                
                # Validate coordinates
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    location_info['valid_coordinates'] = [lat, lon]
                # Try swapped coordinates if original ones seem invalid
                elif -90 <= lon <= 90 and -180 <= lat <= 180:
                    location_info['valid_coordinates'] = [lon, lat]
            
            location_data.append(location_info)
            
        return location_data
    except Exception as e:
        print(f"Error getting location data: {e}")
        return []

# Create Navbar with Login Info
def create_navbar(username=None):
    # If logged in, show username and logout button
    if username:
        navbar = dbc.Navbar(
            dbc.Container(
                [
                    dbc.NavbarBrand("Insights Analytics Dashboard", className="ms-2"),
                    dbc.Nav(
                        [
                            dbc.NavItem(dbc.NavLink("Analytics", href="/analytics", active=True, id="analytics-link")),
                            dbc.NavItem(dbc.NavLink("Client View", href="/client-view", active=False, id="client-link")),
                            dbc.NavItem(dbc.NavLink("Management", href="/management", active=False, id="management-link")),
                            dbc.NavItem(html.Span(f"Logged in as: {username}", className="nav-link")),
                            dbc.NavItem(dbc.NavLink("Logout", href="/logout", id="logout-link")),
                        ],
                        className="ms-auto",
                        navbar=True,
                    ),
                ]
            ),
            color="primary",
            dark=True,
        )
    else:
        navbar = dbc.Navbar(
            dbc.Container(
                [
                    dbc.NavbarBrand("Insights Analytics Dashboard", className="ms-2"),
                    dbc.Nav(
                        [
                            dbc.NavItem(dbc.NavLink("Login", href="/login", id="login-link")),
                        ],
                        className="ms-auto",
                        navbar=True,
                    ),
                ]
            ),
            color="primary",
            dark=True,
        )
    return navbar

# Define the layout for the login page
login_layout = html.Div([
    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H2("Login to Insights Dashboard", className="mt-4"),
                html.Hr(),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Form([
                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Username or Email"),
                                    dbc.Input(type="text", id="username-input", placeholder="Enter username or email")
                                ])
                            ], className="mb-3"),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Password"),
                                    dbc.Input(type="password", id="password-input", placeholder="Enter password")
                                ])
                            ], className="mb-3"),
                            dbc.Button("Login", id="login-button", color="primary", className="mt-3"),
                            html.Div(id="login-output")
                        ])
                    ])
                ])
            ], width=6, className="mx-auto")
        ])
    ])
])

# Define the layout for each page
analytics_layout = html.Div([
    dbc.Row([
        dbc.Col([
            html.H5("Filters"),
            dbc.Card([
                dbc.CardBody([
                    html.H6("Date Range"),
                    dcc.DatePickerRange(
                        id='date-range',
                        start_date=datetime.now() - timedelta(days=30),
                        end_date=datetime.now(),
                        display_format='YYYY-MM-DD'
                    ),
                    html.Hr(),
                    html.H6("Organization"),
                    dcc.Dropdown(id='org-dropdown'),
                    html.Hr(),
                    html.H6("App"),
                    dcc.Dropdown(id='app-dropdown'),
                    html.Hr(),
                    html.H6("Event Type"),
                    dcc.Dropdown(id='event-type-dropdown'),
                    html.Hr(),
                    dbc.Button("Analyze Event", id="analyze-button", color="primary")
                ])
            ]),
        ], width=3),
        dbc.Col([
            html.H4("Event Analysis", id="analysis-title"),
            html.Div(id="analysis-output"),
            
            # Detailed Analysis section
            html.H4("Detailed Analysis", className="mt-4"),
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Select Experience"),
                            dcc.Dropdown(id="experience-dropdown", placeholder="Select Experience")
                        ], width=12, className="mb-3"),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Select Items"),
                            dcc.Dropdown(id="items-dropdown", multi=True, placeholder="Select Items")
                        ], width=12, className="mb-3"),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Visualization Type"),
                            dbc.RadioItems(
                                id="detailed-viz-type",
                                options=[
                                    {"label": "Bar Chart", "value": "bar_chart"},
                                    {"label": "Pie Chart", "value": "pie_chart"},
                                    {"label": "Timeline", "value": "timeline"},
                                    {"label": "Table", "value": "table"},
                                    {"label": "Location Map", "value": "map"}
                                ],
                                value="bar_chart",
                                inline=True
                            )
                        ], width=12, className="mb-3"),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Color Theme"),
                            dbc.Select(
                                id="color-theme-select",
                                options=[
                                    {"label": "Vibrant", "value": "vibrant"},
                                    {"label": "Pastel", "value": "pastel"},
                                    {"label": "Corporate", "value": "corporate"}
                                ],
                                value="vibrant"
                            )
                        ], width=12, className="mb-3"),
                    ]),
                    dbc.Button("Run Detailed Analysis", id="detailed-analysis-button", color="primary")
                ])
            ]),
            
            # Output area for detailed analysis
            html.Div(id="detailed-analysis-output", className="mt-3")
        ], width=9)
    ])
])

client_view_layout = html.Div([
    dbc.Row([
        dbc.Col([
            html.H5("Dashboard Selection"),
            dcc.Dropdown(id='dashboard-dropdown'),
            html.Hr(),
            html.H5("Date Filter"),
            dcc.DatePickerRange(
                id='dashboard-date-range',
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
                display_format='YYYY-MM-DD'
            ),
            html.Hr(),
            dbc.Button("Apply Filter", id="apply-filter-btn", color="primary", className="mb-3 me-2"),
            dbc.Button("Edit Dashboard", id="edit-dashboard-btn", color="secondary", className="mb-3"),
            dbc.Collapse([
                html.H5("Dashboard Settings", className="mt-3"),
                dbc.Input(id="edit-dashboard-name", placeholder="Dashboard Name", className="mb-2"),
                dbc.Textarea(id="edit-dashboard-desc", placeholder="Dashboard Description", className="mb-2"),
                dbc.Button("Update Settings", id="update-dashboard-btn", color="success", className="mb-2"),
            ], id="edit-dashboard-collapse", is_open=False),
        ], width=3),
        dbc.Col([
            html.H4("Dashboard View"),
            html.Div(id="dashboard-content"),
        ], width=9)
    ])
])

management_layout = html.Div([
    dbc.Tabs([
        dbc.Tab([
            html.H5("Create New Dashboard", className="mt-3"),
            dbc.Card([
                dbc.CardBody([
                    dbc.Input(id="new-dashboard-name", placeholder="Dashboard Name", type="text"),
                    dbc.Textarea(id="new-dashboard-desc", placeholder="Dashboard Description", className="mt-2"),
                    dbc.Button("Create Dashboard", id="create-dashboard-btn", color="primary", className="mt-2")
                ])
            ]),
            html.Div(id="create-dashboard-output")
        ], label="Create Dashboard"),
        dbc.Tab([
            html.H5("Manage Dashboards", className="mt-3"),
            html.Div(id="manage-dashboards-content")
        ], label="Manage Dashboards"),
    ]),
])

# Custom CSS for styling
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Insights Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            .graph-container {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 20px;
                border: 1px solid #dee2e6;
            }
            .graph-small {
                height: 250px;
            }
            .graph-medium {
                height: 400px;
            }
            .graph-large {
                height: 600px;
            }
            .graph-controls {
                margin-top: 10px;
                padding: 10px;
                background-color: #f1f3f5;
                border-radius: 5px;
            }
            .metric-card {
                padding: 20px;
                border-radius: 10px;
                background-color: #fff;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                text-align: center;
                height: 100%;
                margin-bottom: 15px;
            }
            .metric-value {
                font-size: 2rem;
                font-weight: bold;
                margin: 10px 0;
            }
            .metric-title {
                font-size: 1.2rem;
                color: #6c757d;
            }
            .metric-delta-positive {
                color: #28a745;
                font-size: 0.9rem;
            }
            .metric-delta-negative {
                color: #dc3545;
                font-size: 0.9rem;
            }
            .drag-handle {
                cursor: move;
                padding: 5px;
                margin-right: 5px;
                color: #6c757d;
            }
            /* Map container style */
            .map-container {
                height: 500px;
                width: 100%;
                border-radius: 8px;
                overflow: hidden;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Initial app layout - this includes dummy elements to avoid callback errors
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='navbar-container'),
    html.Div(id='page-content', className='container-fluid mt-4'),
    
    # Store components for maintaining state
    dcc.Store(id='selected-org', storage_type='session'),
    dcc.Store(id='selected-app', storage_type='session'),
    dcc.Store(id='selected-dashboard', storage_type='session'),
    dcc.Store(id='current-event-data', storage_type='session'),
    dcc.Store(id='filter-dates', storage_type='session'),
    dcc.Store(id='auth-user', storage_type='session'),
    dcc.Store(id='edit-mode', storage_type='session', data=False),
    dcc.Store(id='dashboard-layout', storage_type='session'),
    
    # Add empty div for all dynamically created components
    # This is to avoid callback errors for components that aren't initially in the layout
    html.Div([
        html.Button(id="login-button", style={"display": "none"}),
        html.Button(id="logout-link", style={"display": "none"}),
        html.Button(id="create-dashboard-btn", style={"display": "none"}),
        html.Button(id="confirm-add-dashboard", style={"display": "none"}),
        html.Button(id="update-dashboard-btn", style={"display": "none"}),
        html.Button(id="apply-filter-btn", style={"display": "none"}),
        html.Button(id="edit-dashboard-btn", style={"display": "none"}),
        html.Button(id="detailed-analysis-button", style={"display": "none"}),
        html.Div(id="login-output", style={"display": "none"}),
        html.Div(id="create-dashboard-output", style={"display": "none"}),
        html.Div(id="add-dashboard-output", style={"display": "none"}),
        html.Div(id="manage-dashboards-content", style={"display": "none"}),
        html.Div(id="detailed-analysis-output", style={"display": "none"}),
        html.Div(id="analytics-link", style={"display": "none"}),
        html.Div(id="client-link", style={"display": "none"}),
        html.Div(id="management-link", style={"display": "none"}),
        html.Div(id="username-input", style={"display": "none"}),
        html.Div(id="password-input", style={"display": "none"}),
        html.Div(id="dashboard-dropdown", style={"display": "none"}),
        html.Div(id="dashboard-content", style={"display": "none"}),
        html.Div(id="dashboard-date-range", style={"display": "none"}),
        html.Div(id="edit-dashboard-name", style={"display": "none"}),
        html.Div(id="edit-dashboard-desc", style={"display": "none"}),
        html.Div(id="edit-dashboard-collapse", style={"display": "none"}),
        html.Div(id="date-range", style={"display": "none"}),
        html.Div(id="org-dropdown", style={"display": "none"}),
        html.Div(id="app-dropdown", style={"display": "none"}),
        html.Div(id="event-type-dropdown", style={"display": "none"}),
        html.Div(id="experience-dropdown", style={"display": "none"}),
        html.Div(id="items-dropdown", style={"display": "none"}),
        html.Div(id="detailed-viz-type", style={"display": "none"}),
        html.Div(id="color-theme-select", style={"display": "none"}),
        html.Div(id="analyze-button", style={"display": "none"}),
        html.Div(id="analysis-title", style={"display": "none"}),
        html.Div(id="analysis-output", style={"display": "none"}),
        html.Div(id="new-dashboard-name", style={"display": "none"}),
        html.Div(id="new-dashboard-desc", style={"display": "none"}),
        html.Div(id="dashboard-select-dropdown", style={"display": "none"}),
        html.Div(id="graph-title-input", style={"display": "none"}),
        html.Div(id="graph-desc-input", style={"display": "none"}),
        html.Div(id="graph-size-select", style={"display": "none"}),
        html.Div(id="viz-tabs", style={"display": "none"}),
        html.Div(id="viz-type-radio", style={"display": "none"}),
        html.Div(id="drag-container", style={"display": "none"}),
    ], style={"display": "none"}),
])

# Main page routing
@app.callback(
    [Output('navbar-container', 'children'),
     Output('page-content', 'children'),
     Output('auth-user', 'data')],
    [Input('url', 'pathname'),
     Input('login-button', 'n_clicks'),
     Input('logout-link', 'n_clicks')],
    [State('username-input', 'value'),
     State('password-input', 'value'),
     State('auth-user', 'data')]
)
def handle_auth(pathname, login_clicks, logout_clicks, username, password, current_user):
    triggered_id = ctx.triggered_id if ctx.triggered_id else None
    
    # Handle logout
    if triggered_id == 'logout-link':
        return create_navbar(), login_layout, None
    
    # Handle login
    if triggered_id == 'login-button' and login_clicks:
        if username and password:
            success, message = login_user_cognito(username, password)
            if success:
                # Set current user
                return create_navbar(username), html.Div([
                    html.H3(f"Welcome, {username}"),
                    html.P("Please select a page from the navigation menu.")
                ]), username
            else:
                return create_navbar(), html.Div([
                    login_layout,
                    dbc.Alert(f"Login failed: {message}", color="danger")
                ]), None
    
    # Check if user is authenticated
    if current_user:
        if pathname == '/login':
            return create_navbar(current_user), html.Div([
                html.H3(f"Welcome, {current_user}"),
                html.P("You are already logged in. Choose a section from the navigation.")
            ]), current_user
        elif pathname == '/analytics':
            return create_navbar(current_user), analytics_layout, current_user
        elif pathname == '/client-view':
            return create_navbar(current_user), client_view_layout, current_user
        elif pathname == '/management':
            return create_navbar(current_user), management_layout, current_user
        else:
            return create_navbar(current_user), html.Div([
                html.H3(f"Welcome, {current_user}"),
                html.P("Please select a page from the navigation menu.")
            ]), current_user
    else:
        return create_navbar(), login_layout, None

# Callbacks for navigation tab activation
@app.callback(
    [Output('analytics-link', 'active'),
     Output('client-link', 'active'),
     Output('management-link', 'active')],
    [Input('url', 'pathname')]
)
def update_nav_active(pathname):
    if pathname == '/client-view':
        return False, True, False
    elif pathname == '/management':
        return False, False, True
    elif pathname == '/analytics':
        return True, False, False
    else:
        return False, False, False

# Load organizations
@app.callback(
    Output('org-dropdown', 'options'),
    Input('url', 'pathname'),
    State('auth-user', 'data')
)
def load_organizations(pathname, user):
    if pathname != '/analytics' or not user:
        return []
        
    org_ids = db.events.distinct("orgId")
    org_options = []
    
    for org_id in org_ids:
        org = db.organisations.find_one({"_id": org_id})
        if org and "name" in org:
            org_options.append({"label": f"{org['name']} ({org_id})", "value": org_id})
        else:
            org_options.append({"label": f"Organization {org_id}", "value": org_id})
    
    return sorted(org_options, key=lambda x: x["label"])

# Load apps when org is selected
@app.callback(
    Output('app-dropdown', 'options'),
    Input('org-dropdown', 'value'),
    State('selected-org', 'data')
)
def load_apps(org_id, stored_org):
    # Use stored org if dropdown hasn't been selected yet
    if org_id is None and stored_org:
        org_id = stored_org
    
    if not org_id:
        return []
    
    apps = list(db.events.distinct("appId", {"orgId": org_id}))
    apps = [app for app in apps if app is not None]
    
    return [{"label": app, "value": app} for app in sorted(apps)]

# Load event types when app is selected
@app.callback(
    Output('event-type-dropdown', 'options'),
    [Input('app-dropdown', 'value'),
     Input('org-dropdown', 'value')],
    [State('selected-org', 'data'),
     State('selected-app', 'data')]
)
def load_event_types(app_id, org_id, stored_org, stored_app):
    # Use stored values if dropdowns haven't been selected yet
    if org_id is None and stored_org:
        org_id = stored_org
    if app_id is None and stored_app:
        app_id = stored_app
    
    if not org_id or not app_id:
        return []
    
    event_types = []
    
    try:
        # Direct name field
        name_pipeline = [
            {"$match": {"orgId": org_id, "appId": app_id}},
            {"$group": {"_id": "$name"}}
        ]
        name_results = list(db.events.aggregate(name_pipeline))
        direct_events = [doc["_id"] for doc in name_results if doc["_id"] is not None]
        event_types.extend(direct_events)
        
        # Location.name field
        loc_pipeline = [
            {"$match": {"orgId": org_id, "appId": app_id}},
            {"$group": {"_id": "$location.name"}}
        ]
        loc_results = list(db.events.aggregate(loc_pipeline))
        loc_events = [doc["_id"] for doc in loc_results if doc["_id"] is not None]
        event_types.extend(loc_events)
    except Exception as e:
        print(f"Error loading event types: {e}")
    
    # Remove duplicates and sort
    event_types = sorted(list(set(event_types)))
    
    return [{"label": event_type, "value": event_type} for event_type in event_types]

# Store selected values
@app.callback(
    [Output('selected-org', 'data'),
     Output('selected-app', 'data')],
    [Input('org-dropdown', 'value'),
     Input('app-dropdown', 'value')]
)
def store_selections(org_id, app_id):
    return org_id, app_id

# Analyze event data with multiple visualization options
@app.callback(
    [Output('analysis-title', 'children'),
     Output('analysis-output', 'children'),
     Output('current-event-data', 'data')],
    Input('analyze-button', 'n_clicks'),
    [State('org-dropdown', 'value'),
     State('app-dropdown', 'value'),
     State('event-type-dropdown', 'value'),
     State('date-range', 'start_date'),
     State('date-range', 'end_date'),
     State('selected-org', 'data'),
     State('selected-app', 'data')]
)
def analyze_event(n_clicks, org_id, app_id, event_type, start_date, end_date, stored_org, stored_app):
    if n_clicks is None:
        raise PreventUpdate
    
    # Use stored values if dropdowns haven't been selected yet
    if org_id is None and stored_org:
        org_id = stored_org
    if app_id is None and stored_app:
        app_id = stored_app
    
    if not org_id or not app_id or not event_type:
        return "Please select all required filters", html.Div("Select organization, app, and event type to analyze data."), None
    
    try:
        # Build the query
        query, test_document = build_query(
            org_id, app_id, 
            event_type=event_type,
            start_date=start_date, 
            end_date=end_date
        )
        
        # Count total events
        total_count = db.events.count_documents(query)
        
        # Get counts by date
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "year": {"$year": "$createdAt"},
                    "month": {"$month": "$createdAt"},
                    "day": {"$dayOfMonth": "$createdAt"}
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
        ]
        
        date_counts = list(db.events.aggregate(pipeline))
        
        # Format data for plotting
        if date_counts:
            dates = []
            counts = []
            
            for item in date_counts:
                year = item["_id"]["year"]
                month = item["_id"]["month"]
                day = item["_id"]["day"]
                date_str = f"{year}-{month:02d}-{day:02d}"
                dates.append(date_str)
                counts.append(item["count"])
            
            # Create figures for different visualization types
            timeline_fig = go.Figure()
            timeline_fig.add_trace(go.Scatter(
                x=dates,
                y=counts,
                mode='lines+markers',
                name=event_type,
                line=dict(color=COLOR_PALETTES["vibrant"][0], width=3),
                marker=dict(size=8)
            ))
            
            timeline_fig.update_layout(
                title=f'Event Count Over Time: {event_type}',
                xaxis_title='Date',
                yaxis_title='Count',
                hovermode='x unified',
                height=500
            )
            
            # Bar chart
            bar_fig = go.Figure()
            bar_fig.add_trace(go.Bar(
                x=dates,
                y=counts,
                name=event_type,
                marker_color=COLOR_PALETTES["vibrant"][0]
            ))
            
            bar_fig.update_layout(
                title=f'Event Count by Date: {event_type}',
                xaxis_title='Date',
                yaxis_title='Count',
                hovermode='x unified',
                height=500
            )
            
            # Create a simple dataframe
            df = pd.DataFrame({
                'Date': dates,
                'Count': counts
            })
            
            # Save event data for dashboard use
            event_data = {
                "type": "time_series",
                "title": f"Event Count Over Time: {event_type}",
                "org_id": org_id,
                "app_id": app_id,
                "event_type": event_type,
                "dates": dates,
                "counts": counts,
                "total_count": total_count,
                "dataframe": df.to_dict('records')
            }
            
            # Calculate metrics for previous period
            prev_metrics = None
            if start_date and end_date:
                start_date_obj = parse_date(start_date)
                end_date_obj = parse_date(end_date)
                if start_date_obj and end_date_obj:
                    date_diff = (end_date_obj - start_date_obj).days
                    prev_end = start_date_obj - timedelta(days=1)
                    prev_start = prev_end - timedelta(days=date_diff)
                    
                    # Query for previous period
                    prev_query, _ = build_query(
                        org_id, app_id,
                        event_type=event_type,
                        start_date=prev_start,
                        end_date=prev_end
                    )
                    
                    prev_count = db.events.count_documents(prev_query)
                    prev_metrics = {
                        "prev_count": prev_count,
                        "prev_start": prev_start.strftime('%Y-%m-%d'),
                        "prev_end": prev_end.strftime('%Y-%m-%d')
                    }
                    
                    event_data["previous_metrics"] = prev_metrics
            
            # Build output with visualization options
            output = html.Div([
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"Total: {total_count}", className="card-title"),
                                html.P("Total Events", className="card-text"),
                                html.Div([
                                    html.Span(f"{((total_count - prev_metrics['prev_count']) / prev_metrics['prev_count'] * 100):.1f}% ", 
                                             className=f"metric-delta-{'positive' if total_count >= prev_metrics['prev_count'] else 'negative'}"),
                                    html.Span(f"vs previous period ({prev_metrics['prev_start']} to {prev_metrics['prev_end']})")
                                ]) if prev_metrics and prev_metrics['prev_count'] > 0 else html.Div()
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"Date Range:", className="card-title"),
                                html.P(f"{min(dates) if dates else 'N/A'} to {max(dates) if dates else 'N/A'}", className="card-text"),
                            ])
                        ])
                    ], width=8),
                ], className="mb-4"),
                
                # Visualization selector tabs
                dbc.Tabs([
                    dbc.Tab([
                        dcc.Graph(figure=timeline_fig)
                    ], label="Timeline"),
                    dbc.Tab([
                        dcc.Graph(figure=bar_fig)
                    ], label="Bar Chart"),
                    dbc.Tab([
                        html.Div([
                            html.H5("Data Table"),
                            dash.dash_table.DataTable(
                                data=df.to_dict('records'),
                                columns=[{"name": i, "id": i} for i in df.columns],
                                sort_action="native",
                                filter_action="native",
                                page_size=10,
                                style_table={'overflowX': 'auto'},
                                style_header={
                                    'backgroundColor': 'rgb(230, 230, 230)',
                                    'fontWeight': 'bold'
                                },
                                style_cell={
                                    'padding': '10px',
                                    'whiteSpace': 'normal',
                                    'height': 'auto',
                                }
                            )
                        ])
                    ], label="Data Table"),
                    dbc.Tab([
                        html.Div([
                            html.H5("Pie Chart"),
                            html.P("Event distribution by date"),
                            dcc.Graph(
                                figure=px.pie(
                                    df, 
                                    names='Date', 
                                    values='Count',
                                    title=f'Event Distribution: {event_type}',
                                    color_discrete_sequence=COLOR_PALETTES["vibrant"]
                                )
                            )
                        ])
                    ], label="Pie Chart")
                ], id="viz-tabs"),
                
                # Dashboard options
                dbc.Row([
                    dbc.Col([
                        html.H5("Add to Dashboard", className="mt-4"),
                        dbc.Card([
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Select Dashboard"),
                                        dcc.Dropdown(id="dashboard-select-dropdown", placeholder="Select Dashboard")
                                    ], width=12, className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Visualization Type"),
                                        dbc.RadioItems(
                                            id="viz-type-radio",
                                            options=[
                                                {"label": "Timeline", "value": "timeline"},
                                                {"label": "Bar Chart", "value": "bar_chart"},
                                                {"label": "Pie Chart", "value": "pie_chart"},
                                                {"label": "Data Table", "value": "table"},
                                                {"label": "Metric Card", "value": "metric"}
                                            ],
                                            value="timeline",
                                            inline=True
                                        )
                                    ], width=12, className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Title"),
                                        dbc.Input(id="graph-title-input", placeholder="Title", value=f"Event Count: {event_type}")
                                    ], width=12, className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Description"),
                                        dbc.Textarea(id="graph-desc-input", placeholder="Description", 
                                                    value=f"Analysis of {event_type} events from {min(dates) if dates else 'N/A'} to {max(dates) if dates else 'N/A'}.")
                                    ], width=12, className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Size"),
                                        dbc.Select(
                                            id="graph-size-select",
                                            options=[
                                                {"label": "Small", "value": "small"},
                                                {"label": "Medium", "value": "medium"},
                                                {"label": "Large", "value": "large"}
                                            ],
                                            value="medium"
                                        )
                                    ], width=12, className="mb-3"),
                                ]),
                                dbc.Button("Add to Dashboard", id="confirm-add-dashboard", color="success", className="mt-2")
                            ])
                        ]),
                        html.Div(id="add-dashboard-output")
                    ], width=12)
                ])
            ])
            
            return f"Analysis for Event: {event_type}", output, event_data
        else:
            return f"Analysis for Event: {event_type}", html.Div("No date data available for the selected filters"), None
            
    except Exception as e:
        print(f"Error in event analysis: {e}")
        return "Error in Analysis", html.Div(f"An error occurred: {str(e)}"), None

# Load experiences dropdown
@app.callback(
    Output('experience-dropdown', 'options'),
    [Input('org-dropdown', 'value'),
     Input('app-dropdown', 'value')],
    [State('selected-org', 'data'),
     State('selected-app', 'data')]
)
def load_experiences(org_id, app_id, stored_org, stored_app):
    # Use stored values if dropdowns haven't been selected yet
    if org_id is None and stored_org:
        org_id = stored_org
    if app_id is None and stored_app:
        app_id = stored_app
    
    if not org_id or not app_id:
        return []
    
    experiences = []
    test_document = db.events.find_one({"orgId": org_id, "appId": app_id})
    
    try:
        # Check both possible locations for experienceId
        # First try device.experienceId
        device_exps = db.events.distinct("device.experienceId", {"orgId": org_id, "appId": app_id})
        experiences.extend([exp for exp in device_exps if exp is not None])
        
        # Then try direct experienceId
        direct_exps = db.events.distinct("experienceId", {"orgId": org_id, "appId": app_id})
        experiences.extend([exp for exp in direct_exps if exp is not None])
    except Exception as e:
        print(f"Error loading experiences: {e}")
    
    # Remove duplicates, sort, and add a "No Experience" option
    experiences = sorted(list(set(experiences)))
    experiences = ["No Experience"] + experiences
    
    return [{"label": exp, "value": exp} for exp in experiences]

# Load items dropdown based on experience
@app.callback(
    Output('items-dropdown', 'options'),
    [Input('experience-dropdown', 'value'),
     Input('org-dropdown', 'value'),
     Input('app-dropdown', 'value')],
    [State('selected-org', 'data'),
     State('selected-app', 'data')]
)
def load_items(exp_id, org_id, app_id, stored_org, stored_app):
    # Use stored values if dropdowns haven't been selected yet
    if org_id is None and stored_org:
        org_id = stored_org
    if app_id is None and stored_app:
        app_id = stored_app
    
    if not org_id or not app_id or not exp_id:
        return []
    
    # Build base query for the experience
    query, test_doc = build_query(
        org_id, app_id, 
        exp_id=exp_id
    )
    
    # Get items
    items = []
    item_field = get_item_name_field(test_doc)
    
    try:
        item_pipeline = [
            {"$match": query},
            {"$group": {"_id": f"${item_field}"}}
        ]
        item_results = list(db.events.aggregate(item_pipeline))
        items = [doc["_id"] for doc in item_results if doc["_id"] is not None and doc["_id"] != ""]
    except Exception as e:
        print(f"Error getting items: {e}")
    
    return [{"label": item, "value": item} for item in sorted(items)]

# Detailed analysis callback
@app.callback(
    Output('detailed-analysis-output', 'children'),
    Input('detailed-analysis-button', 'n_clicks'),
    [State('org-dropdown', 'value'),
     State('app-dropdown', 'value'),
     State('experience-dropdown', 'value'),
     State('items-dropdown', 'value'),
     State('detailed-viz-type', 'value'),
     State('color-theme-select', 'value'),
     State('date-range', 'start_date'),
     State('date-range', 'end_date')]
)
def run_detailed_analysis(n_clicks, org_id, app_id, exp_id, selected_items, viz_type, color_theme, start_date, end_date):
    if n_clicks is None or not org_id or not app_id:
        raise PreventUpdate
    
    # Check if items are selected
    if not selected_items or len(selected_items) == 0:
        return dbc.Alert("Please select at least one item for detailed analysis", color="warning")
    
    try:
        # Build the query with all filters
        query, test_doc = build_query(
            org_id, app_id,
            exp_id=exp_id,
            selected_items=selected_items,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get counts by item for bar and pie charts
        item_field = get_item_name_field(test_doc)
        item_pipeline = [
            {"$match": query},
            {"$group": {
                "_id": f"${item_field}",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        item_counts = list(db.events.aggregate(item_pipeline))
        
        # Format data for visualization
        items = [item["_id"] for item in item_counts]
        counts = [item["count"] for item in item_counts]
        
        # Calculate total count
        total_count = sum(counts)
        
        # Create DataFrame for table
        df = pd.DataFrame({
            "Item": items,
            "Count": counts,
            "Percentage": [round(count/total_count*100, 2) for count in counts]
        })
        
        # Create different visualizations based on the selected type
        if viz_type == "bar_chart":
            # Create bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=items,
                y=counts,
                marker_color=COLOR_PALETTES[color_theme][:len(items)]
            ))
            
            fig.update_layout(
                title=f'Item Counts for {exp_id}',
                xaxis_title='Items',
                yaxis_title='Count',
                hovermode='x unified',
                height=500,
                xaxis=dict(tickangle=-45)
            )
            
            return html.Div([
                html.H4(f"Total Events: {total_count}"),
                dcc.Graph(figure=fig),
                html.Div([
                    html.H5("Add to Dashboard"),
                    dcc.Dropdown(id="detailed-dashboard-select", placeholder="Select Dashboard"),
                    dbc.Button("Add to Dashboard", id="add-detailed-to-dashboard", color="primary", className="mt-2")
                ], className="mt-3")
            ])
            
        elif viz_type == "pie_chart":
            # Create pie chart
            fig = go.Figure(data=[go.Pie(
                labels=items,
                values=counts,
                hole=0.3,
                marker=dict(colors=COLOR_PALETTES[color_theme][:len(items)])
            )])
            
            fig.update_layout(
                title=f'Event Distribution by Item for {exp_id}',
                height=500
            )
            
            return html.Div([
                html.H4(f"Total Events: {total_count}"),
                dcc.Graph(figure=fig),
                html.Div([
                    html.H5("Add to Dashboard"),
                    dcc.Dropdown(id="detailed-dashboard-select", placeholder="Select Dashboard"),
                    dbc.Button("Add to Dashboard", id="add-detailed-to-dashboard", color="primary", className="mt-2")
                ], className="mt-3")
            ])
            
        elif viz_type == "timeline":
            # Get counts by date and item
            timeline_pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": {
                        "item": f"${item_field}",
                        "year": {"$year": "$createdAt"},
                        "month": {"$month": "$createdAt"},
                        "day": {"$dayOfMonth": "$createdAt"}
                    },
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
            ]
            
            timeline_results = list(db.events.aggregate(timeline_pipeline))
            
            # Process data for timeline visualization
            timeline_data = {}
            for result in timeline_results:
                item = result["_id"]["item"]
                year = result["_id"]["year"]
                month = result["_id"]["month"]
                day = result["_id"]["day"]
                date_str = f"{year}-{month:02d}-{day:02d}"
                count = result["count"]
                
                if item not in timeline_data:
                    timeline_data[item] = {"dates": [], "counts": []}
                
                timeline_data[item]["dates"].append(date_str)
                timeline_data[item]["counts"].append(count)
            
            # Create multi-line timeline
            fig = go.Figure()
            
            for i, (item, data) in enumerate(timeline_data.items()):
                fig.add_trace(go.Scatter(
                    x=data["dates"],
                    y=data["counts"],
                    mode='lines+markers',
                    name=item,
                    line=dict(color=COLOR_PALETTES[color_theme][i % len(COLOR_PALETTES[color_theme])], width=2)
                ))
            
            fig.update_layout(
                title=f'Timeline for Items in {exp_id}',
                xaxis_title='Date',
                yaxis_title='Count',
                hovermode='x unified',
                height=500
            )
            
            return html.Div([
                html.H4(f"Total Events: {total_count}"),
                dcc.Graph(figure=fig),
                html.Div([
                    html.H5("Add to Dashboard"),
                    dcc.Dropdown(id="detailed-dashboard-select", placeholder="Select Dashboard"),
                    dbc.Button("Add to Dashboard", id="add-detailed-to-dashboard", color="primary", className="mt-2")
                ], className="mt-3")
            ])
            
        elif viz_type == "table":
            # Create data table
            return html.Div([
                html.H4(f"Total Events: {total_count}"),
                dash.dash_table.DataTable(
                    data=df.to_dict('records'),
                    columns=[{"name": i, "id": i} for i in df.columns],
                    sort_action="native",
                    filter_action="native",
                    page_size=10,
                    style_table={'overflowX': 'auto'},
                    style_header={
                        'backgroundColor': 'rgb(230, 230, 230)',
                        'fontWeight': 'bold'
                    },
                    style_cell={
                        'padding': '10px',
                        'whiteSpace': 'normal',
                        'height': 'auto',
                    }
                ),
                html.Div([
                    html.H5("Add to Dashboard"),
                    dcc.Dropdown(id="detailed-dashboard-select", placeholder="Select Dashboard"),
                    dbc.Button("Add to Dashboard", id="add-detailed-to-dashboard", color="primary", className="mt-2")
                ], className="mt-3")
            ])
            
        elif viz_type == "map":
            # Get location data for mapping
            location_data = get_location_data(query)
            
            if not location_data:
                return dbc.Alert("No location data available for the selected filters", color="warning")
            
            # Create map visualization using Plotly
            # Extract valid location data
            valid_locations = [loc for loc in location_data if 'valid_coordinates' in loc]
            
            if not valid_locations:
                return dbc.Alert("No valid coordinates found for mapping", color="warning")
            
            # Create map
            lat_values = [loc['valid_coordinates'][0] for loc in valid_locations]
            lon_values = [loc['valid_coordinates'][1] for loc in valid_locations]
            
            # Create hover text
            hover_text = [
                f"City: {loc['city']}<br>" +
                f"Region: {loc['region']}<br>" +
                f"Country: {loc['country']}<br>" +
                f"Count: {loc['count']}"
                for loc in valid_locations
            ]
            
            # Use Mapbox for better map quality
            fig = go.Figure(go.Scattermapbox(
                lat=lat_values,
                lon=lon_values,
                mode='markers',
                marker=dict(
                    size=[min(loc['count']*2, 30) for loc in valid_locations],  # Scale marker size by count
                    color=COLOR_PALETTES[color_theme][0],
                    opacity=0.7
                ),
                text=hover_text,
                hoverinfo='text'
            ))
            
            # Calculate center of map
            center_lat = sum(lat_values) / len(lat_values)
            center_lon = sum(lon_values) / len(lon_values)
            
            fig.update_layout(
                title=f'Location Map for {exp_id}',
                mapbox=dict(
                    style='open-street-map',
                    center=dict(lat=center_lat, lon=center_lon),
                    zoom=2
                ),
                height=600,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            # Create summary table
            summary_df = pd.DataFrame({
                'City': [loc['city'] for loc in location_data],
                'Region': [loc['region'] for loc in location_data],
                'Country': [loc['country'] for loc in location_data],
                'Count': [loc['count'] for loc in location_data]
            })
            
            summary_table = dash.dash_table.DataTable(
                data=summary_df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in summary_df.columns],
                sort_action="native",
                filter_action="native",
                page_size=5,
                style_table={'overflowX': 'auto'},
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold'
                },
                style_cell={
                    'padding': '10px',
                    'whiteSpace': 'normal',
                    'height': 'auto',
                }
            )
            
            return html.Div([
                html.H4(f"Total Events: {total_count}"),
                dcc.Graph(figure=fig, className="map-container"),
                html.H5("Location Summary", className="mt-3"),
                summary_table,
                html.Div([
                    html.H5("Add to Dashboard"),
                    dcc.Dropdown(id="detailed-dashboard-select", placeholder="Select Dashboard"),
                    dbc.Button("Add to Dashboard", id="add-detailed-to-dashboard", color="primary", className="mt-2")
                ], className="mt-3")
            ])
        
        # Default case
        return dbc.Alert("Please select a visualization type", color="warning")
            
    except Exception as e:
        print(f"Error in detailed analysis: {e}")
        return dbc.Alert(f"Error in detailed analysis: {str(e)}", color="danger")

# Load dashboards dropdown
@app.callback(
    Output("dashboard-select-dropdown", "options"),
    Input("viz-tabs", "active_tab")
)
def load_dashboards_dropdown(active_tab):
    # Load current dashboards
    client_data = load_client_data()
    dashboards = client_data.get("dashboards", [])
    
    if not dashboards:
        # Create a default dashboard if none exist
        dashboard_id = create_dashboard("Default Dashboard", "Auto-generated default dashboard")
        dashboards = [{"id": dashboard_id, "name": "Default Dashboard"}]
    
    return [{"label": dash["name"], "value": dash["id"]} for dash in dashboards]

# Add to dashboard
@app.callback(
    Output("add-dashboard-output", "children"),
    Input("confirm-add-dashboard", "n_clicks"),
    [State("dashboard-select-dropdown", "value"),
     State("graph-title-input", "value"),
     State("graph-desc-input", "value"),
     State("viz-type-radio", "value"),
     State("graph-size-select", "value"),
     State("current-event-data", "data")]
)
def add_event_to_dashboard(n_clicks, dashboard_id, title, description, viz_type, size, event_data):
    if n_clicks is None or not dashboard_id or not event_data:
        raise PreventUpdate
    
    try:
        # Create a copy of the data
        display_data = event_data.copy()
        
        # Set the visualization type
        display_data["type"] = viz_type
        
        # Add to dashboard based on visualization type
        graph_id = None
        
        if viz_type == "metric":
            # Create metric data
            metric_data = {
                "title": title,
                "value": display_data["total_count"],
                "previous_value": display_data.get("previous_metrics", {}).get("prev_count"),
                "type": "metric"
            }
            
            # Add metric card
            graph_id = add_metric_to_dashboard(metric_data, dashboard_id, title, description)
        else:
            # Add graph (timeline, bar_chart, pie_chart, or table)
            graph_id = add_to_dashboard(display_data, dashboard_id, title, description, size)
        
        if graph_id:
            return html.Div([
                dbc.Alert(f"Added to dashboard successfully!", color="success"),
                dbc.Button("View Dashboard", id="view-dashboard-btn", color="primary", className="mt-2",
                          href="/client-view")
            ])
        else:
            return dbc.Alert("Failed to add to dashboard. Please try again.", color="danger")
    except Exception as e:
        print(f"Error adding to dashboard: {e}")
        return dbc.Alert(f"Error: {str(e)}", color="danger")

# Load dashboard dropdown in client view
@app.callback(
    Output("dashboard-dropdown", "options"),
    Input("url", "pathname")
)
def load_client_dashboards(pathname):
    if pathname != '/client-view':
        raise PreventUpdate
        
    # Load current dashboards
    client_data = load_client_data()
    dashboards = client_data.get("dashboards", [])
    
    return [{"label": dash["name"], "value": dash["id"]} for dash in dashboards]

# Toggle edit mode
@app.callback(
    [Output("edit-dashboard-collapse", "is_open"),
     Output("edit-mode", "data")],
    [Input("edit-dashboard-btn", "n_clicks")],
    [State("edit-dashboard-collapse", "is_open"),
     State("edit-mode", "data")]
)
def toggle_edit_mode(n_clicks, is_open, edit_mode):
    if n_clicks is None:
        return is_open, edit_mode
    
    return not is_open, not edit_mode

# Update dashboard settings
@app.callback(
    Output("update-dashboard-btn", "disabled"),
    [Input("update-dashboard-btn", "n_clicks"),
     Input("dashboard-dropdown", "value")],
    [State("edit-dashboard-name", "value"),
     State("edit-dashboard-desc", "value")]
)
def update_dashboard_settings(n_clicks, dashboard_id, name, description):
    if n_clicks is None or dashboard_id is None:
        return False
    
    if name and dashboard_id:
        update_dashboard(dashboard_id, name, description)
        return False
    
    return True

# Store date filter
@app.callback(
    Output("filter-dates", "data"),
    [Input("apply-filter-btn", "n_clicks")],
    [State("dashboard-date-range", "start_date"),
     State("dashboard-date-range", "end_date")]
)
def store_date_filter(n_clicks, start_date, end_date):
    if n_clicks is None:
        raise PreventUpdate
    
    # Ensure we have valid dates
    if not start_date or not end_date:
        return None
    
    return {
        "start_date": start_date,
        "end_date": end_date
    }

# Display selected dashboard
@app.callback(
    Output("dashboard-content", "children"),
    [Input("dashboard-dropdown", "value"),
     Input("filter-dates", "data"),
     Input("edit-mode", "data"),
     Input("update-dashboard-btn", "n_clicks"),
     Input("apply-filter-btn", "n_clicks")]
)
def display_dashboard(dashboard_id, filter_dates, edit_mode, update_clicks, filter_clicks):
    if not dashboard_id:
        return html.Div("Please select a dashboard from the dropdown")
    
    # Load dashboard data
    client_data = load_client_data()
    dashboard = next((d for d in client_data.get("dashboards", []) if d["id"] == dashboard_id), None)
    
    if not dashboard:
        return html.Div("Dashboard not found")
    
    # Get all items for this dashboard
    layouts = [item for item in client_data.get("layouts", []) 
              if "dashboard_id" in item and item["dashboard_id"] == dashboard_id]
    
    # Sort by order
    layouts = sorted(layouts, key=lambda x: x.get("order", 0))
    
    # Create drag container elements
    dashboard_items = []
    
    dashboard_items.append(html.H3(dashboard["name"]))
    dashboard_items.append(html.P(dashboard["description"]))
    dashboard_items.append(html.Hr())
    
    # Add date filter info if applied
    if filter_dates:
        start_date = parse_date(filter_dates["start_date"])
        end_date = parse_date(filter_dates["end_date"])
        
        if start_date and end_date:
            dashboard_items.append(
                dbc.Alert(
                    f"Filtered data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                    color="info",
                    dismissable=True
                )
            )
    
    # Prepare draggable layout
    draggable_items = {}
    
    # Create content for each item
    for i, layout_item in enumerate(layouts):
        item_id = layout_item["id"]
        item_type = layout_item["type"]
        
        if item_type == "graph":
            # Find the corresponding graph data
            graph_data = next((g for g in client_data.get("graphs", []) if g["id"] == item_id), None)
            
            if graph_data:
                # Apply date filtering if applicable
                filtered_graph_data = graph_data
                if filter_dates and graph_data.get("type") in ["time_series", "timeline"]:
                    start_date = parse_date(filter_dates["start_date"])
                    end_date = parse_date(filter_dates["end_date"])
                    
                    if start_date and end_date:
                        filtered_graph_data = filter_graph_by_dates(graph_data, start_date.date(), end_date.date())
                
                # Create component based on graph type
                component = None
                
                # Determine column width based on size
                size = graph_data.get("size", "medium")
                col_width = 6  # Default for medium
                if size == "small":
                    col_width = 4
                elif size == "large":
                    col_width = 12
                
                # Handle edit mode controls
                edit_controls = []
                if edit_mode:
                    edit_controls = [
                        html.Div([
                            html.I(className="fa fa-bars drag-handle"),
                            dbc.Button("Edit", id={"type": "edit-graph-btn", "index": item_id}, 
                                       color="link", size="sm", className="me-2"),
                            dbc.Button("Remove", id={"type": "remove-graph-btn", "index": item_id}, 
                                       color="link", size="sm", className="me-2")
                        ], className="graph-controls")
                    ]
                
                # Set up edit modal for this graph
                edit_modal = dbc.Modal([
                    dbc.ModalHeader("Edit Graph"),
                    dbc.ModalBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Title"),
                                dbc.Input(id={"type": "edit-title-input", "index": item_id}, 
                                        value=graph_data.get("heading", graph_data.get("title", "")))
                            ])
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Description"),
                                dbc.Textarea(id={"type": "edit-desc-input", "index": item_id}, 
                                            value=graph_data.get("description", ""))
                            ])
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Size"),
                                dbc.Select(
                                    id={"type": "edit-size-select", "index": item_id},
                                    options=[
                                        {"label": "Small", "value": "small"},
                                        {"label": "Medium", "value": "medium"},
                                        {"label": "Large", "value": "large"}
                                    ],
                                    value=graph_data.get("size", "medium")
                                )
                            ])
                        ], className="mb-3")
                    ]),
                    dbc.ModalFooter([
                        dbc.Button("Save", id={"type": "save-edit-btn", "index": item_id}, color="primary"),
                        dbc.Button("Cancel", id={"type": "cancel-edit-btn", "index": item_id}, color="secondary")
                    ])
                ], id={"type": "edit-modal", "index": item_id}, is_open=False)
                
                if filtered_graph_data["type"] == "metric":
                    # Create metric card
                    metric_data = filtered_graph_data
                    
                    component = html.Div([
                        html.Div([
                            html.Div(metric_data.get("title", "Metric"), className="metric-title"),
                            html.Div(str(metric_data.get("value", "N/A")), className="metric-value"),
                            html.Div([
                                html.Span(f"{((metric_data.get('value', 0) - metric_data.get('previous_value', 0)) / metric_data.get('previous_value', 1) * 100):.1f}% ", 
                                         className=f"metric-delta-{'positive' if metric_data.get('value', 0) >= metric_data.get('previous_value', 0) else 'negative'}"),
                                html.Span("vs previous period")
                            ]) if metric_data.get("previous_value") else None
                        ], className="metric-card"),
                        *edit_controls,
                        edit_modal
                    ])
                
                elif filtered_graph_data["type"] in ["time_series", "timeline"]:
                    # Create timeline
                    dates = filtered_graph_data.get("dates", [])
                    counts = filtered_graph_data.get("counts", [])
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=dates,
                        y=counts,
                        mode='lines+markers',
                        name=filtered_graph_data.get("event_type", "Events"),
                        line=dict(color=COLOR_PALETTES["vibrant"][0], width=3),
                        marker=dict(size=8)
                    ))
                    
                    fig.update_layout(
                        title=filtered_graph_data.get("heading", filtered_graph_data.get("title", "")),
                        xaxis_title='Date',
                        yaxis_title='Count',
                        hovermode='x unified'
                    )
                    
                    component = html.Div([
                        html.H5(filtered_graph_data.get("heading", filtered_graph_data.get("title", ""))),
                        html.P(filtered_graph_data.get("description", ""), className="text-muted"),
                        dcc.Graph(figure=fig, className=f"graph-{size}"),
                        *edit_controls,
                        edit_modal
                    ], className="graph-container")
                
                elif filtered_graph_data["type"] == "bar_chart":
                    # Create bar chart
                    dates = filtered_graph_data.get("dates", [])
                    counts = filtered_graph_data.get("counts", [])
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=dates,
                        y=counts,
                        name=filtered_graph_data.get("event_type", "Events"),
                        marker_color=COLOR_PALETTES["vibrant"][0]
                    ))
                    
                    fig.update_layout(
                        title=filtered_graph_data.get("heading", filtered_graph_data.get("title", "")),
                        xaxis_title='Date',
                        yaxis_title='Count',
                        hovermode='x unified'
                    )
                    
                    component = html.Div([
                        html.H5(filtered_graph_data.get("heading", filtered_graph_data.get("title", ""))),
                        html.P(filtered_graph_data.get("description", ""), className="text-muted"),
                        dcc.Graph(figure=fig, className=f"graph-{size}"),
                        *edit_controls,
                        edit_modal
                    ], className="graph-container")
                
                elif filtered_graph_data["type"] == "pie_chart":
                    # Create pie chart
                    dates = filtered_graph_data.get("dates", [])
                    counts = filtered_graph_data.get("counts", [])
                    
                    fig = go.Figure(data=[go.Pie(
                        labels=dates,
                        values=counts,
                        hole=0.3,
                        marker=dict(colors=COLOR_PALETTES["vibrant"])
                    )])
                    
                    fig.update_layout(
                        title=filtered_graph_data.get("heading", filtered_graph_data.get("title", ""))
                    )
                    
                    component = html.Div([
                        html.H5(filtered_graph_data.get("heading", filtered_graph_data.get("title", ""))),
                        html.P(filtered_graph_data.get("description", ""), className="text-muted"),
                        dcc.Graph(figure=fig, className=f"graph-{size}"),
                        *edit_controls,
                        edit_modal
                    ], className="graph-container")
                
                elif filtered_graph_data["type"] == "table":
                    # Create data table
                    if "dataframe" in filtered_graph_data:
                        df_data = filtered_graph_data["dataframe"]
                        
                        component = html.Div([
                            html.H5(filtered_graph_data.get("heading", filtered_graph_data.get("title", ""))),
                            html.P(filtered_graph_data.get("description", ""), className="text-muted"),
                            dash.dash_table.DataTable(
                                data=df_data,
                                columns=[{"name": i, "id": i} for i in df_data[0].keys()],
                                sort_action="native",
                                filter_action="native",
                                page_size=10,
                                style_table={'overflowX': 'auto'},
                                style_header={
                                    'backgroundColor': 'rgb(230, 230, 230)',
                                    'fontWeight': 'bold'
                                },
                                style_cell={
                                    'padding': '10px',
                                    'whiteSpace': 'normal',
                                    'height': 'auto',
                                }
                            ),
                            *edit_controls,
                            edit_modal
                        ], className="graph-container")
                
                # Add item to draggable layout
                item_key = f"item-{item_id}"
                draggable_items[item_key] = dbc.Col(component, width=col_width)
    
    # Create rows from items
    current_row = []
    row_width = 0
    
    if draggable_items:
        for key, item in draggable_items.items():
            item_width = item.width
            
            # Check if this item fits in the current row
            if row_width + item_width <= 12:
                current_row.append(item)
                row_width += item_width
            else:
                # Row is full, add it to dashboard
                dashboard_items.append(dbc.Row(current_row, className="mb-4"))
                # Start a new row with this item
                current_row = [item]
                row_width = item_width
        
        # Add any remaining items in the last row
        if current_row:
            dashboard_items.append(dbc.Row(current_row, className="mb-4"))
    else:
        dashboard_items.append(
            dbc.Alert("No items in this dashboard. Add items from the Analytics page.", color="info")
        )
    
    # Setup draggable layout for edit mode if needed
    if edit_mode:
        dashboard_items.append(
            html.Div([
                html.P("Drag items to rearrange them", className="text-muted"),
                # We would typically use dash_draggable here, but for simplicity 
                # we're just showing a placeholder for this code example
                html.Div(id="drag-container", className="drag-container")
            ])
        )
    
    return html.Div(dashboard_items)

# Pattern-matching callback for editing graphs
@app.callback(
    Output({"type": "edit-modal", "index": MATCH}, "is_open"),
    [Input({"type": "edit-graph-btn", "index": MATCH}, "n_clicks"),
     Input({"type": "save-edit-btn", "index": MATCH}, "n_clicks"),
     Input({"type": "cancel-edit-btn", "index": MATCH}, "n_clicks")],
    [State({"type": "edit-modal", "index": MATCH}, "is_open"),
     State({"type": "edit-title-input", "index": MATCH}, "value"),
     State({"type": "edit-desc-input", "index": MATCH}, "value"),
     State({"type": "edit-size-select", "index": MATCH}, "value"),
     State({"type": "edit-graph-btn", "index": MATCH}, "id")]
)
def handle_edit_graph(edit_clicks, save_clicks, cancel_clicks, is_open, title, description, size, btn_id):
    ctx_triggered = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if not ctx_triggered:
        return is_open
    
    if "edit-graph-btn" in ctx_triggered:
        return not is_open
    
    if "save-edit-btn" in ctx_triggered:
        # Get the item ID from the button ID
        item_id = json.loads(ctx_triggered.replace("'", '"'))["index"]
        update_graph_metadata(item_id, heading=title, description=description, size=size)
        return False
    
    if "cancel-edit-btn" in ctx_triggered:
        return False
        
    return is_open

# Create new dashboard
@app.callback(
    Output("create-dashboard-output", "children"),
    Input("create-dashboard-btn", "n_clicks"),
    [State("new-dashboard-name", "value"),
     State("new-dashboard-desc", "value")]
)
def create_new_dashboard(n_clicks, name, description):
    if n_clicks is None:
        raise PreventUpdate
    
    if not name:
        return dbc.Alert("Please enter a dashboard name", color="warning")
    
    try:
        dashboard_id = create_dashboard(name, description)
        
        return html.Div([
            dbc.Alert(f"Dashboard '{name}' created successfully!", color="success"),
            dbc.Button("View Dashboard", href="/client-view", color="primary", className="mt-2")
        ])
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return dbc.Alert(f"Error: {str(e)}", color="danger")

# Load existing dashboards
@app.callback(
    Output("manage-dashboards-content", "children"),
    Input("url", "pathname")
)
def load_manage_dashboards(pathname):
    if pathname != '/management':
        raise PreventUpdate
        
    # Load current dashboards
    client_data = load_client_data()
    dashboards = client_data.get("dashboards", [])
    
    if not dashboards:
        return html.Div("No dashboards found. Create a new dashboard in the Create Dashboard tab.")
    
    dashboard_cards = []
    
    for dash in dashboards:
        # Count items
        item_count = len(dash.get("items", []))
        
        # Parse dates
        created_at = datetime.fromisoformat(dash["created_at"]).strftime('%Y-%m-%d %H:%M')
        updated_at = datetime.fromisoformat(dash["updated_at"]).strftime('%Y-%m-%d %H:%M')
        
        card = dbc.Card([
            dbc.CardHeader(html.H5(dash["name"])),
            dbc.CardBody([
                html.P(dash["description"]),
                html.P([
                    html.Strong("Created: "), created_at, html.Br(),
                    html.Strong("Updated: "), updated_at, html.Br(),
                    html.Strong("Items: "), str(item_count)
                ]),
                dbc.Button("View Dashboard", href="/client-view", color="primary", className="me-2"),
                dbc.Button("Delete", id={"type": "delete-dash-btn", "index": dash["id"]}, color="danger")
            ])
        ], className="mb-3")
        
        dashboard_cards.append(card)
    
    return html.Div(dashboard_cards)

# Pattern-matching callback for removing graphs
@app.callback(
    Output("dashboard-content", "children", allow_duplicate=True),
    [Input({"type": "remove-graph-btn", "index": ALL}, "n_clicks")],
    [State({"type": "remove-graph-btn", "index": ALL}, "id"),
     State("dashboard-dropdown", "value"),
     State("filter-dates", "data"),
     State("edit-mode", "data")],
    prevent_initial_call=True
)
def remove_graph(n_clicks_list, btn_ids, dashboard_id, filter_dates, edit_mode):
    ctx_triggered = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if not ctx_triggered or not any(n_clicks_list):
        raise PreventUpdate
    
    # Find which button was clicked
    for i, n_clicks in enumerate(n_clicks_list):
        if n_clicks:
            try:
                item_id = json.loads(ctx_triggered.replace("'", '"'))["index"]
                remove_from_dashboard(item_id)
                
                # Force refresh of dashboard content
                return display_dashboard(dashboard_id, filter_dates, edit_mode, None, None)
            except:
                # If parsing fails, try to get ID from the saved state
                if i < len(btn_ids):
                    item_id = btn_ids[i]["index"]
                    remove_from_dashboard(item_id)
                    
                    # Force refresh of dashboard content
                    return display_dashboard(dashboard_id, filter_dates, edit_mode, None, None)
    
    raise PreventUpdate

# Pattern-matching callback for deleting dashboards
@app.callback(
    Output("manage-dashboards-content", "children", allow_duplicate=True),
    [Input({"type": "delete-dash-btn", "index": ALL}, "n_clicks")],
    [State({"type": "delete-dash-btn", "index": ALL}, "id"),
     State("url", "pathname")],
    prevent_initial_call=True
)
def delete_dashboard(n_clicks_list, btn_ids, pathname):
    ctx_triggered = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if not ctx_triggered or not any(n_clicks_list):
        raise PreventUpdate
    
    # Find which button was clicked
    for i, n_clicks in enumerate(n_clicks_list):
        if n_clicks:
            try:
                dashboard_id = json.loads(ctx_triggered.replace("'", '"'))["index"]
                
                # Load client data
                client_data = load_client_data()
                
                # Get dashboard items
                dashboard = next((d for d in client_data["dashboards"] if d["id"] == dashboard_id), None)
                if dashboard:
                    # Remove all items from this dashboard
                    for item_id in dashboard.get("items", []):
                        remove_from_dashboard(item_id)
                    
                    # Remove dashboard
                    client_data["dashboards"] = [d for d in client_data["dashboards"] if d["id"] != dashboard_id]
                    save_client_data(client_data)
                
                # Refresh dashboard list
                return load_manage_dashboards(pathname)
            except:
                # If parsing fails, try to get ID from the saved state
                if i < len(btn_ids):
                    dashboard_id = btn_ids[i]["index"]
                    
                    # Load client data
                    client_data = load_client_data()
                    
                    # Get dashboard items
                    dashboard = next((d for d in client_data["dashboards"] if d["id"] == dashboard_id), None)
                    if dashboard:
                        # Remove all items from this dashboard
                        for item_id in dashboard.get("items", []):
                            remove_from_dashboard(item_id)
                        
                        # Remove dashboard
                        client_data["dashboards"] = [d for d in client_data["dashboards"] if d["id"] != dashboard_id]
                        save_client_data(client_data)
                    
                    # Refresh dashboard list
                    return load_manage_dashboards(pathname)
    
    raise PreventUpdate

# Handle dashboard layout drag and drop (client-side implementation)
app.clientside_callback(
    """
    function(dragData, dashboardId) {
        if (!dragData || !dashboardId) return window.dash_clientside.no_update;
        
        // Process drag data and update the layout order
        let layoutOrder = {};
        for (let key in dragData) {
            // Extract item ID from the key (e.g., "item-123456")
            let itemId = key.replace("item-", "");
            // Store the new position
            layoutOrder[itemId] = dragData[key].order;
        }
        
        // Call a server-side function to update the layout order
        // In a real implementation, you would use a Dash callback or API to update the server
        console.log("Layout order updated:", layoutOrder);
        
        return layoutOrder;
    }
    """,
    Output("dashboard-layout", "data"),
    [Input("drag-container", "layout")],
    [State("dashboard-dropdown", "value")]
)

# Save dashboard layout order changes
@app.callback(
    Output("dashboard-content", "children", allow_duplicate=True),
    [Input("dashboard-layout", "data")],
    [State("dashboard-dropdown", "value"),
     State("filter-dates", "data"),
     State("edit-mode", "data")],
    prevent_initial_call=True
)
def save_layout_order(layout_order, dashboard_id, filter_dates, edit_mode):
    if not layout_order or not dashboard_id:
        raise PreventUpdate
    
    # Update the layout order in the database
    update_layout_order_from_drag(dashboard_id, layout_order)
    
    # Force refresh of dashboard content
    return display_dashboard(dashboard_id, filter_dates, edit_mode, None, None)

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run_server(host='0.0.0.0', port=port, debug=False)