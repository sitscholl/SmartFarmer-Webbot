from flask import Flask
from flask import render_template
import datetime
import pandas as pd
import numpy as np
import os
from functions.fetch_smartfarmer import fetch_smartfarmer
import subprocess
from pathlib import Path
app = Flask(__name__)

@app.route('/')
def hello_geek():
    if Path('results/tbl_string.csv').is_file():
        tbl = pd.read_csv('results/tbl_string.csv', header=[0,1,2])
        tbl.rename(columns = lambda x: '' if 'Unnamed' in x else x, inplace = True)
        data = {i: tbl[i].to_html() for i in np.unique(tbl.columns.get_level_values(0)) if i != ''}
    else:
        data = None
    print(data)
    content = render_template(
        "main_page.html",
        date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        data = data
    )
    return(content)
    
#https://stackoverflow.com/questions/42601478/flask-calling-python-function-on-button-onclick-event
#background process happening without any refreshing
@app.route('/update_data')
def background_process_test():
    subprocess.run(['python', 'main.py'])
    return ("nothing")

if __name__ == "__main__":
    app.run(debug=True)