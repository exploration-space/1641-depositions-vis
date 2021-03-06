# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

import dash_table


import plotly.graph_objs as go
import pandas as pd
import json
import itertools

import networkx as nx
import numpy as np
from matplotlib import cm
from matplotlib.colors import Normalize

import colorlover as cl 

from Levenshtein import ratio
from scipy.spatial.distance import pdist, squareform


import os

from datetime import date

print(dash.__version__)

if os.environ['MAPBOX_ACCESS_TOKEN'] is None:
    sys.exit('Please provide a mapbox access token as environment variable: export MAPBOX_ACCESS_TOKEN=<Your token>')

mapbox_access_token = os.environ['MAPBOX_ACCESS_TOKEN']

EXTERNAL_VIEWER_URL = 'http://51.75.162.36:5000'
EXTERNAL_VIEWER_LINK = EXTERNAL_VIEWER_URL + "/id/%s"

app = dash.Dash(__name__)
server = app.server 

with open('./data/ireland-geo.json') as f:
    geojson = json.load(f)

def date_string_to_date(date_string):
    return date(
            int(date_string.split('-')[0]), 
            int(date_string.split('-')[1]), 
            int(date_string.split('-')[2]))

def create_person_counter_df(dff):
    #Generate persons graph

    print('Creating person counter out of %s depositions' % len(dff))

    name_counter = dict()
    names_list = []
    person2indx = {}
    indx2role = {}
    for i, deposition in dff.iterrows():
        dep_part = deposition['people_list']
        names = []
        for person in dep_part:
            person_str = ''
            forename = ''
            surname = ''
            if 'forename' in person and person['forename'] != '*':
                forename = person['forename'].lower()
            else:
                forename = 'Unknown'
            
            if 'surname' in person and person['surname'] != '*':
                surname = person['surname'].lower()
            else:
                surname = 'Unknown'

            person_str = forename + ' ' + surname


            if person_str not in person2indx:
                idx = len(person2indx)
                person_dict = dict({
                    'forename' : forename,
                    'surname' : surname,
                    'fullname' : person_str,
                    'depositions' : [i],
                    'count' : 1,
                    'roles' :{i: person['role']},
                    'idx': idx
                })
                name_counter[person_str] = person_dict
                person2indx[person_str] = idx
                indx2role[idx] = {i : person['role']}
            else:
                name_counter[person_str]['depositions'].append(i)
                name_counter[person_str]['roles'][i] = person['role']
                name_counter[person_str]['count'] += 1
                idx = person2indx[person_str]
                indx2role[idx][i] = person['role']

            names.append(person_str)
        names_list.append(names)

    indx2person = {v:k for k,v in person2indx.items()}

    print('Processed %s distinct names' % (len(indx2person.keys())))
    name_counts = [( v['idx'],
                 v['fullname'], 
                 v['forename'], 
                 v['surname'], 
                 v['count'],
                 v['depositions']
                 ) for v in name_counter.values()]

    names_counter_df = pd.DataFrame(name_counts, columns=['idx', 
                                                          'fullname',
                                                          'forename',
                                                          'surname',
                                                          'appearances',
                                                          'depositions'])
    names_counter_df.set_index('idx', inplace=True)

    # names_counter_df = names_counter_df.rename(columns={'index' : 'name', 0 : 'appearances'})
    names_counter_df.sort_values(by=['appearances'], ascending=False, inplace=True)

    return names_counter_df


def initialize():
    df = pd.read_json('./data/all_depositions.json')

    #Data amends/conversions
    #Dates

    print(len(df))

    df['creation_date_parsed'] = df['creation_date'].map(
        lambda x: date_string_to_date(x) if isinstance(x, str) else x)

    df['creation_year'] = df['creation_date'].str.slice(start=0, stop=4)
    df['creation_year'] = df['creation_year'].fillna('Unknown')

    #Places
    df.deponent_county = df.deponent_county.fillna('Unknown')

    df = df[df['people_list'].map(lambda d: len(d)) > 0]

    df.reset_index(inplace=True)


    
    # print(name_counter.most_common(40))

    # names = list(person2indx.keys())
    # print(names)

    # transformed_names = np.array(names).reshape(-1,1)
    # print(transformed_names)

    # print(transformed_names.shape)

    # distance_matrix = pdist(transformed_names, lambda x,y: 1 - ratio(x[0], y[0]))

    # print(squareform(distance_matrix))

    
    #Persons graph

    # G = nx.Graph()
    # for i, dep_names in enumerate(names_list):
    #     for person_a, person_b in itertools.combinations(dep_names, 2):
    #         G.add_edge(person2indx[person_a], person2indx[person_b], deposition=i)

    return df

