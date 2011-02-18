import hashlib
import os

import flask

import llvmlab.data
import llvmlab.user
import llvmlab.ui.views

class App(flask.Flask):
    @staticmethod
    def create_standalone(config = None, data = None):
        # Construct the application.
        app = App(__name__)

        # Load the application configuration.
        app.load_config(config)

        # Load the database.
        app.load_data(data)

        # Load the application routes.
        app.register_module(llvmlab.ui.views.ui)

        return app

    @staticmethod
    def create_test_instance():
        secret_key = "not so secret"

        # Manually construct a test configuration.
        #
        # FIXME: Would be nice to vet that this matches the sample config.
        config = {
            "ADMIN_LOGIN" : "admin",
            "ADMIN_PASSHASH" : hashlib.sha256(
                "admin" + secret_key).hexdigest(),
            "ADMIN_NAME" : "Administrator",
            "ADMIN_EMAIL" : "admin@example.com",
            "DEBUG" : True,
            "SECRET_KEY" : secret_key,
            "DATA_PATH" : None }

        # Construct an empty test database.
        data = llvmlab.data.Data(users = [])

        return App.create_standalone(config, data)

    def __init__(self, name):
        super(App, self).__init__(name)

    def load_config(self, config = None):
        if config is None:
            # Load the configuration file.
            self.config.from_envvar("LLVMLAB_CONFIG")
        else:
            self.config.update(config)

        # Set the application secret key.
        self.secret_key = self.config["SECRET_KEY"]

        # Set the debug mode.
        self.debug = self.config["DEBUG"]

    def load_data(self, data = None):
        if data is None:
            data_path = self.config["DATA_PATH"]
            data_file = open(data_path, "rb")
            data_object = flask.json.load(data_file)
            data_file.close()

            # Create the internal Data object.
            data = llvmlab.data.Data.fromdata(data_object)

        # Set the admin pseudo-user.
        data.set_admin_user(llvmlab.user.User(
                id = self.config['ADMIN_LOGIN'],
                passhash = self.config['ADMIN_PASSHASH'],
                name = self.config['ADMIN_NAME'],
                email = self.config['ADMIN_EMAIL']))

        self.config.data = data

    def authenticate_login(self, username, password):
        passhash = hashlib.sha256(
            password + self.config["SECRET_KEY"]).hexdigest()
        user = self.config.data.users.get(username)
        return user and passhash == user.passhash
