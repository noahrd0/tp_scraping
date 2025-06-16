# FootGraph

A web scraping application that extracts football data from FotMob and generates statistical visualizations through graphs and charts.

## Features

- Data scraping from FotMob
- Statistical analysis and data processing
- Interactive visualizations
- Multi-threaded data collection
- Django web interface

## Prerequisites

- Python 3.7+
- pip
- Virtual environment support

## Installation

### 1. Setup Virtual Environment

```bash
python3 -m venv venv_name
source venv_name/bin/activate
```

### 2. Install Dependencies

```bash
cd footgraph
pip install -r requirements.txt
```

### 3. Database Setup

```bash
./manage.py makemigrations
./manage.py migrate
```

## Usage

### Data Collection

```bash
./manage.py scrap_data --max_workers 5
```

Expected duration: approximately 2 hours.

### Run Application

```bash
./manage.py runserver
```

Access the application at `http://localhost:8000`

## Configuration

- `--max_workers`: Number of concurrent threads for scraping (default: 3)
- Adjust based on system capabilities and network bandwidth

## Troubleshooting

- Check internet connection if scraping fails
- Ensure database migrations are applied
- Reduce worker count if experiencing performance issues
- Monitor system resources during data collection
