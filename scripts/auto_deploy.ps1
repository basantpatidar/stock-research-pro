<#
.SYNOPSIS
    Auto-deployment script for Stock Research Pro.
.DESCRIPTION
    Checks GitHub for new commits on the main branch. 
    If new commits exist, it pulls them and restarts the Docker containers.
    If no new commits exist, it exits quietly.
#>

# Navigate to the root folder of the repository (one level up from the scripts folder)
Set-Location -Path "$PSScriptRoot\.."

Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Checking for updates..."

# Fetch the latest changes from the remote repository
git fetch origin main

# Compare the local HEAD commit hash with the remote origin/main commit hash
$localCommit = git rev-parse HEAD
$remoteCommit = git rev-parse origin/main

if ($localCommit -ne $remoteCommit) {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] New updates found! Pulling changes..."
    
    # Pull the new code
    git pull origin main
    
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Rebuilding and restarting Docker containers..."
    
    # Shut down the old containers, rebuild, and start in detached mode
    docker-compose down
    docker-compose up --build -d
    
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Deployment complete!"
} else {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Already up to date. No action taken."
}
