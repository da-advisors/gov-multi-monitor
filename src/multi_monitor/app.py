from flask import Flask, render_template
from .db import MonitorDB

# Flask constructor takes the name of 
# current module (__name__) as argument.
app = Flask(__name__)

db = MonitorDB('../data/monitor.db', read_only=True)

# The route() function of the Flask class is a decorator, 
# which tells the application which URL should call 
# the associated function.
@app.route('/')
# ‘/’ URL is bound with hello_world() function.
def landing_home():

    return render_template(
        'multi_page/landing_page.html',
        data_collections_count=100,
        data_resources_count=10000,
        unavailable_collections_count=1,
        partially_unavailable_collections_count=2,
        stale_collections_count=3
    )

@app.route('/resources')
def list_resources():
    results = db._read_query(
        """
        SELECT * FROM resources
        """)
    return results

@app.route('/resources/<resource_id>')
def show_resource_details(resource_id: str):
    # TODO: Make as safer executition string.
    results = db._read_query(
    f"""
    SELECT * FROM resources
    WHERE id = '{resource_id}';
    """
    )
    column_headers = [field[0] for field in results[0]]
    body = results[1][0]
    
    return render_template(
        "multi_page/resource_detail.html",
        resource = {
            'name': body[1],
            'type': body[2],
            'url': body[3],
            # "metadata" field in [4]
            'created_at': body[5]
        }
    )




# main driver function
if __name__ == '__main__':

    # run() method of Flask class runs the application 
    # on the local development server.
    app.run()
