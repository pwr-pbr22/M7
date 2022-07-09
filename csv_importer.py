import pandas as pd

import db
from configuration import ProjectConfiguration
from definitions import Commit


def import_values(df):
    session = db.get_session()
    for index, row in df.iterrows():
        commit = Commit()
        commit.id = str(row['commit_id'])
        commit.buggy = bool(row['buggy'])
        commit.project = str(row['project'])
        commit.la = int(row['la'])
        commit.ld = int(row['ld'])
        commit.nf = int(row['nf'])
        commit.nd = int(row['nd'])
        commit.ns = int(row['ns'])
        commit.ent = float(row['ent'])
        commit.ndev = float(row['ndev'])
        commit.age = float(row['age'])
        commit.nuc = float(row['nuc'])
        commit.aexp = int(row['aexp'])
        commit.arexp = float(row['arexp'])
        commit.asexp = float(row['asexp'])
        session.merge(commit)
        session.commit()
    session.close()


if __name__ == '__main__':
    config = ProjectConfiguration()
    db.prepare(config.connstr)
    csv_file = pd.read_csv(config.csv_path)
    import_values(csv_file)
