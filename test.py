from apify_client import ApifyClient

# Initialize the ApifyClient with your API token
client = ApifyClient("apify_api_AsrvwacK8FbSbIQ6vhcrLs5IgDw5Gl2jIZfC")

# Prepare the Actor input
run_input = { "profileUrls": [
        "https://www.linkedin.com/in/williamhgates",
        "http://www.linkedin.com/in/jeannie-wyrick-b4760710a",
    ] }

# Run the Actor and wait for it to finish
run = client.actor("2SyF0bVxmgGr8IVCZ").call(run_input=run_input)

# Fetch and print Actor results from the run's dataset (if there are any)
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item)