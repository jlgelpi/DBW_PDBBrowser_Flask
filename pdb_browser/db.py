from flask_mysqldb import MySQL
from flask import current_app, g
from flask.cli import with_appcontext

mysql = MySQL(current_app)


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)