import * as core from '@actions/core';
import * as exec from '@actions/exec';
import * as path from 'path';
import * as fs from 'fs';

async function run(): Promise<void> {
  try {
    // Get inputs (no need for fallbacks - action.yml provides defaults)
    const apiKey = core.getInput('api-key', { required: true });
    const specPath = core.getInput('spec-path');
    const command = core.getInput('command');
    const failOnWarning = core.getInput('fail-on-warning') === 'true';
    const verbose = core.getInput('verbose') === 'true';

    // Mask the API key in logs for security
    core.setSecret(apiKey);

    // Validate we're in GitHub Actions environment
    const workspace = process.env.GITHUB_WORKSPACE;
    if (!workspace) {
      throw new Error(
        'GITHUB_WORKSPACE environment variable not set. This action must run in a GitHub Actions environment.'
      );
    }

    // Validate spec path exists with robust path resolution
    const absoluteSpecPath = path.isAbsolute(specPath) 
      ? specPath 
      : path.resolve(workspace, specPath);
      
    if (!fs.existsSync(absoluteSpecPath)) {
      throw new Error(`OpenAPI specification file not found at: ${specPath}`);
    }
    
    core.info(`📋 OpenAPI spec found at: ${specPath}`);

    // Install delimit-cli from npm
    core.info('📦 Installing delimit-cli v1.0.0...');
    await exec.exec('npm', ['install', '-g', 'delimit-cli@1.0.0']);

    // Prepare CLI command with JSON output for reliable parsing
    const cliArgs = [command, absoluteSpecPath, '--output', 'json'];
    if (verbose) {
      cliArgs.push('--verbose');
    }
    
    // Execute the CLI with API key as environment variable
    core.info(`🚀 Running delimit ${command} on ${specPath}`);
    
    let output = '';
    let errorOutput = '';
    
    const exitCode = await exec.exec('delimit', cliArgs, {
      env: {
        ...process.env,
        DELIMIT_API_KEY: apiKey
      },
      listeners: {
        stdout: (data: Buffer) => {
          output += data.toString();
        },
        stderr: (data: Buffer) => {
          errorOutput += data.toString();
        }
      },
      ignoreReturnCode: true
    });

    // Parse output to extract validation results
    const validationPassed = exitCode === 0;
    
    let errorCount = 0;
    let warningCount = 0;
    
    try {
      // Try to parse JSON output first (if CLI supports it)
      const jsonOutput = JSON.parse(output);
      errorCount = jsonOutput.summary?.error_count || 0;
      warningCount = jsonOutput.summary?.warning_count || 0;
    } catch {
      // Fallback to regex parsing if JSON parsing fails
      const errorMatch = output.match(/Found (\d+) error\(s\)/);
      if (errorMatch) {
        errorCount = parseInt(errorMatch[1], 10);
      }
      
      const warningMatch = output.match(/Found (\d+) warning\(s\)/);
      if (warningMatch) {
        warningCount = parseInt(warningMatch[1], 10);
      }
    }

    // Set outputs
    core.setOutput('valid', validationPassed.toString());
    core.setOutput('error-count', errorCount.toString());
    core.setOutput('warning-count', warningCount.toString());

    // Display summary
    if (validationPassed) {
      if (warningCount > 0) {
        core.warning(`Validation passed with ${warningCount} warning(s)`);
        if (failOnWarning) {
          core.setFailed(`Validation passed but found ${warningCount} warning(s) and fail-on-warning is enabled`);
        }
      } else {
        core.info('✅ OpenAPI specification validation passed!');
      }
    } else {
      core.setFailed(`Validation failed with ${errorCount} error(s) and ${warningCount} warning(s)`);
    }

  } catch (error) {
    if (error instanceof Error) {
      core.setFailed(error.message);
    } else {
      core.setFailed('An unexpected error occurred');
    }
  }
}

// Run the action
run();