from flask import Flask, render_template
from .db import MonitorDB

# Flask constructor takes the name of 
# current module (__name__) as argument.
app = Flask(__name__)

db = MonitorDB('../data/monitor.db')

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

@app.route('')

# main driver function
if __name__ == '__main__':

    # run() method of Flask class runs the application 
    # on the local development server.
    app.run()
