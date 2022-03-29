import definitions
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, session

Session = sessionmaker()


def prepare(connection_string):
    try:
        engine = create_engine(connection_string)
        definitions.Base.metadata.create_all(engine)
        global Session
        Session = sessionmaker(bind=engine)
    except:
        return False
    return True


def getSession() -> session:
    return Session()