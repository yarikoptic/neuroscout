import os
import pytest
from flask_security.utils import encrypt_password
from app import app as _app
from database import db as _db

import sqlalchemy as sa


@pytest.fixture(scope='session')
def app():
    """Session-wide test `Flask` application."""
    if 'APP_SETTINGS' in os.environ:
        if os.environ['APP_SETTINGS'] != 'config.TravisConfig':
            _app.config.from_object('config.TestingConfig')
    else:
        _app.config.from_object('config.TestingConfig')

    # Establish an application context before running the tests.
    ctx = _app.app_context()
    ctx.push()

    yield _app

    ctx.pop()

@pytest.fixture(scope='session')
def db(app):
    """Session-wide test database."""
    _db.init_app(app)
    _db.create_all()

    yield _db

    _db.session.remove()
    _db.drop_all()

@pytest.fixture(scope='function')
def session(db):
    """Creates a new db session for a test."""
    connection = db.engine.connect()
    transaction = connection.begin()

    options = dict(bind=connection, binds={})
    session = db.create_scoped_session(options=options)

    session.begin_nested()

    # session is actually a scoped_session
    # for the `after_transaction_end` event, we need a session instance to
    # listen for, hence the `session()` call
    @sa.event.listens_for(session(), 'after_transaction_end')
    def resetart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            session.expire_all()
            session.begin_nested()

    db.session = session

    yield session

    print("Rollin")
    session.remove()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def add_users(app, db, session):
    """ Adds a test user to db """
    from flask_security import SQLAlchemyUserDatastore
    from models.auth import User, Role

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)

    user1 = 'test1'
    pass1 = 'test1'

    user_datastore.create_user(email=user1, password=encrypt_password(pass1))
    session.commit()
    id_1 = user_datastore.find_user(email=user1).id

    user_datastore.create_user(email='test2', password=encrypt_password('test2'))
    session.commit()
    id_2 = user_datastore.find_user(email='test2').id

    yield (id_1, id_2), (user1, pass1)

@pytest.fixture(scope="function")
def auth_client(add_users):
    from tests.request_utils import Client

    _ , (username, password) = add_users
    client = Client(username=username, password=password)
    return client