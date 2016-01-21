import flask
import settings
import traceback
from networkx.readwrite import json_graph
import networkx as nx
from flask import Flask
from flask_restful import Resource, Api, reqparse
import os
import json
import time
import logging

''' 
Use like:
curl -i http://130.245.145.75:5000/13812
curl -i http://130.245.145.75:5000/<as_num>
to get the JSON representation for the AS's graph/
'''

SECS_IN_DAY = 24 * 60 * 60
notFoundJSON = { 'error': "Could not find record" }
all_graphs = {}
app = Flask(__name__)
api = Api(app)
logging.basicConfig( filename=settings.ASTORIA_SERVER_LOG, level=logging.DEBUG )

# This method will get the new graphs built in the last 24 hours.
def get_updates():
    current_time = time.time()
    files = [ x for x in os.listdir( settings.GRAPH_DIR ) \
              if os.path.isfile( os.path.join( settings.GRAPH_DIR, x ) ) ]
    files = [ os.path.join( settings.GRAPH_DIR, f ) for f in files ]

    files.sort(key=lambda x: os.path.getmtime(x))
    updated_files = []
    for f in files:
        if ( current_time - os.path.getmtime( f ) ) < SECS_IN_DAY:
            updated_files.append( f )
    updates_json = {}
    for f in updated_files:
        filestr = f.split( '/' )[ -1 ]
        asn = filestr.split( '-' )[ 0 ]
        with open( f ) as fi:
            jsonStr = json.load( fi )
        updates_json[ asn ] = jsonStr
    return flask.jsonify( updates_json )

def get_files_dict():
    relevant_files = os.listdir( settings.GRAPH_DIR )
    asn_file_dict = {}
    for fname in relevant_files:
        asn = fname.split( '-' )[ 0 ].split( 'AS' )[ 1 ]
        asn_file_dict[ asn ] = fname
    return asn_file_dict
    
def get_as_graph( asn ):
    asn_to_file = get_files_dict()
    found = asn in asn_to_file
    if not found:
        logging.warning( "Could not find AS path for " + asn )
        return flask.jsonify( notFoundJSON )
    else:
        with open( settings.GRAPH_DIR + asn_to_file[ asn ] ) as json_file:
            json_data = json.load(json_file)
        return flask.jsonify(json_data)

class ASPath( Resource ):
    def get( self ):
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument('src', type=str, required=True )
        parser.add_argument('dst', type=str, required=True )
        args = parser.parse_args()
        src = args[ "src" ]
        dst = args[ "dst" ]
        if dst in all_graphs and 'AS' + src in all_graphs[ dst ].nodes():
            paths = nx.all_simple_paths( all_graphs[ dst ], 'AS' + src, 'AS' + dst )
            path_dict = {}
            count = 1
            for p in list( paths ):
                path_dict[ count ] = p
                count += 1
            return flask.jsonify( path_dict )
        else:
            logging.warning( "Could not find AS path for " + dst )
            return notFoundJSON
        
class AutonomousSystem(Resource):
    def get(self, asn):
        try:
            return get_as_graph( asn )
        except Exception as ex:
            logging.exception( str( ex ) )

class ASUpdates(Resource):
    def get( self ):
        try:
            js = get_updates()
        except:
            print traceback.format_exc()
        return js
    
def load_graphs_in_mem():
    files = [ x for x in os.listdir( settings.GRAPH_DIR ) \
              if os.path.isfile( os.path.join( settings.GRAPH_DIR, x ) ) ]
    files = [ os.path.join( settings.GRAPH_DIR, f ) for f in files ]

    all_graphs = {}
    for f in files:
        filestr = f.split( '/' )[ -1 ]
        asnStr = filestr.split( '-' )[ 0 ]
        asn = asnStr.split( 'AS' )[ 1 ]
        with open( f ) as fi:
            jsonStr = json.load( fi )
        all_graphs[ asn ] = json_graph.node_link_graph( jsonStr )
    print "Loaded graphs in memory"
    return all_graphs

all_graphs = load_graphs_in_mem()

api.add_resource( AutonomousSystem, '/<string:asn>')
api.add_resource( ASUpdates, '/daily-update')
api.add_resource( ASPath, '/path', endpoint='path' )

if __name__ == '__main__':
    app.run(host='0.0.0.0')
