# Service Desk Scraper

A Python script to scrape **Tasks** from a Service Desk and output the data in a clean, structured format.  
Ideal for analysis or training AI models. 

## Features

- Fetches tasks from the Service Desk
- Retrieve the data you need from tasks based on the given arguments.
- Creates and saves all data to `data.json` 
- Handles existing tasks inside `data.json` to avoid duplicates


## Options 
You can change the data the script collects and the conditions under which it collects it. Currently, it retrieves the ID, description, and resolution from all tasks that have a resolution, in a format like:
```json
{
  "TASK_ID"
      "description": "TASK_DESCRIPTION",
      "resolution": "TASK_RESOLUTION"
}
```

## Setup

## 1. Clone the repository
```bash
git clone https://github.com/SinRise-Git/servicedesk-scraper.git
```
## 2. Move to the repository 
```bash
cd servicedesk-scraper
```
## 3. Create a venv for the packages (Optional)
Creating a virtual environment (venv) is optional but recommended.
```bash
python -m venv venv
```
## 4. Start venv (Skip if you didn't create a venv)
**Windows**
```bash
venv\Scripts\activate
```
**Linux**
```bash
source myenv/bin/activate
```
## 5. Downlaod required packages 
```bash 
pip install -r requirements.txt
```
## 6. Run script
```bash 
python main.py -t YOUR_SDPSESSIONID -u YOUR_BASE_URL
```