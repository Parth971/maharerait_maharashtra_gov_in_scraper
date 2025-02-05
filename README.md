# `maharerait.maharashtra.gov.in` Scraper

This project scrapes complaint data from `maharerait.maharashtra.gov.in` using Python.

## Requirements
- **Python Version**: 3.12

## Setup Instructions

### 1. Create a Virtual Environment
```sh
python3.12 -m venv venv
```

### 2. Activate Virtual Environment
#### On macOS/Linux:
```sh
source venv/bin/activate
```
#### On Windows:
```sh
venv\Scripts\activate
```

### 3. Install Dependencies
```sh
pip install -r requirements.txt
```

## Configuration
This project uses a `.env` file to manage various settings and credentials. Example:
```ini
CAPTCHA_SOLVER_API_KEY="xxx"
OUTPUT_DIR="/path_to_directory/output"
LOGS_DIRECTORY="/path_to_directory/logs"
# HEADLESS=False  # By default it's True
# DEBUG=True  # By default it's False
```

## Usage
Run the script:
```sh
python script.py main
```
