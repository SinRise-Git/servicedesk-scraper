import argparse
import requests
import json
import asyncio
import html
import aiofiles
import os
import aiohttp
from pathlib import Path
from bs4 import BeautifulSoup
from aiohttp import ClientError, ContentTypeError


class ServiceDeskScraper:
    def __init__(self, token, local_url):
        self.task_queue = asyncio.Queue()
        self.lock_index, self.lock_count = asyncio.Lock(), asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.session = requests.Session()
        self.completed_tasks, self.index = 0, 0
        self.all_tasks, self.existing_tasks = {}, {}
        self.fatal_error = False, None
        self.current_task = None
        self.token = token
        self.local_url = local_url

    async def check_tasks(self):
        ## Check if data.json file exists and load existing tasks
        file_path = Path("data.json")
        if file_path.exists():
            async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
                content = await file.read()
                print("Found existing data.json file.")
            if content.strip():
                try:
                    self.existing_tasks = json.loads(content)
                    print(f"Loaded {len(self.existing_tasks)} existing tasks from the data.json file.")
                except json.JSONDecodeError:
                    # If JSON is invalid, deletes the file
                    print("Something is wrong with the data.json file, deleting file and starting fresh")
                    await asyncio.to_thread(os.remove, file_path)

    async def get_tasks(self, session):
        current_index = 0
        while not self.stop_event.is_set():
            data = {
                "list_info": {
                    "row_count": "100",
                    "start_index": current_index,
                    "get_total_count": "true",
                    "sort_field": "id",
                    "sort_order": "asc",
                    "fields_required": ["id"],
                },
            }
            params = {
                "input_data": json.dumps(data),
            }
            headers = {
                "Cookie": f"SDPSESSIONID={self.token};"
            }
            try:
                async with session.get(f"{self.local_url}/api/v3/requests", params=params, headers=headers) as response:
                    response_json = await response.json()
                    try:
                        ##The response_status can be a list or a dict, handle both cases, why they do this is weird    
                        status_code = response_json["response_status"][0].get("status_code") if isinstance(response_json["response_status"], list) else response_json["response_status"].get("status_code")
                        if status_code in [2000]:               
                            for task in response_json["requests"]:
                                print(f"\rChecking task: {task['id']} - task: {self.current_task} is missing so adding to queue", end="", flush=True)
                                ## Checks if task ID already exists in existing_tasks
                                if str(task["id"]) not in self.existing_tasks:
                                    self.current_task = task["id"]
                                    await self.task_queue.put(task["id"])
                            if response_json["list_info"]["has_more_rows"] == False:
                                self.stop_event.set()
                        elif status_code in [4000]:
                            ## If SDPSESSIONID is invalid, stop all tasks
                            self.fatal_error = True, "Your SDPSESSIONID is most likely invalid, please check and try again"
                            self.stop_event.set()
                    except (KeyError, IndexError, TypeError) as e:
                        self.fatal_error = True, f"Error occurred while processing response: {e}"
                        self.stop_event.set()
            except (ClientError, ContentTypeError, json.JSONDecodeError) as e:
                self.fatal_error = True, f"Error occurred while fetching tasks: {e}"
            self.stop_event.set()
            async with self.lock_index:
                current_index = self.index
                self.index += 100

    async def task_request(self, session):
        while not self.task_queue.empty():
            task_id = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
            headers = {
                "Cookie": f"SDPSESSIONID={self.token};",
            }
            try:
                async with session.get(f"{self.local_url}/api/v3/requests/{task_id}/request_detail", headers=headers) as response:
                    task_details = await response.json()
                    task_complete = task_details['request_detail'][0]['request']['resolution']['content']

                    ## Here you can add more filtering if needed, currently just checks if resolution exists
                    if task_complete is not None:
                        
                        ## Here you add more fields if needed, currently just getting description and resolution
                        task_description = task_details['request_detail'][0]['request']['description']
                        
                        task_description_html, task_complete_html = html.unescape(task_description), html.unescape(task_complete)
                        soup_description, soup_complete = BeautifulSoup(task_description_html, 'html.parser'), BeautifulSoup(task_complete_html, 'html.parser')
                        task_description_text, task_complete_text = soup_description.get_text(strip=True), soup_complete.get_text(strip=True)
                        
                        ## Here you can change how the json data is stored, currently stores in a dict with task ID as key and description and resolution as values
                        self.all_tasks[task_id] = {        
                            "description": task_description_text,
                            "resolution": task_complete_text
                        }
                        async with self.lock_count:
                           current_count = self.completed_tasks
                           self.completed_tasks += 1

                        print(f"\rTotal tasks in queue: {self.task_queue.qsize()} - Tasks added to list: {current_count + 1} - Current Task ID: {task_id} will sort later", end="", flush=True)
                    self.task_queue.task_done()
            except Exception as e:
                print(f"\nError fetching task {task_id} Error: {e} will retry task")

async def run_scraper(token, local_url):
    scraper = ServiceDeskScraper(token, local_url)
    await scraper.check_tasks()

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=100)) as session:
        ## Create multiple tasks to fetch task IDs concurrently
        get_ids = [asyncio.create_task(scraper.get_tasks(session)) for _ in range(50)]
        await asyncio.gather(*get_ids)

        error, msg = scraper.fatal_error
        print("\nFinished getting all task IDs")
 
        if error:
            print(f"\n{msg}, exiting")
            return
        
        print("\nFinished getting all task IDs, now fetching details")
        ## Create multiple tasks to fetch task details concurrently
        get_details = [asyncio.create_task(scraper.task_request(session)) for _ in range(50)]
        await asyncio.gather(*get_details)

        print("\nFetched all valid task details, saving to data.json")
     
        ## Merge existing tasks with new tasks and sort by task ID before saving
        scraper.all_tasks.update(scraper.existing_tasks)
        sorted_tasks = dict(sorted(scraper.all_tasks.items(), key=lambda item: item[0]))
        with open("data.json", "w", encoding="utf-8") as file:
            json.dump(sorted_tasks, file, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ServiceDesk Scraper")
    parser.add_argument("-t", "--token", required=True, help="Your ServiceDesk token")
    parser.add_argument("-u", "--url", required=True, help="Your ServiceDesk base URL")

    args = parser.parse_args()

    asyncio.run(run_scraper(args.token, args.url))