const core = require('@actions/core');
const { exec } = require('child_process');
const axios = require('axios');
const fs = require('fs').promises;

async function run() {
  try {
    const runId = core.getInput('run_id', { required: true });
    const repoOwner = core.getInput('repo_owner', { required: true });
    const repoName = core.getInput('repo_name', { required: true });
    const githubToken = core.getInput('github_token', { required: true });
    const customServiceCookie = core.getInput('custom_service_cookie');

    // Checkout logs_summary_action repository
    await execCommand(`git clone https://github.com/shivendratiwari07/logs_summary_action.git logs_summary_action`);

    // Set up Python 3.12 environment
    await execCommand(`python3 -m venv logs_summary_action/myenv`);
    await execCommand(`source logs_summary_action/myenv/bin/activate && pip install -r logs_summary_action/requirements.txt && pip install requests`);

    // Wait for all jobs to complete or timeout
    let allJobsCompleted = false;
    const maxAttempts = 180;
    const sleepTime = 10000; // in ms

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const response = await axios.get(
        `https://api.github.com/repos/${repoOwner}/${repoName}/actions/runs/${runId}/jobs`,
        { headers: { Authorization: `token ${githubToken}` } }
      );

      const incompleteJobs = response.data.jobs.filter(job => job.name !== 'collect-logs' && (job.status === 'queued' || job.status === 'in_progress'));

      if (incompleteJobs.length === 0) {
        core.info('All jobs have completed.');
        allJobsCompleted = true;
        await fs.writeFile('jobs_response.json', JSON.stringify(response.data));
        break;
      } else {
        core.info('Waiting for jobs to complete...');
        await new Promise(resolve => setTimeout(resolve, sleepTime));
      }
    }

    if (!allJobsCompleted) {
      core.info('Jobs did not complete within the expected time. Proceeding with available job statuses.');
    }

    // Fetch and analyze job statuses
    const jobsResponse = await fs.readFile('jobs_response.json', 'utf8');
    const jobsData = JSON.parse(jobsResponse);

    core.info('Listing all job statuses:');
    jobsData.jobs.forEach(job => {
      core.info(`${job.name} - ${job.conclusion} - Job ID: ${job.id}`);
    });
    
    const failedJobs = jobsData.jobs.filter(job => job.conclusion === 'failure');

    let runAnalysis = failedJobs.length > 0;
    core.setOutput('run_analysis', runAnalysis);

    // Run log analysis if there are failed jobs
    if (runAnalysis) {
      process.env.GITHUB_TOKEN = githubToken;
      process.env.REPO_OWNER = repoOwner;
      process.env.REPO_NAME = repoName;
      process.env.CUSTOM_SERVICE_COOKIE = customServiceCookie;
      process.env.GITHUB_RUN_ID = runId;

      await execCommand(`source logs_summary_action/myenv/bin/activate && python logs_summary_action/script/debug_fetch_logs.py`);
      
      // List files after analysis
      await execCommand('ls -la logs_summary_action/script/');
    }

    // Display analysis summary
    await displayAnalysisSummary();
  } catch (error) {
    core.setFailed(error.message);
  }
}

async function execCommand(command) {
  return new Promise((resolve, reject) => {
    exec(command, (error, stdout, stderr) => {
      if (error) {
        return reject(error);
      }
      core.info(stdout);
      core.info(stderr);
      resolve();
    });
  });
}

async function displayAnalysisSummary() {
  try {
    const summaries = await fs.readdir('logs_summary_action/script/');
    const summaryFiles = summaries.filter(file => file.includes('_analysis_'));
    
    if (summaryFiles.length > 0) {
      for (const file of summaryFiles) {
        const jobName = file.replace('_analysis_', '').replace('.txt', '');
        core.summary.addHeading(`Job Name: ${jobName}`);
        const content = await fs.readFile(`logs_summary_action/script/${file}`, 'utf8');
        core.summary.addRaw(content.replace(/Root Cause Summary:/g, 'Root cause of Job failure:'));
      }
    } else {
      core.summary.addHeading('All jobs ran successfully');
    }

    await core.summary.write();
  } catch (error) {
    core.setFailed(error.message);
  }
}

run();