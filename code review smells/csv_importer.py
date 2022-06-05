import pandas as pd

import db
from configuration import ProjectConfiguration
from definitions import Commit


def import_values(df):
    session = db.get_session()
    for index, row in df.iterrows():
        commit = session.query(Commit).get(row['commit_id'])
        if commit is not None:
            commit.buggy = bool(row['buggy'])
            print("Assigned")
            session.merge(commit)
            session.commit()
    session.close()


if __name__ == '__main__':
    config = ProjectConfiguration()
    db.prepare(config.connstr)
    csv_file = pd.read_csv(config.csv_path)
    import_values(csv_file)
