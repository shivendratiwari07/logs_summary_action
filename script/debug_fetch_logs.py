import argparse
import os
import sys
import requests
from datetime import datetime
import tiktoken  # OpenAI's tokenizer package

MAX_TOKENS = 1000  # Adjust according to the model's limit, e.g., 8000 for GPT-4 (8K context)

def chunk_text_by_tokens(text, max_tokens, tokenizer):
    tokens = tokenizer.encode(text)
    token_chunks = [tokens[i:i+max_tokens] for i in range(0, len(tokens), max_tokens)]
    return [tokenizer.decode(chunk) for chunk in token_chunks]

def get_failed_steps(owner, repo, run_id, headers):
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    jobs = response.json()["jobs"]
    failed_steps = []
    for job in jobs:
        job_logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job['id']}/logs"
        for step in job["steps"]:
            if step["conclusion"] == "failure":
                failed_steps.append({
                    "job_name": job["name"],
                    "step_name": step["name"],
                    "job_logs_url": job_logs_url
                })
    return failed_steps

def download_logs(logs_url, headers, output_filename):
    response = requests.get(logs_url, headers=headers)
    response.raise_for_status()
    if not response.content:
        raise Exception("Received empty content from GitHub API.")
    with open(output_filename, 'wb') as file:  # Fixed the syntax error here
        file.write(response.content)
    return True

def analyze_logs_with_custom_service(log_chunks, tokenizer):
    url = "https://www.dex.inside.philips.com/philips-ai-chat/chat/api/user/SendImageMessage"
    headers = {
        'Cookie': os.getenv('CUSTOM_SERVICE_COOKIE'),
        'Content-Type': 'application/json'
    }
    combined_logs = "\n".join(log_chunks)
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Provide only a summary of the root cause of the job failure. Print the file name, line number and code exactly where job failed:\n\n" + combined_logs
                    }
                ]
            }
        ]
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    print(f"Raw response content: {response.text}")
    analysis_result = response.json()
    summary = analysis_result.get('choices', [{}])[0].get('message', {}).get('content', 'No summary available')
    return summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=False, help='The GITHUB_RUN_ID to use')
    args = parser.parse_args()

    run_id = args.run_id or os.getenv('GITHUB_RUN_ID')
    repo_owner = os.getenv('REPO_OWNER')
    repo_name = os.getenv('REPO_NAME')
    token = os.getenv('GITHUB_TOKEN')

    print(f"repo_owner: {repo_owner}")
    print(f"repo_name: {repo_name}")
    print(f"run_id: {run_id}")
    print(f"token: {token}")
    
    if not all([repo_owner, repo_name, run_id, token]):
        raise Exception("REPO_OWNER, REPO_NAME, GITHUB_RUN_ID, and GITHUB_TOKEN must be set")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    failed_steps = get_failed_steps(repo_owner, repo_name, run_id, headers)
    if not failed_steps:
        print("No failed steps found.")
        return

    tokenizer = tiktoken.get_encoding("cl100k_base")

    for step in failed_steps:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_filename = f"{step['job_name']}_{step['step_name']}_logs_{timestamp}.txt"
        if not download_logs(step["job_logs_url"], headers, log_filename):
            print(f"Failed to download logs for {step['job_name']} - {step['step_name']}")
            continue

        try:
            with open(log_filename, 'r') as file:
                log_content = file.read()

            log_chunks = chunk_text_by_tokens(log_content, MAX_TOKENS, tokenizer)
            summary = analyze_logs_with_custom_service(log_chunks, tokenizer)

            # Print summary to logs
            print(summary)

            # Save the summary to a file
            # analysis_filename = f"./scripts/{step['job_name']}_{step['step_name']}_analysis_{timestamp}.txt"
            # with open(analysis_filename, 'w') as analysis_file:
            #     analysis_file.write(summary)
            analysis_filename = f"./logs_summary_action/script/{step['job_name']}_analysis_{timestamp}.txt"
            with open(analysis_filename, 'w') as analysis_file:
                analysis_file.write(f"Job Name: {step['job_name']}\n")
                analysis_file.write(summary)

            print(f"Analysis saved to {analysis_filename}")

        except Exception as e:
            print(f"Failed to analyze logs for {log_filename}: {str(e)}")