df = initialize()
df = df[['creation_date_parsed', 'deponent_county', 'people_list', 'filename']]
df.reset_index(inplace=True)

person_counter_df = create_person_counter_df(df)
#Create index for depositions.
dates_list = df['creation_date_parsed'].copy()
dates_list.dropna(inplace=True)

min_date = dates_list.min()
max_date = dates_list.max()

n_counties = len(geojson['features'])

app.layout = html.Div(children=[
    html.H3(children='The 1641 Depositions'),

    html.Div(className='row', children=[
        html.Div([dcc.Graph(
                        id='timeline'), html.Div(id='debug-div')],
            className='four columns'),        

        html.Div([dcc.Graph(
                        id='map'), html.Div(id='link-div', children=[html.P("None selected")]), html.Span('       '), html.Div([html.Button('Graph', id='button-network'), html.Button('Heatmap', id='button-heatmap')],
            id='button-div')],
            className='four columns'),

        html.Div(dash_table.DataTable(
                        id='table',
                        columns=[{"name" : i, "id": i} for i in ["forename", "surname", "appearances"]],
                        filtering='be',
                        sorting=True,
                        style_table={
                            'maxHeight': '300px',
                            'overflowY': 'scroll',
                            'border': 'thin lightgrey solid'
                        }),
            className='four columns')]),

    html.Div(className='row', children=[
        html.Div(dcc.Graph(
                        id='network', figure={'layout':go.Layout(height=290)}),
            className='eight columns'),
        html.Div(dcc.Graph(
                        id='heatmap', figure={'layout':go.Layout(height=290)}),
            className='four columns')  
    ]),

    dcc.Store(id='memory')
])
    

def create_timeline(dff):
    #Counts by Date
    dates_counts = dff['creation_date_parsed'].value_counts()
    dates_counts.sort_index(inplace=True)
    dates = dates_counts.index.tolist()
    dates_c = [dates_counts[d] for d in dates]

    return  {
                'data': [go.Histogram(
                    x=dates,
                    y=dates_c,
                    opacity = 0.8,
                    marker=dict(
                        color='#16632d'),
                    xbins=dict(
                        start=min(dates),
                        end=max(dates),
                        size='M1'
                        ),
                    autobinx=False)],
                'layout': go.Layout(
                    autosize=False,
                    margin = dict(l=20, r=0, b=30, t=0),
                    xaxis=dict(
                        rangeselector=dict(
                            buttons=list([
                                dict(count=1,
                                     label='1m',
                                     step='month',
                                     stepmode='backward'),
                                dict(count=6,
                                     label='6m',
                                     step='month',
                                     stepmode='backward'),
                                dict(count=1,
                                    label='1y',
                                    step='year',
                                    stepmode='backward'),
                                dict(step='all')
                            ])
                        ),
                        rangeslider=dict(
                            visible = False
                        ),
                        type='date'
                    ),
                    height=290)
            }
            

