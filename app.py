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
import boto3
import hmac
import hashlib
import dash_draggable
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('insights-dashboard')

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

# Configure Cognito values from environment variables
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-southeast-2_Zezx8S9cn")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "578tc1t3a5gmfe7fqqju3hdopj")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET", "1mlhgcqhtihirabgrm3pal3etc3huh86errlc7spr7k6qhkafou4")

# Create a User class for Flask-Login
class User(UserMixin):
    def __init__(self, username):
        self.id = username

# User loader callback for Flask-Login
@login_manager.user_loader
def load_user(username):
    return User(username)

# MongoDB connection with error handling
try:
    # Use environment variables for MongoDB connection
    MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://vans1:Vans123456789!@insights.3jr7t.mongodb.net/?retryWrites=true&w=majority&appName=Insights")
    client = pymongo.MongoClient(MONGO_URI,
        tls=True,
        tlsAllowInvalidCertificates=False,
        serverSelectionTimeoutMS=5000
    )
    # Test connection
    client.admin.command('ping')
    logger.info("Successfully connected to MongoDB")
    db = client["insights_live"]
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    # Create a fallback for testing
    db = None

# Define color palettes
COLOR_PALETTES = {
    "vibrant": ["#FF9E00", "#12A4D9", "#9B4DCA", "#DD4124", "#7CB518"],
    "pastel": ["#FFD3B5", "#B5DEFF", "#D5C5FC", "#BCDFC9", "#FEBFB3"],
    "corporate": ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD"]
}

# In-memory storage for dashboards and settings - this replaces file storage
DASHBOARDS_STORAGE = {"dashboards": [], "graphs": [], "layouts": []}
USER_PERMISSIONS = {"users": {}}

# Helper function to create secret hash
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

# Login function with error handling
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
        logger.error(f"Login error: {e}")
        return False, str(e)

# Load client dashboards from storage
def load_client_data():
    return DASHBOARDS_STORAGE

# Save client data to storage
def save_client_data(data):
    global DASHBOARDS_STORAGE
    DASHBOARDS_STORAGE = data
    return True

# Date parsing function 
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
                logger.warning(f"Failed to parse date: {date_str}")
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
    try:
        test_document = db.events.find_one({"orgId": org_id, "appId": app_id})
    except Exception as e:
        logger.error(f"Error fetching test document: {e}")
        test_document = None
    
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
        logger.error(f"Error filtering graph data: {e}")
    
    return filtered_data

# Fetch location data for mapping
def get_location_data(query):
    """Extract location data from MongoDB for mapping"""
    try:
        if db is None:
            return []
            
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
        logger.error(f"Error getting location data: {e}")
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

# Main page routing callback with error handling
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
            try:
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
            except Exception as e:
                logger.error(f"Error during login process: {e}")
                return create_navbar(), html.Div([
                    login_layout,
                    dbc.Alert(f"An error occurred during login. Please try again later.", color="danger")
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

# Load organizations with error handling
@app.callback(
    Output('org-dropdown', 'options'),
    Input('url', 'pathname'),
    State('auth-user', 'data')
)
def load_organizations(pathname, user):
    if pathname != '/analytics' or not user:
        return []
    
    try:
        if db is None:
            # Return mock data if DB is not available
            return [{"label": "Demo Organization (demo1)", "value": "demo1"}]
            
        org_ids = db.events.distinct("orgId")
        org_options = []
        
        for org_id in org_ids:
            org = db.organisations.find_one({"_id": org_id})
            if org and "name" in org:
                org_options.append({"label": f"{org['name']} ({org_id})", "value": org_id})
            else:
                org_options.append({"label": f"Organization {org_id}", "value": org_id})
        
        return sorted(org_options, key=lambda x: x["label"])
    except Exception as e:
        logger.error(f"Error loading organizations: {e}")
        # Return mock data on error
        return [{"label": "Demo Organization (demo1)", "value": "demo1"}]

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
    
    try:
        if db is None:
            # Return mock data if DB is not available
            return [{"label": "Demo App", "value": "demo-app"}]
            
        apps = list(db.events.distinct("appId", {"orgId": org_id}))
        apps = [app for app in apps if app is not None]
        
        return [{"label": app, "value": app} for app in sorted(apps)]
    except Exception as e:
        logger.error(f"Error loading apps: {e}")
        # Return mock data on error
        return [{"label": "Demo App", "value": "demo-app"}]

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
    
    try:
        if db is None:
            # Return mock data if DB is not available
            return [
                {"label": "Click", "value": "click"},
                {"label": "View", "value": "view"},
                {"label": "Purchase", "value": "purchase"}
            ]
            
        event_types = []
        
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
        
        # Remove duplicates and sort
        event_types = sorted(list(set(event_types)))
        
        return [{"label": event_type, "value": event_type} for event_type in event_types]
    except Exception as e:
        logger.error(f"Error loading event types: {e}")
        # Return mock data on error
        return [
            {"label": "Click", "value": "click"},
            {"label": "View", "value": "view"},
            {"label": "Purchase", "value": "purchase"}
        ]

# Store selected values
@app.callback(
    [Output('selected-org', 'data'),
     Output('selected-app', 'data')],
    [Input('org-dropdown', 'value'),
     Input('app-dropdown', 'value')]
)
def store_selections(org_id, app_id):
    return org_id, app_id

# This is the main entry point
if __name__ == '__main__':
    # Create a default dashboard for demo purposes
    if not DASHBOARDS_STORAGE["dashboards"]:
        dashboard_id = create_dashboard("Default Dashboard", "Default dashboard for demonstration")
        logger.info(f"Created default dashboard with ID: {dashboard_id}")
    
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 8080))
    
    # Start the server with proper host and port
    logger.info(f"Starting server on port {port}")
    app.run_server(host='0.0.0.0', port=port, debug=False)