if __name__ == "__main__":
    main()






# # # import argparse
# # # import os
# # # import sys
# # # import requests
# # # from datetime import datetime
# # # import tiktoken  # OpenAI's tokenizer package

# # # MAX_TOKENS = 1000  ## Adjust according to the model's limit, e.g., 8000 for GPT-4 (8K context)

# # # def chunk_text_by_tokens(text, max_tokens, tokenizer):
# # #     tokens = tokenizer.encode(text)
# # #     token_chunks = [tokens[i:i+max_tokens] for i in range(0, len(tokens), max_tokens)]
# # #     return [tokenizer.decode(chunk) for chunk in token_chunks], len(tokens)

# # # def get_failed_steps(owner, repo, run_id, headers):
# # #     url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
# # #     response = requests.get(url, headers=headers)
# # #     response.raise_for_status()
# # #     jobs = response.json()["jobs"]
# # #     failed_steps = []
# # #     for job in jobs:
# # #         job_logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job['id']}/logs"
# # #         for step in job["steps"]:
# # #             if step["conclusion"] == "failure":
# # #                 failed_steps.append({
# # #                     "job_name": job["name"],
# # #                     "step_name": step["name"],
# # #                     "job_logs_url": job_logs_url
# # #                 })
# # #     return failed_steps

# # # def download_logs(logs_url, headers, output_filename):
# # #     response = requests.get(logs_url, headers=headers)
# # #     response.raise_for_status()
# # #     if not response.content:
# # #         raise Exception("Received empty content from GitHub API.")
# # #     with open(output_filename, 'wb') as file:
# # #         file.write(response.content)
# # #     return True

# # # def analyze_logs_with_custom_service(log_chunks, tokenizer):
# # #     url = "https://www.dex.inside.philips.com/philips-ai-chat/chat/api/user/SendImageMessage"
# # #     headers = {
# # #         'Cookie': os.getenv('CUSTOM_SERVICE_COOKIE'),
# # #         'Content-Type': 'application/json'
# # #     }
# # #     combined_logs = "\n".join(log_chunks)
# # #     payload = {
# # #         "messages": [
# # #             {
# # #                 "role": "user",
# # #                 "content": [
# # #                     {
# # #                         "type": "text",
# # #                         "text": "Provide only a summary of the root cause of the job failure. Print the file name, line number and code exactly where job failed:\n\n" + combined_logs
# # #                     }
# # #                 ]
# # #             }
# # #         ]
# # #     }
# # #     response = requests.post(url, json=payload, headers=headers)
# # #     response.raise_for_status()
# # #     analysis_result = response.json()
# # #     summary = analysis_result.get('choices', [{}])[0].get('message', {}).get('content', 'No summary available')
# # #     output_tokens = len(tokenizer.encode(summary))
# # #     return summary, output_tokens

# # # def main():
# # #     parser = argparse.ArgumentParser()
# # #     parser.add_argument('--run-id', required=False, help='The GITHUB_RUN_ID to use')
# # #     args = parser.parse_args()

# # #     run_id = args.run_id or os.getenv('GITHUB_RUN_ID')
# # #     repo_owner = os.getenv('REPO_OWNER')
# # #     repo_name = os.getenv('REPO_NAME')
# # #     token = os.getenv('GITHUB_TOKEN')

# # #     if not all([repo_owner, repo_name, run_id, token]):
# # #         raise Exception("REPO_OWNER, REPO_NAME, GITHUB_RUN_ID, and GITHUB_TOKEN must be set")

# # #     headers = {
# # #         "Accept": "application/vnd.github+json",
# # #         "Authorization": f"Bearer {token}",
# # #         "X-GitHub-Api-Version": "2022-11-28"
# # #     }

# # #     failed_steps = get_failed_steps(repo_owner, repo_name, run_id, headers)
# # #     if not failed_steps:
# # #         print("No failed steps found.")
# # #         return

# # #     tokenizer = tiktoken.get_encoding("cl100k_base")

# # #     for step in failed_steps:
# # #         timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
# # #         log_filename = f"{step['job_name']}_{step['step_name']}_logs_{timestamp}.txt"
# # #         if not download_logs(step["job_logs_url"], headers, log_filename):
# # #             print(f"Failed to download logs for {step['job_name']} - {step['step_name']}")
# # #             continue