def create_map(dff):
    def scalarmappable(cmap, cmin, cmax):
        colormap = cm.get_cmap(cmap)
        norm = Normalize(vmin=cmin, vmax=cmax)
        return cm.ScalarMappable(norm=norm, cmap=colormap)

    def get_scatter_colors(sm, df, counties):
        grey = 'rgba(128,128,128,1)'
        return ['rgba' + str(sm.to_rgba(df[c], bytes = True, alpha = 1)) \
            if df[c] != 0 else grey for c in counties]

    def get_colorscale(sm, df, cmin, cmax):
        arange = np.linspace(0, 1, len(df))
        values = np.linspace(cmin, cmax, len(df))

        return [[i, 'rgba' + str(sm.to_rgba(v, bytes = True))] for i,v in zip(arange, values) ]

    def get_hover_text(counts) :
        text_value = (counts).round(2).astype(str)
        with_data = '<b>{}:</b> <br> {} depositions'
        return [with_data.format(p,v) for p,v in zip(counts.index, text_value)]

    def get_centers(features):
        lon, lat = [], []
        n_counties = len(features)
        for k in range(n_counties):
            geometry = features[k]['geometry']

            if geometry['type'] == 'Polygon':
                coords=np.array(geometry['coordinates'][0])
            elif geometry['type'] == 'MultiPolygon':
                longest_idx = -1
                max_length = -1
                for i in range(len(geometry['coordinates'])):
                    poly_length = len(geometry['coordinates'][i][0])
                    if max_length < poly_length:
                        max_length = poly_length
                        longest_idx = i
                coords=np.array(geometry['coordinates'][longest_idx][0])

            lon.append(sum(coords[:,0]) / len(coords[:,0]))
            lat.append(sum(coords[:,1]) / len(coords[:,1]))
                
        return lon, lat


    #Counts by County
    features = sorted(geojson['features'], key=lambda k: k['properties']['CountyName'])
    county_names = sorted(list(set([k['properties']['CountyName'] for k in geojson['features']])))
    counts = dff['deponent_county'].value_counts()
    
    if 'Unknown' in counts.index:
        counts.drop('Unknown', inplace=True)

    for c in county_names:
        if c not in counts.index:
            counts[c] = 0
    
    counts.sort_index(inplace=True)

    # print(counts)

    colormap = 'Greens'
    cmin = counts.min()
    cmax = counts.max()

    lons, lats = get_centers(features)

    sm = scalarmappable(colormap, cmin, cmax)
    scatter_colors = get_scatter_colors(sm, counts, county_names)

    colorscale = get_colorscale(sm, counts, cmin, cmax)
    hover_text = get_hover_text(counts)


    layers = ([dict(sourcetype = 'geojson',
                  source = features[k],
                  below = "",
                  type = 'line',    # the borders
                  line = dict(width = 1),
                  color = 'black',
                  ) for k in range(len(features))] +

            [dict(sourcetype = 'geojson',
                 source = features[k],
                 below="water",
                 type = 'fill',
                 color = scatter_colors[k],
                 opacity=1
                ) for k in range(len(features))]
            )

    return {
                'data': [go.Scattermapbox(
                    lat=lats,
                    lon=lons,
                    mode='markers',
                    marker=dict(
                        size=1,
                        color=scatter_colors,
                        showscale=True,
                        cmin=cmin,
                        cmax=cmax,
                        colorscale=colorscale,
                        colorbar=dict(tickformat = ".0")
                    ),
                    text=hover_text,
                    customdata= counts.index,
                    showlegend=False,
                    hoverinfo='text'
                )],
                'layout': go.Layout(
                    autosize=False,
                    height=290,
                    clickmode='event+select',
                    dragmode='zoom',
                    hovermode='closest',
                    margin = dict(l=0, r=0, b=0, t=0),
                    mapbox=dict(
                        layers=layers,
                        accesstoken=mapbox_access_token,
                        bearing=0,
                        center=dict(
                            lat=53.4,
                            lon=-8
                        ),
                        pitch=0,
                        zoom=4.9,
                        style = 'light'
                    ),

                ) 
            }
            
def build_sq_distance_matrix(name_counter_dff, names):

    names = names or sorted(name_counter_dff['fullname'].tolist())
    print(names)

    transformed_names = np.array(names).reshape(-1,1)
    # print(transformed_names)

    print(transformed_names.shape)

    print(transformed_names[0])

    sq_distance_matrix = squareform(pdist(transformed_names, lambda x,y: ratio(x[0], y[0])))

    print(sq_distance_matrix.shape)
    print(sq_distance_matrix)
    return sq_distance_matrix


@app.callback(
    Output('network', 'figure'),
    [Input('button-network', 'n_clicks')],
    [State('memory', 'data')])
