from flask import current_app

# Index page
@current_app.route('/pdb')
def index():
    return render_template('index.html')