# # #         try:
# # #             with open(log_filename, 'r') as file:
# # #                 log_content = file.read()

# # #             log_chunks, input_tokens = chunk_text_by_tokens(log_content, MAX_TOKENS, tokenizer)
# # #             summary, output_tokens = analyze_logs_with_custom_service(log_chunks, tokenizer)
# # #             total_tokens = input_tokens + output_tokens

# # #             # Print token information and summary to logs
# # #             print(f"Input Tokens: {input_tokens}")
# # #             print(f"Output Tokens: {output_tokens}")
# # #             print(f"Total Tokens: {total_tokens}")
# # #             print(f"Analysis Result: {summary}")

# # #             # Save the summary to a file
# # #             analysis_filename = f"./scripts/{step['job_name']}_{step['step_name']}_analysis_{timestamp}.txt"
# # #             with open(analysis_filename, 'w') as analysis_file:
# # #                 analysis_file.write(f"Input Tokens: {input_tokens}\n")
# # #                 analysis_file.write(f"Output Tokens: {output_tokens}\n")
# # #                 analysis_file.write(f"Total Tokens: {total_tokens}\n\n")
# # #                 analysis_file.write(f"Analysis Result:\n{summary}\n")

# # #             print(f"Analysis saved to {analysis_filename}")

# # #         except Exception as e:
# # #             print(f"Failed to analyze logs for {log_filename}: {str(e)}")

# # # if __name__ == "__main__":
# # #     main()









# # # # import argparse
# # # # import os
# # # # import sys
# # # # import requests
# # # # from datetime import datetime

# # # # CHUNK_SIZE = 10000  # Adjust this size based on your needs

# # # # def chunk_text(text, max_size):
# # # #     """
# # # #     Split text into chunks of a specified maximum size.
# # # #     """
# # # #     return [text[i:i+max_size] for i in range(0, len(text), max_size)]

# # # # def get_failed_steps(owner, repo, run_id, headers):
# # # #     url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
# # # #     response = requests.get(url, headers=headers)
# # # #     response.raise_for_status()
    
# # # #     jobs = response.json()["jobs"]
# # # #     failed_steps = []
    
# # # #     for job in jobs:
# # # #         job_logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job['id']}/logs"
# # # #         for step in job["steps"]:
# # # #             if step["conclusion"] == "failure":
# # # #                 failed_steps.append({
# # # #                     "job_name": job["name"],
# # # #                     "step_name": step["name"],
# # # #                     "job_logs_url": job_logs_url
# # # #                 })
    
# # # #     return failed_steps

# # # # def download_logs(logs_url, headers, output_filename):
# # # #     response = requests.get(logs_url, headers=headers)
# # # #     response.raise_for_status()
    
# # # #     if not response.content:
# # # #         raise Exception("Received empty content from GitHub API.")
    
# # # #     with open(output_filename, 'wb') as file:
# # # #         file.write(response.content)
    
# # # #     return True

# # # # def analyze_logs_with_custom_service(log_chunks):
# # # #     url = "https://www.dex.inside.philips.com/philips-ai-chat/chat/api/user/SendImageMessage"
# # # #     headers = {
# # # #         'Cookie': os.getenv('CUSTOM_SERVICE_COOKIE'),
# # # #         'Content-Type': 'application/json'
# # # #     }
    
# # # #     # Combine all chunks into one single string
# # # #     combined_logs = "\n".join(log_chunks)
    
# # # #     payload = {
# # # #         "messages": [
# # # #             {
# # # #                 "role": "user",
# # # #                 "content": [
# # # #                     {
# # # #                         "type": "text",
# # # #                         "text": "Provide only a summary of the root cause of the job failure. Print the file name, line number and code exactly where job failed:\n\n" + combined_logs
# # # #                     }
# # # #                 ]
# # # #             }
# # # #         ]
# # # #     }

# # # #     response = requests.post(url, json=payload, headers=headers)
# # # #     response.raise_for_status()

# # # #     analysis_result = response.json()
# # # #     summary = analysis_result.get('choices', [{}])[0].get('message', {}).get('content', 'No summary available')

# # # #     return summary

