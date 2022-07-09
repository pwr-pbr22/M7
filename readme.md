# Prediction of software defects based on code review smells and metrics for pull requests
Research conducted as part of Research and _Development Project in Software Engineering_ course at [Wrocław University of Science and Technology](https://pwr.edu.pl/en/) by:
- Krzysztof Baciejowski ([ORCID](https://orcid.org/0000-0001-9572-1625?lang=en))
- Damian Garbala
- Szymon Żmijewski
- Lech Madeyski ([ORCID](https://orcid.org/0000-0003-3907-3357?lang=en))

## How to run?
> ⚠️ Reproduction of _E. Dogan, E. Tuzun, Towards a taxonomy of code review smells, Information and Software Technology 142 (2022)_ is located [on separate branch](https://github.com/pwr-pbr22/M7/tree/reproduction).

### Required software and packages
- [Python >=3.7](https://www.python.org/downloads/)
- [JupyterLab](https://jupyter.org/install)
- [PostgreSQL](https://www.postgresql.org/download/)
- [all packages specified in requirements.txt](https://pip.pypa.io/en/stable/user_guide/#requirements-files)

### Required data
- Program requires dataset [_K. Hossein, N. Meiyappan, ApacheJIT: A Large Dataset for Just-In-Time Defect Prediction_](https://zenodo.org/record/5907847), located in file apachejit\dataset\apachejit_total.csv
- To retrieve data from github API you will need [github token](https://github.com/settings/tokens/new), no permissions needed (with it user can send up to 5000 requests per hour, app allows to utilize more than one token).

### Configuration
Copy file **config.template.properties** with name **config.properties** and fill according to the template below:
```
[Config]
connstr=postgresql://{DbUser}:{Password}@localhost:5432/{DbName}
projects={project1},{project2}
gh_keys={token1},{token2}
csv_path={Path to apachejit_total.csv}
```
<details>
<summary>List of proper project values</summary>
Analysis can be performed for:
- apache/ignite
- apache/hadoop-mapreduce
- apache/groovy
- apache/zookeeper
- apache/hbase
- apache/kafka
- apache/activemq
- apache/zeppelin
- apache/camel
- apache/spark
- apache/flink
- apache/cassandra
- apache/hadoop-hdfs
- apache/hadoop
- apache/hive
</details>

eg.
```
[Config]
connstr=postgresql://postgres:password@localhost:5432/pbr
projects=apache/flink
gh_keys=ghp_s5OAH0D9a2NFjzBU7PF3POgUURvuiR00S22a
csv_path=C:/shared/apachejit_total.csv
```

## Importing data from CSV
To import data execute script **csv_importer.py**.
> 💡 To execute .py file in JupyterLab you can do one of:
> 1. Use editor console
> - open the file, 
> - right click on text area,
> - select "Create console for editor",
> - select code you want to execute (here ctrl+A),
> - click shift+enter to execute.
>
> 2. Open Pythoon console in Jupyter lab and run ```%run csv_importer.py``` with shift+enter.
>
> 3. Simply use integrated sytem terminal.

This step can take about minute. There are no obstacles to run it multiple times.

### Downloading data from github
To download required data execute script **downloader.py**.

> ⚠️ Asyncio library isn't working properly in Ipython, thus usage of system terminal is necessary.

> ✅ ```OSError22, 'The semaphore timeout period has expired'``` is a Windows thing, which does not affect downloading in other way than prolonging it (sometimes updating network drivers helps).
>
> ✅ ```Session closed exception``` after downloading project can happen, however this and previous project data won't be affected.

This step can take hours depending on number of tokens and number of requests allowed. There are no obstacles to run it multiple times.

> 💡 Some repositories are available in **db** file which can be imported to your Postgres database. To check available repositories run ```SELECT full_name FROM repo```.

### Run data analysis in main.ipynb
Execute notebook cell by cell and get the results.

> ⚠️ JupyterLab displays results better than Jupyter Notebook (no unnecessary scrolling), while Pycharm implementation of Jupyer Notebooks is problematic, thus we advise to use JupyterLab.