def create_graph(n_clicks, memData):
    prop = dash.callback_context.triggered[0]
    print(prop)
    if (prop['prop_id'] != 'button-network.n_clicks') or \
    (prop['prop_id'] == 'button-network.n_clicks' and prop['value'] == None):
        raise dash.exceptions.PreventUpdate

    name_counter_dff = pd.read_json(memData['person_counter_dff'])

    counts = name_counter_dff['depositions'].apply(pd.Series).stack().value_counts()

    G = nx.Graph() 
    for i in counts.index:
        dep_names = name_counter_dff[[int(i) in x for x in name_counter_dff['depositions']]]['fullname'].tolist()
        print(dep_names)
        for (name_a, name_b) in itertools.combinations(dep_names, 2):
            if G.has_edge(name_a, name_b):
                G[name_a][name_b]['depositions'].append(i)
                G[name_a][name_b]['weight'] += 1
                G[name_a][name_b]['text'] += ' %s' % i
            else:
                G.add_edge(name_a, name_b, depositions=[i], weight=1, text='Depositions : %s' % i)

    sq_distance_matrix = build_sq_distance_matrix(name_counter_dff, None)
    names = sorted(name_counter_dff['fullname'].tolist())

    optimal_dists = {}

    for row in range(0, len(names)):
        for col in range(row + 1, len(names)):
            try:
                nx.shortest_path(G, source=names[row], target=names[col])
            except:
                continue
                # optimal_dists[(names[row], names[col])] = nx.shortest_path_length(G, names[row], names[col]) * sq_distance_matrix[row][col]
            else:
                optimal_dists[(names[row], names[col])] = nx.shortest_path_length(G, names[row], names[col]) + 2 * (1 - sq_distance_matrix[row][col])
                
        

    print(optimal_dists)


    # pos = nx.layout.kamada_kawai_layout(G, dist=optimal_dists)
    # pos = nx.layout.kamada_kawai_layout(G)
    pos = nx.layout.spring_layout(G, k=0.5)
    
    for node in G.nodes:
        G.nodes[node]['pos'] = list(pos[node])



    print(name_counter_dff.head(20))
    
    edge_traces = [] 

    # cl_scale = cl.scales[str(len(counts.index))]['qual']['Paired'] 

    for e in G.edges(data=True):
        # color = cl_scale[counts.index.index(e[2]['weight']['depositions'][0])]
        x0, y0 = G.node[e[0]]['pos']
        x1, y1 = G.node[e[1]]['pos']
        edge_traces.append(go.Scatter(
                    x= tuple([x0, x1, None]),
                    y= tuple([y0, y1, None]),
                    line=dict(width=e[2]['weight'] / 2, color="#888"),
                    hoverinfo='text',
                    mode='lines'))

    node_trace = go.Scatter(
        x=[],
        y=[],
        text=[],
        mode='markers',
        hoverinfo='text')

    for node in G.nodes():
        x, y = G.node[node]['pos']
        node_trace['x'] += tuple([x])
        node_trace['y'] += tuple([y])
        node_trace['text'] += tuple([str(node)])

    return {
        'data': edge_traces + [node_trace],
        'layout': go.Layout(
            autosize=False,
            height=290,
            hovermode='closest',
            margin = dict(l=0, r=0, b=0, t=10),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    }


@app.callback(
    Output('link-div', 'children'),
    [Input('network', 'hoverData')],
    [State('memory', 'data')])
def select_nodes_in_network(hoverData, memoryData):
    if hoverData and len(hoverData['points']) > 0:
        name = hoverData['points'][0]['text']
        name_counter_dff = pd.read_json(memoryData['person_counter_dff'])
        appears_in = name_counter_dff[name_counter_dff['fullname'] == name]['depositions'].tolist()
        print(type(appears_in))
        print(appears_in)
         
        links = [html.A(x, target='_blank', href= EXTERNAL_VIEWER_LINK % df.loc[int(x)]['filename']) for x in appears_in[0]]
        return links
    else:
        raise dash.exceptions.PreventUpdate

# @app.callback(
#     Output('heatmap', 'selectedData'),
#     [Input('network', 'hoverData')],)
# def select_nodes_in_network(selectedData):
#     print(selectedData)
#     raise dash.exceptions.PreventUpdate


# @app.callback(
#     Output('network', 'hoverData'),
#     [Input('heatmap', 'hoverData')],
#     [State('network', 'figure')])
# def hover_nodes_in_network(hoverData, networkFigure):
#     if hoverData and len(hoverData['points']) > 0:
#         name_1 = hoverData['points'][0]['x']
#         name_2 = hoverData['points'][0]['y']
#         print('Selected %s and %s' % (name_1, name_2))
#         names = [name_1, name_2]

#     if networkFigure is not None:
#         curve_no = len(networkFigure['data']) - 1
#         trace = list(filter(lambda x: x['mode'] == 'markers', networkFigure['data']))[0]
#         hoveredPoints = []

#         for name in names:
#             name_pos = trace['text'].index(name)
#             print('%s appears at position %s' % (name, name_pos))
#             hoveredPoints.append({
#                     'curveNumber': trace_no,
#                     'pointNumber' : name_pos,
#                     'pointIndex': name_pos,
#                     'x': trace['x'][name_pos],
#                     'y': trace['y'][name_pos],
#                     'text': name
#                 })

#         print(hoveredPoints)
#         return {'points' : hoveredPoints[:1]}
#     else:
#         raise dash.exceptions.PreventUpdate

#     raise dash.exceptions.PreventUpdate    

            

    #{'points': [{'curveNumber': 173, 'pointNumber': 28, 'pointIndex': 28, 'x': -0.7759760926342992, 'y': 0.6059220634290629, 'text': 'thomas roch'}]}
    




@app.callback(
    Output('heatmap', 'figure'),
    [Input('button-heatmap', 'n_clicks')],
    [State('memory', 'data')])
def create_heatmap(n_clicks, memData):
    prop = dash.callback_context.triggered[0]
    print(prop)
    if (prop['prop_id'] != 'button-heatmap.n_clicks') or \
    (prop['prop_id'] == 'button-heatmap.n_clicks' and prop['value'] == None):
        raise dash.exceptions.PreventUpdate

    name_counter_dff = pd.read_json(memData['person_counter_dff']).sort_values(by=['surname'])
    print(name_counter_dff.head(10))
    forenames = name_counter_dff['forename'].tolist() 
    surnames = name_counter_dff['surname'].tolist()

    names = [surnames[i] + ', ' + forenames[i] for i in range(len(forenames))]

    print(forenames)
    print(surnames)
    print(names)
    
    # print(squareform(distance_matrix))

    # return {
    #     'data': [{
                
    #         }],
    #     'type': 'heatmap'
    # }

    return  {
                'data': [go.Heatmap(
                    z=build_sq_distance_matrix(name_counter_dff, names),
                    x=names,
                    y=names,
                    colorscale = 'Viridis')],
                'layout': go.Layout(
                    autosize=False,
                    margin = dict(l=0, r=0, b=0, t=0),
                    height=290)
            }


@app.callback(
    Output('table', 'data'),
    [Input('memory', 'modified_timestamp')],
    [State('memory', 'data')])

def update_table(timestamp, memData):
    if timestamp is None:
        raise dash.exceptions.PreventUpdate
    print('update TABLE')
    person_counter_df = pd.read_json(memData['person_counter_dff'])
    person_counter_df.sort_values(by=['appearances'], ascending=False, inplace=True)

    return person_counter_df.to_dict("rows")



@app.callback(
    Output('map', 'figure'),
    [Input('memory', 'modified_timestamp')],
    [State('memory', 'data')])

def update_map(timestamp, memData):
    # print(relayoutData)
    # if relayoutData and ('xaxis.range[0]' in relayoutData or 'xaxis.range' in relayoutData):
    #     # print(selectedData['points'][0]['x'])
    #     if 'xaxis.range[0]' in relayoutData:
    #         start_date = relayoutData['xaxis.range[0]'].split(" ")[0]
    #         end_date = relayoutData['xaxis.range[1]'].split(" ")[0]
    #     else:
    #         start_date = relayoutData['xaxis.range'][0].split(" ")[0]
    #         end_date = relayoutData['xaxis.range'][1].split(" ")[0]
    #     print(start_date, end_date)
    #     dff = df[(df['creation_date_parsed'] >= date_string_to_date(start_date)) & \
    #     (df['creation_date_parsed'] <= date_string_to_date(end_date))]
    #     # print(dff)
    #     return create_map(dff)
    # else:
    #     return create_map(df)
    if timestamp is None:
        raise dash.exceptions.PreventUpdate
    # print('current storage is {}'.format(memData))
    print('modified_timestamp is {}'.format(timestamp))

    return create_map(pd.read_json(memData['dff'])) 

# @app.callback(
#     Output('timeline', 'data'),
#     [Input('map', 'hoverData')])
# def update_timeline_with_map_hover():


@app.callback(
    Output('timeline', 'figure'),
    [Input('memory', 'modified_timestamp')],
    [State('memory', 'data')])

def update_timeline(timestamp, memData):
    if timestamp is None:
        raise dash.exceptions.PreventUpdate
    # print('current storage is {}'.format(memData))
    print('modified_timestamp is {}'.format(timestamp))

    
    return create_timeline(pd.read_json(memData['dff']))
    

# @app.callback(
#     Output('network', 'figure'),
#     [Input('timeline', 'relayoutData')])

# def update_network(relayoutData):
#     print(relayoutData)
#     if relayoutData and ('xaxis.range[0]' in relayoutData or 'xaxis.range' in relayoutData):
#         # print(selectedData['points'][0]['x'])
#         if 'xaxis.range[0]' in relayoutData:
#             start_date = relayoutData['xaxis.range[0]'].split(" ")[0]
#             end_date = relayoutData['xaxis.range[1]'].split(" ")[0]
#         else:
#             start_date = relayoutData['xaxis.range'][0].split(" ")[0]
#             end_date = relayoutData['xaxis.range'][1].split(" ")[0]
#         print(start_date, end_date)
#         dff = df[(df['creation_date_parsed'] >= date_string_to_date(start_date)) & \
#         (df['creation_date_parsed'] <= date_string_to_date(end_date))]
#         # print(dff)
#         return create_graph(dff, update=True)
#     else:
#         return create_graph(df)

@app.callback(
    Output('debug-div', 'children'),
    [Input('memory', 'modified_timestamp')],
    [State('memory', 'data')])

def update_output_div(timestamp, memData):
    if timestamp is None:
        raise dash.exceptions.PreventUpdate
    # print('current storage is {}'.format(memData))
    print('modified_timestamp is {}'.format(timestamp))
    print('update_output_div:')
    print(min_date)
    start_date = memData['start_date'] or min_date
    end_date = memData['end_date'] or max_date
    
    if len(memData['selected_counties']) == 0:
        counties = 'All counties'
        num_counties = n_counties
    else:
        counties = ",".join(memData['selected_counties'])
        num_counties = len(memData['selected_counties'])

    return [html.P('%s depositions in %s counties (%s) in period %s to %s' % \
        (memData['n_depositions'],
            num_counties, 
            str(counties),
            start_date,
            end_date)),
            html.P('%s distinct names referenced' % memData['person_count'])]

@app.callback(
    Output('memory', 'data'),
    [Input('map', 'clickData'),
    Input('timeline', 'relayoutData'),
    Input('table', 'filtering_settings')],
    [State('memory', 'data')])

def update_state(clickDataMap, relayoutData, filtering_settings, memData):
    # print('clickData:')
    # print(clickDataMap)
    # print('relayoutData:')
    # print(relayoutData)

    # print(dash.callback_context.triggered)

    if memData:
        print('memData:')
        print(memData['selected_counties'], memData['start_date'], memData['end_date'])
    else:
        
        depositions = sorted(list(set([d for l in person_counter_df['depositions'] for d in l])))
        memData = {
                    'selected_counties' : [], 
                    'start_date' : None, 
                    'end_date' : None, 
                    'dff' : df.to_json(),
                    'filtering_settings' : "",
                    'person_count': len(person_counter_df),
                    'person_counter_df': person_counter_df.to_json(),
                    'text_filter_depositions': depositions}

    prop_id = dash.callback_context.triggered[0]['prop_id']

    print('prop_id is %s' % prop_id)
    
    if prop_id == 'map.clickData':
        print('Changing counties')
        clicked_county = clickDataMap['points'][0]['customdata']
        if clicked_county not in memData['selected_counties']:
            print('Selecting')
            if memData['selected_counties'] is None:
                memData['selected_counties'] = []
            memData['selected_counties'].append(clicked_county)
            dff, person_counter_dff = filter_df_by_state(df, memData)
            memData['dff'] = dff.to_json()
            memData['n_depositions'] = len(dff)
            memData['person_counter_dff'] = person_counter_dff.to_json()
            memData['person_count'] = len(person_counter_dff)
        else:
            print('Deselecting')
            memData['selected_counties'].remove(clicked_county)
            dff, person_counter_dff = filter_df_by_state(df, memData)
            memData['dff'] = dff.to_json()
            memData['n_depositions'] = len(dff)
            memData['person_counter_dff'] = person_counter_dff.to_json()
            memData['person_count'] = len(person_counter_dff)

        return memData
        
    if prop_id == 'timeline.relayoutData': 
        if relayoutData and 'xaxis.range[0]' in relayoutData:
            print('Changing dates')
            start_date = relayoutData['xaxis.range[0]'].split(" ")[0]
            end_date = relayoutData['xaxis.range[1]'].split(" ")[0]
            print(start_date, end_date)
            
            memData['start_date'] = start_date
            memData['end_date'] = end_date

            dff, person_counter_dff = filter_df_by_state(df, memData)
            memData['dff'] = dff.to_json()
            memData['n_depositions'] = len(dff)
            memData['person_counter_dff'] = person_counter_dff.to_json()
            memData['person_count'] = len(person_counter_dff)
            return memData
        else:
            memData['start_date'] = None
            memData['end_date'] = None
            dff, person_counter_dff = filter_df_by_state(df, memData)
            memData['dff'] = dff.to_json()
            memData['n_depositions'] = len(dff)
            memData['person_counter_dff'] = person_counter_dff.to_json()
            memData['person_count'] = len(person_counter_dff)
            return memData


    if prop_id == 'table.filtering_settings':
        print('Filtering table: %s' % filtering_settings)
        if filtering_settings is not None:
            memData['filtering_settings'] = filtering_settings
            dff, person_counter_dff = filter_df_by_state(df, memData)
            memData['dff'] = dff.to_json()
            memData['n_depositions'] = len(dff)
            memData['person_counter_dff'] = person_counter_dff.to_json()
            memData['person_count'] = len(person_counter_dff)
            return memData

    return memData
    

def filter_df_by_state(df, memData):
    print('filter by state')
    dff = filter_df_by_county(df, memData['selected_counties'])
    dff = filter_df_by_dates(dff, memData['start_date'], memData['end_date'])
    person_counter_dff = create_person_counter_df(dff)

    
    if len(memData['filtering_settings']) == 0:
        print('filtering_expressions is 0')
        return dff, person_counter_dff
    
    filtering_expressions = memData['filtering_settings'].split(' && ')
    print(person_counter_dff.columns)
    # print(filtering_expressions)
    for filter in filtering_expressions:
        if 'eq' in filter:
            col_name = filter.split(' eq ')[0].replace('"','')
            filter_value = filter.split(' eq ')[1].replace('"','')
            # person_counter_dff = person_counter_dff[person_counter_dff[col_name] == filter_value]
            person_counter_dff = person_counter_dff[person_counter_dff[col_name].str.contains(filter_value)]
        if ' > ' in filter:
            col_name = filter.split(' > ')[0].replace('"','')
            filter_value = float(filter.split(' > ')[1])
            person_counter_dff = person_counter_dff[person_counter_dff[col_name] > filter_value]
        if ' < ' in filter:
            col_name = filter.split(' < ')[0]
            filter_value = float(filter.split(' < ')[1])
            dff = dff.loc[dff[col_name] < filter_value]
            person_counter_dff = person_counter_dff[person_counter_dff[col_name] < filter_value]

    
    # memData['person_counter_df'] = person_counter_dff
    text_filter_depositions = sorted(list(set([d for l in person_counter_dff['depositions'] for d in l])))
    # print(text_filter_depositions)
    dff = filter_df_by_text_filter(dff, text_filter_depositions)
    return dff, person_counter_dff

def filter_df_by_text_filter(df, text_filter_depositions):
    # print(text_filter_depositions)
    if len(text_filter_depositions) == 0: return df
    return df.loc[text_filter_depositions]
    

def filter_df_by_county(df, counties):
    print('Filter by counties: %s' % str(counties))
    if len(counties) == 0: return df
    return df[df['deponent_county'].isin(counties)]

def filter_df_by_dates(df, start_date, end_date):
    print('Filter by dates: %s - %s' % (start_date, end_date))
    if start_date and end_date:
        return df[(df['creation_date_parsed'] >= date_string_to_date(start_date)) & \
            (df['creation_date_parsed'] <= date_string_to_date(end_date))]
    else:
        return df


if __name__ == '__main__':
    app.run_server(debug=True)