# # # # def main():
# # # #     parser = argparse.ArgumentParser()
# # # #     parser.add_argument('--run-id', required=False, help='The GITHUB_RUN_ID to use')
# # # #     args = parser.parse_args()

# # # #     run_id = args.run_id or os.getenv('GITHUB_RUN_ID')
# # # #     repo_owner = os.getenv('REPO_OWNER')
# # # #     repo_name = os.getenv('REPO_NAME')
# # # #     token = os.getenv('GITHUB_TOKEN')

# # # #     if not all([repo_owner, repo_name, run_id, token]):
# # # #         raise Exception("REPO_OWNER, REPO_NAME, GITHUB_RUN_ID, and GITHUB_TOKEN must be set")

# # # #     headers = {
# # # #         "Accept": "application/vnd.github+json",
# # # #         "Authorization": f"Bearer {token}",
# # # #         "X-GitHub-Api-Version": "2022-11-28"
# # # #     }

# # # #     failed_steps = get_failed_steps(repo_owner, repo_name, run_id, headers)
# # # #     if not failed_steps:
# # # #         print("No failed steps found.")
# # # #         return

# # # #     for step in failed_steps:
# # # #         timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
# # # #         log_filename = f"{step['job_name']}_{step['step_name']}_logs_{timestamp}.txt"
# # # #         if not download_logs(step["job_logs_url"], headers, log_filename):
# # # #             print(f"Failed to download logs for {step['job_name']} - {step['step_name']}")
# # # #             continue

# # # #         try:
# # # #             ## Read the entire log and chunk it
# # # #             with open(log_filename, 'r') as file:
# # # #                 log_content = file.read()

# # # #             log_chunks = chunk_text(log_content, CHUNK_SIZE)  # Use the defined chunk size

# # # #             # Analyze all chunks after collecting them
# # # #             summary = analyze_logs_with_custom_service(log_chunks)

# # # #             analysis_filename = f"./scripts/{step['job_name']}_{step['step_name']}_analysis_{timestamp}.txt"
# # # #             with open(analysis_filename, 'w') as analysis_file:
# # # #                 analysis_file.write(summary)

# # # #             print(f"Analysis saved to {analysis_filename}")

# # # #             # Display the analysis summary directly in the GitHub Actions log
# # # #             print("Analysis summary:")
# # # #             print(summary)

# # # #         except Exception as e:
# # # #             print(f"Failed to analyze logs for {log_filename}: {str(e)}")

# # # # if __name__ == "__main__":
# # # #     main()









# # # # import argparse
# # # # import os
# # # # import sys
# # # # import requests
# # # # from datetime import datetime
# # # # print("###################### running debug_fetch_logs.py file ################")
# # # # def get_failed_steps(owner, repo, run_id, headers):
# # # #     url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
# # # #     response = requests.get(url, headers=headers)
# # # #     response.raise_for_status()
    
# # # #     jobs = response.json()["jobs"]
# # # #     print(f"Retrieved jobs: {jobs}")  # Debugging statement
# # # #     failed_steps = []
    
# # # #     for job in jobs:
# # # #         job_logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job['id']}/logs"
# # # #         for step in job["steps"]:
# # # #             if step["conclusion"] == "failure":
# # # #                 failed_steps.append({
# # # #                     "job_name": job["name"],
# # # #                     "step_name": step["name"],
# # # #                     "job_logs_url": job_logs_url
# # # #                 })
    
# # # #     print(f"Failed steps: {failed_steps}")  # Debugging statement
# # # #     return failed_steps

# # # # def download_logs(logs_url, headers, output_filename):
# # # #     response = requests.get(logs_url, headers=headers)
# # # #     response.raise_for_status()
    
# # # #     if not response.content:
# # # #         print("Received empty content from GitHub API.")  # Debugging statement
# # # #         raise Exception("Received empty content from GitHub API.")
    
# # # #     with open(output_filename, 'wb') as file:
# # # #         file.write(response.content)
    
# # # #     print(f"Logs downloaded successfully to {output_filename}.")
# # # #     return True

