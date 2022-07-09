from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import definitions

Session = sessionmaker()


def prepare(connection_string):
    try:
        engine = create_engine(connection_string)
        definitions.Base.metadata.create_all(engine)
        global Session
        Session = sessionmaker(bind=engine)
    except Exception as err:
        print(err)
        return False
    return True


def get_session():
    return Session()
