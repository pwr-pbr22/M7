from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import definitions

Session = sessionmaker()


def prepare(connection_string):
    engine = create_engine(connection_string, pool_size=50, max_overflow=50)
    definitions.Base.metadata.create_all(engine)
    global Session
    Session = sessionmaker(bind=engine)


def get_session():
    return Session()