# # # # def analyze_logs_with_custom_service(log_filename):
# # # #     url = "https://www.dex.inside.philips.com/philips-ai-chat/chat/api/user/SendImageMessage"
# # # #     headers = {
# # # #         'Cookie': os.getenv('CUSTOM_SERVICE_COOKIE'),
# # # #         'Content-Type': 'application/json'
# # # #     }
# # # #     with open(log_filename, 'r') as file:
# # # #         log_content = file.read()
    
# # # #     payload = {
# # # #         "messages": [
# # # #             {
# # # #                 "role": "user",
# # # #                 "content": [
# # # #                     {
# # # #                         "type": "text",
# # # #                         "text": "Examine the log content to pinpoint the exact cause of the job failure. Provide a clear summary of the failure, including the specific line and file name where the failure occurred. Focus exclusively on errors or anomalies that directly contributed to the job's failure:\n\n" + log_content
# # # #                     }
# # # #                 ]
# # # #             }
# # # #         ]
# # # #     }
    
# # # #     response = requests.post(url, json=payload, headers=headers)
# # # #     response.raise_for_status()
    
# # # #     # Debugging statement
# # # #     analysis_result = response.json()
# # # #     print(f"Analysis result: {analysis_result}")
    
# # # #     return analysis_result

# # # # def main():
# # # #     parser = argparse.ArgumentParser()
# # # #     parser.add_argument('--run-id', required=False, help='The GITHUB_RUN_ID to use')
# # # #     args = parser.parse_args()


# # # #     run_id = args.run_id or os.getenv('GITHUB_RUN_ID')
# # # #     #run_id = os.getenv('GITHUB_RUN_ID')
# # # #     repo_owner = os.getenv('REPO_OWNER')
# # # #     repo_name = os.getenv('REPO_NAME')
# # # #     token = os.getenv('GITHUB_TOKEN')

# # # #     # Debugging statements to check environment variable values
# # # #     print(f"GITHUB_RUN_ID: {run_id}")
# # # #     print(f"REPO_OWNER: {repo_owner}")
# # # #     print(f"REPO_NAME: {repo_name}")
# # # #     print(f"GITHUB_TOKEN: {token}")

# # # #     if not all([repo_owner, repo_name, run_id, token]):
# # # #         raise Exception("REPO_OWNER, REPO_NAME, GITHUB_RUN_ID, and GITHUB_TOKEN must be set")

# # # #     headers = {
# # # #         "Accept": "application/vnd.github+json",
# # # #         "Authorization": f"Bearer {token}",
# # # #         "X-GitHub-Api-Version": "2022-11-28"
# # # #     }

# # # #     failed_steps = get_failed_steps(repo_owner, repo_name, run_id, headers)
# # # #     if not failed_steps:
# # # #         print("No failed steps found.")
# # # #         return

# # # #     for step in failed_steps:
# # # #         timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
# # # #         log_filename = f"{step['job_name']}_{step['step_name']}_logs_{timestamp}.txt"
# # # #         if not download_logs(step["job_logs_url"], headers, log_filename):
# # # #             print(f"Failed to download logs for {step['job_name']} - {step['step_name']}")
# # # #             continue

# # # #         print(f"Analyzing log file: {log_filename}")
# # # #         try:
# # # #             analysis_result = analyze_logs_with_custom_service(log_filename)
# # # #             summary = analysis_result.get('choices', [{}])[0].get('message', {}).get('content', 'No summary available')

# # # #             # Check if the summary is being generated correctly
# # # #             print(f"Generated Summary: {summary}")

# # # #             # Save the analysis summary to a unique file
# # # #             analysis_filename = f"./scripts/{step['job_name']}_{step['step_name']}_analysis_{timestamp}.txt"
# # # #             with open(analysis_filename, 'w') as analysis_file:
# # # #                 analysis_file.write(summary)
            
# # # #             print(f"Analysis saved to {analysis_filename}")

# # # #             # Display the analysis summary directly in the GitHub Actions log
# # # #             print("Analysis summary:")
# # # #             print(summary)
            
# # # #             # Optionally, create GitHub Actions annotations for the analysis summary
# # # #             print(f"::warning file={analysis_filename},line=1,col=1::{summary}")

# # # #         except Exception as e:
# # # #             print(f"Failed to analyze logs for {log_filename}: {str(e)}")

# # # # if __name__ == "__main__":
# # # #     main()

