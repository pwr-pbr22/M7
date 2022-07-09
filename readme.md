# Prediction of software defects based on code review smells and metrics for pull requests (Dogan and Tuzun reproduction)
Research conducted as part of the _Research and Development Project in Software Engineering_ course at [Wrocław University of Science and Technology](https://pwr.edu.pl/en/) by:
- Krzysztof Baciejowski ([ORCID](https://orcid.org/0000-0001-9572-1625?lang=en))
- Damian Garbala
- Szymon Żmijewski
- Lech Madeyski ([ORCID](https://orcid.org/0000-0003-3907-3357?lang=en))

## How to run?
> ⚠️ This is reproduction of _E. Dogan, E. Tuzun, Towards a taxonomy of code review smells, Information and Software Technology 142 (2022)_. Models creation scripts are available [on main branch](https://github.com/pwr-pbr22/M7).

### Required software and packages
- [Python >=3.7](https://www.python.org/downloads/)
- [PostgreSQL](https://www.postgresql.org/download/)
- [all packages specified in requirements.txt](https://pip.pypa.io/en/stable/user_guide/#requirements-files)

### Required data
- To retrieve data from github API you will need [github token](https://github.com/settings/tokens/new), no permissions needed (with it user can send up to 5000 requests per hour, app allows to utilize more than one token).

### Downloading data from Github
To download required data execute script **downloader.py** with ```py .\downloader.py <database_connection_sting> <repository_full_name> <github_token(s)>``` supplying necessary data, e.g. 
```py .\downloader.py postgresql://postgres:password@localhost:5432/pbr desktop/desktop ghp_s5OAH0D9a2NFjzBU7PF3POgUURvuiR00S22a ghp_a5092D9a2NFjzBU7PF3POgUURvuiR00S27b```.

> ✅ ```OSError22, 'The semaphore timeout period has expired'``` is a Windows thing, which does not affect downloading in other way than prolonging it (sometimes updating network drivers helps).
>
> ✅ ```Session closed exception``` after downloading project can happen, however this and previous project data won't be affected.

This step can take hours depending on number of tokens and number of requests allowed. There are no obstacles to run it multiple times.

### Run data analysis in evaluator.py
To obtain information on percentage of smelly PRs invoke `py .\evaluator.py <database_connection_sting> <repository_full_name>`, e.g. ```py .\downloader.py postgresql://postgres:password@localhost:5432/pbr desktop/desktop```