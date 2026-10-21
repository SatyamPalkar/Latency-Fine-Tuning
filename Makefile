.PHONY: install install-dev install-benchmark run test lint benchmark plots dashboard docker-up docker-down

install:
	python3 -m pip install -r requirements.txt

install-dev:
	python3 -m pip install -r requirements-dev.txt

install-benchmark:
	python3 -m pip install -r requirements-benchmark.txt

run:
	python3 scripts/serve.py

test:
	python3 -m pytest

lint:
	ruff check .

benchmark:
	python3 scripts/run_benchmark.py --url http://localhost:8000 --output benchmark_results/results.csv

plots:
	python3 scripts/make_plots.py --input benchmark_results/results.csv --output-dir plots

dashboard:
	python3 scripts/make_dashboard.py --input benchmark_results/results.csv --output dashboard/index.html

docker-up:
	docker compose up --build

docker-down:
	docker compose down
