const core = require('@actions/core');
const github = require('@actions/github');
const exec = require('@actions/exec');
const axios = require('axios');
const fs = require('fs');

async function run() {
  try {
    const runId = core.getInput('run_id');
    const repoOwner = core.getInput('repo_owner');
    const repoName = core.getInput('repo_name');
    const githubToken = core.getInput('github_token');
    const customServiceCookie = process.env.CUSTOM_SERVICE_COOKIE;

    // Set up axios with GitHub token
    const instance = axios.create({
      baseURL: 'https://api.github.com/',
      timeout: 10000,
      headers: { 'Authorization': `token ${githubToken}` }
    });

    // Wait for all jobs to complete or timeout
    let maxAttempts = 180;
    let sleepTime = 10;
    let attempt = 0;
    let allJobsCompleted = false;
    while (attempt < maxAttempts) {
      const response = await instance.get(`repos/${repoOwner}/${repoName}/actions/runs/${runId}/jobs`);
      const incompleteJobs = response.data.jobs.filter(job => job.name !== 'collect-logs' && (job.status === 'queued' || job.status === 'in_progress'));
      if (incompleteJobs.length === 0) {
        console.log('All jobs have completed.');
        allJobsCompleted = true;
        break;
      } else {
        console.log('Waiting for jobs to complete...');
        attempt++;
        await new Promise(resolve => setTimeout(resolve, sleepTime * 1000));
      }
    }

    if (!allJobsCompleted) {
      console.log('Jobs did not complete within the expected time. Proceeding with available job statuses.');
    }

    const response = await instance.get(`repos/${repoOwner}/${repoName}/actions/runs/${runId}/jobs`);
    fs.writeFileSync('jobs_response.json', JSON.stringify(response.data));

    // Fetch and analyze job statuses
    const jobStatuses = response.data.jobs.map(job => `${job.name} - ${job.conclusion} - Job ID: ${job.id}`).join('\n');
    console.log('Listing all job statuses:');
    console.log(jobStatuses);

    fs.writeFileSync('job_statuses.txt', jobStatuses);
    const failedJobs = response.data.jobs.filter(job => job.conclusion === 'failure').map(job => `${job.name} - ${job.conclusion}`).join('\n');
    if (failedJobs) {
      console.log('Failed jobs detected.');
      fs.writeFileSync('failed_jobs.txt', failedJobs);
      core.setOutput('run_analysis', 'true');
    } else {
      console.log('No failed jobs detected. Skipping log analysis.');
      core.setOutput('run_analysis', 'false');
    }

    // Run log analysis if any job failed
    if (core.getOutput('run_analysis') === 'true') {
      const options = {
        env: {
          GITHUB_TOKEN: githubToken,
          REPO_OWNER: repoOwner,
          REPO_NAME: repoName,
          CUSTOM_SERVICE_COOKIE: customServiceCookie,
          GITHUB_RUN_ID: runId,
        },
      };

      await exec.exec('bash', ['-c', `
        python -m venv logs_summary_action/myenv
        source logs_summary_action/myenv/bin/activate
        if [ -f logs_summary_action/requirements.txt ]; then
          pip install -r logs_summary_action/requirements.txt
        fi
        pip install requests

        echo "Current directory:"
        pwd
        echo "Listing the root directory files:"
        ls -la logs_summary_action
        python logs_summary_action/script/debug_fetch_logs.py
      `], options);
    }

    // List files after analysis
    await exec.exec('bash', ['-c', `
      echo "Listing the files in the logs_summary_action/scripts directory"
      ls -la logs_summary_action/script/
    `]);

    // Display analysis summary
    await exec.exec('bash', ['-c', `
      echo "Debug: Checking if summary files exist..."
      summary_files=$(ls logs_summary_action/script/*_analysis_*.txt 2>/dev/null || true)
      echo "Found summary files: $summary_files"
      for file in $summary_files; do
        job_name=$(basename "$file" | sed 's/_analysis_.*//')
        echo "### Job Name: $job_name" >> $GITHUB_STEP_SUMMARY
        echo "Appending content of file: $file into summary"
        sed 's/Root Cause Summary:/Root cause of Job failure:/g' "$file" >> $GITHUB_STEP_SUMMARY
        echo "" >> $GITHUB_STEP_SUMMARY
      done
      if [ -z "$summary_files" ]; then
        echo "### All jobs ran successfully" >> $GITHUB_STEP_SUMMARY
      fi
    `]);

    // Display the summary
    await exec.exec('bash', ['-c', `
      echo "Debug: Displaying summary file content..."
      cat $GITHUB_STEP_SUMMARY
    `]);
  } catch (error) {
    core.setFailed(error.message);
  }
}

run();