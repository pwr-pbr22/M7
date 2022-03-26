# Downloader

1. install necessary packages and prepare postgresql db
2. invoke `py .\downloader.py <github_token> <database_connection_sting> <repository_full_name>`, e.g. `py .\downloader.py ghp_vyz3FEONhVYgQWagxxxxxxxxxxxxxxxxxxxx postgresql://postgres:tajne_haselko@localhost:5432/pbr desktop/desktop`

# Evaluator

1. invoke `py .\evaluator.py <database_connection_sting> <repository_full_name>`, e.g. `py .\evaluator.py postgresql://postgres:tajne_haselko@localhost:5432/pbr desktop/desktop`