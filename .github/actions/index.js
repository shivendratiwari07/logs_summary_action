const core = require('@actions/core');
const exec = require('@actions/exec');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

async function run() {
  try {
    const runId = core.getInput('run_id');
    const repoOwner = core.getInput('repo_owner');
    const repoName = core.getInput('repo_name');
    const githubToken = core.getInput('github_token');

    // Get custom_service_cookie either from input or environment variable
    let customServiceCookie = core.getInput('custom_service_cookie');

    if (!customServiceCookie) {
      // Fallback to environment variable if input is not provided
      customServiceCookie = process.env.custom_service_cookie;
    }

    if (!customServiceCookie) {
      throw new Error('CUSTOM_SERVICE_COOKIE is not provided as input or available in environment variables.');
    }

    console.log(`run_id: ${runId}`);
    console.log(`repo_owner: ${repoOwner}`);
    console.log(`repo_name: ${repoName}`);
    console.log(`github_token: ${githubToken}`);
    console.log(`CUSTOM_SERVICE_COOKIE: [Secret Retrieved from Input or Environment]`);

    // Set up axios with GitHub token
    const instance = axios.create({
      baseURL: 'https://api.github.com/',
      timeout: 10000,
      headers: { 'Authorization': `token ${githubToken}` }
    });

    // Check out the logs_summary_action repository with PAT
    console.log(`Cloning repository: https://github.com/shivendratiwari07/logs_summary_action.git`);
    const cloneUrl = `https://x-access-token:${githubToken}@github.com/shivendratiwari07/logs_summary_action.git`;
    await exec.exec('git', ['clone', cloneUrl, 'logs_summary_action']);

    // Change working directory to the logs_summary_action repository
    console.log('Changing working directory to logs_summary_action');
    process.chdir('logs_summary_action');

    // Print the current directory and list files
    console.log('Current directory after cloning:');
    await exec.exec('pwd');
    console.log('Listing contents of the directory:');
    await exec.exec('ls -la');

    // Set up Python environment
    console.log('Setting up Python environment...');
    await exec.exec('python3', ['-m', 'venv', 'myenv']);
    await exec.exec('bash', ['-c', 'source myenv/bin/activate && pip install -r requirements.txt && pip install requests']);

    // Wait for all jobs to complete or timeout
    let maxAttempts = 180;
    let sleepTime = 10;
    let attempt = 0;
    let allJobsCompleted = false;
    let response;
    while (attempt < maxAttempts) {
      response = await instance.get(`repos/${repoOwner}/${repoName}/actions/runs/${runId}/jobs`);
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

    fs.writeFileSync('jobs_response.json', JSON.stringify(response.data));

    // Fetch and analyze job statuses
    const jobStatuses = response.data.jobs.map(job => `${job.name} - ${job.conclusion} - Job ID: ${job.id}`).join('\n');
    console.log('Listing all job statuses:');
    console.log(jobStatuses);

    fs.writeFileSync('job_statuses.txt', jobStatuses);
    const failedJobs = response.data.jobs.filter(job => job.conclusion === 'failure').map(job => `${job.name} - ${job.conclusion}`).join('\n');
    if (failedJobs.length > 0) {
      console.log('Failed jobs detected.');
      fs.writeFileSync('failed_jobs.txt', failedJobs);
      core.setOutput('run_analysis', 'true');
    } else {
      console.log('No failed jobs detected. Skipping log analysis.');
      core.setOutput('run_analysis', 'false');
    }

    // Run log analysis if any job failed
    if (failedJobs.length > 0) {
      console.log('Running log analysis...');
      console.log(`Passing to Python: REPO_OWNER=${repoOwner}, REPO_NAME=${repoName}, GITHUB_RUN_ID=${runId}, GITHUB_TOKEN=${githubToken}, CUSTOM_SERVICE_COOKIE=${customServiceCookie}`);
    
      await exec.exec('bash', ['-c', `
        source myenv/bin/activate && \
        export REPO_OWNER=${repoOwner} && \
        export REPO_NAME=${repoName} && \
        export GITHUB_RUN_ID=${runId} && \
        export GITHUB_TOKEN=${githubToken} && \
        export CUSTOM_SERVICE_COOKIE=${customServiceCookie} && \
        python script/debug_fetch_logs.py
      `]);
    }

    // List files after analysis
    console.log('Listing files in the logs_summary_action/scripts directory after analysis:');
    await exec.exec('bash', ['-c', `
      pwd 
      ls -la script/ 
      pwd 
    `]);

    // Display analysis summary
    console.log('Displaying analysis summary...');
    await exec.exec('bash', ['-c', `
      echo "Debug: Checking if summary files exist..."
      summary_files=$(ls script/*_analysis_*.txt 2>/dev/null || true)
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









// const core = require('@actions/core');
// const github = require('@actions/github');
// const exec = require('@actions/exec');
// const axios = require('axios');
// const fs = require('fs');

// async function run() {
//   try {
//     const runId = core.getInput('run_id');
//     const repoOwner = core.getInput('repo_owner');
//     const repoName = core.getInput('repo_name');
//     const githubToken = core.getInput('github_token');
//     const customServiceCookie = process.env.CUSTOM_SERVICE_COOKIE;

//     // Set up axios with GitHub token
//     const instance = axios.create({
//       baseURL: 'https://api.github.com/',
//       timeout: 10000,
//       headers: { 'Authorization': `token ${githubToken}` }
//     });

//     // Check out the logs_summary_action repository
//     await exec.exec('git', ['clone', `https://github.com/${repoOwner}/${repoName}.git`, 'logs_summary_action']);

//     // Change working directory to the logs_summary_action repository
//     process.chdir('logs_summary_action');

//     // Set up Python environment
//     await exec.exec('python', ['-m', 'venv', 'myenv']);
//     await exec.exec('bash', ['-c', 'source myenv/bin/activate && pip install -r requirements.txt && pip install requests']);


//     // Wait for all jobs to complete or timeout
//     let maxAttempts = 180;
//     let sleepTime = 10;
//     let attempt = 0;
//     let allJobsCompleted = false;
//     let response;
//     while (attempt < maxAttempts) {
//       response = await instance.get(`repos/${repoOwner}/${repoName}/actions/runs/${runId}/jobs`);
//       const incompleteJobs = response.data.jobs.filter(job => job.name !== 'collect-logs' && (job.status === 'queued' || job.status === 'in_progress'));
//       if (incompleteJobs.length === 0) {
//         console.log('All jobs have completed.');
//         allJobsCompleted = true;
//         break;
//       } else {
//         console.log('Waiting for jobs to complete...');
//         attempt++;
//         await new Promise(resolve => setTimeout(resolve, sleepTime * 1000));
//       }
//     }

//     if (!allJobsCompleted) {
//       console.log('Jobs did not complete within the expected time. Proceeding with available job statuses.');
//     }

//     fs.writeFileSync('jobs_response.json', JSON.stringify(response.data));

//     // Fetch and analyze job statuses
//     const jobStatuses = response.data.jobs.map(job => `${job.name} - ${job.conclusion} - Job ID: ${job.id}`).join('\n');
//     console.log('Listing all job statuses:');
//     console.log(jobStatuses);

//     fs.writeFileSync('job_statuses.txt', jobStatuses);
//     const failedJobs = response.data.jobs.filter(job => job.conclusion === 'failure').map(job => `${job.name} - ${job.conclusion}`).join('\n');
//     if (failedJobs.length > 0) {
//       console.log('Failed jobs detected.');
//       fs.writeFileSync('failed_jobs.txt', failedJobs);
//       core.setOutput('run_analysis', 'true');
//     } else {
//       console.log('No failed jobs detected. Skipping log analysis.');
//       core.setOutput('run_analysis', 'false');
//     }

//     // Run log analysis if any job failed
//     if (failedJobs.length > 0) {
//       const options = {
//         env: {
//           GITHUB_TOKEN: githubToken,
//           REPO_OWNER: repoOwner,
//           REPO_NAME: repoName,
//           CUSTOM_SERVICE_COOKIE: customServiceCookie,
//           GITHUB_RUN_ID: runId,
//         },
//       };

//       await exec.exec('bash', ['-c', `
//         python -m venv logs_summary_action/myenv
//         source logs_summary_action/myenv/bin/activate
//         if [ -f logs_summary_action/requirements.txt ]; then
//           pip install -r logs_summary_action/requirements.txt
//         fi
//         pip install requests

//         echo "Current directory:"
//         pwd
//         echo "Listing the root directory files:"
//         ls -la logs_summary_action
//         python logs_summary_action/script/debug_fetch_logs.py
//       `], options);
//     }

//     // List files after analysis
//     await exec.exec('bash', ['-c', `
//       echo "Listing the files in the logs_summary_action/scripts directory"
//       ls -la logs_summary_action/script/
//     `]);

//     // Display analysis summary
//     await exec.exec('bash', ['-c', `
//       echo "Debug: Checking if summary files exist..."
//       summary_files=$(ls logs_summary_action/script/*_analysis_*.txt 2>/dev/null || true)
//       echo "Found summary files: $summary_files"
//       for file in $summary_files; do
//         job_name=$(basename "$file" | sed 's/_analysis_.*//')
//         echo "### Job Name: $job_name" >> $GITHUB_STEP_SUMMARY
//         echo "Appending content of file: $file into summary"
//         sed 's/Root Cause Summary:/Root cause of Job failure:/g' "$file" >> $GITHUB_STEP_SUMMARY
//         echo "" >> $GITHUB_STEP_SUMMARY
//       done
//       if [ -z "$summary_files" ]; then
//         echo "### All jobs ran successfully" >> $GITHUB_STEP_SUMMARY
//       fi
//     `]);

//     // Display the summary
//     await exec.exec('bash', ['-c', `
//       echo "Debug: Displaying summary file content..."
//       cat $GITHUB_STEP_SUMMARY
//     `]);
//   } catch (error) {
//     core.setFailed(error.message);
//   }
// }

// run();