from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import definitions

Session = sessionmaker()


def prepare(connection_string):
    engine = create_engine(connection_string)
    definitions.Base.metadata.create_all(engine)
    global Session
    Session = sessionmaker(bind=engine)


def getSession():
    return Session()
