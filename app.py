
# initialize application
from flask import Flask
app = Flask(__name__)

# get
@app.route('/')  # the default is GET only
def blog():
    # ...

#post
@app.route('/new', methods=['POST'])
def new():
    # ...



# run application
if __name__ == '__main__':
    app.run(host='0.0.0.0')
