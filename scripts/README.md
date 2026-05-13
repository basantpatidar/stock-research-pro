# Automated Deployment Guide

The `auto_deploy.ps1` script allows you to automatically deploy new code to your laptop (or any Windows machine running Docker) without needing a complex CI/CD pipeline.

## How to use it manually
If you ever want to force an update immediately, simply right-click `auto_deploy.ps1` and select **"Run with PowerShell"**.

## How to set it up to run automatically (Background Auto-Pull)

You can use the built-in Windows Task Scheduler on your laptop to run this script every 5 minutes in the background.

1. On your laptop, open the Start Menu and search for **Task Scheduler**, then open it.
2. In the right-hand panel, click **Create Task...** (Do not use Basic Task).
3. **General Tab:**
   * Name: `Stock Research Pro Auto-Deploy`
   * Select **"Run whether user is logged on or not"** (so it runs silently in the background).
   * Check **"Run with highest privileges"** (Docker often requires admin rights).
4. **Triggers Tab:**
   * Click **New...**
   * Begin the task: **"On a schedule"**
   * Advanced Settings: Check **"Repeat task every:"** and type `5 minutes` for a duration of `Indefinitely`.
   * Click OK.
5. **Actions Tab:**
   * Click **New...**
   * Action: **"Start a program"**
   * Program/script: type `powershell.exe`
   * Add arguments: type `-WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Path\To\Your\stock-research-pro\scripts\auto_deploy.ps1"`
     *(Make sure to change `C:\Path\To\Your` to the actual location where you cloned the repo on the laptop).*
   * Click OK.
6. **Conditions & Settings Tabs:**
   * Uncheck "Stop if the computer switches to battery power" if you want it to run on battery.
   * Click **OK** to save the task. It will ask for your Windows password to authorize running it in the background.

That's it! Your laptop will now silently check GitHub every 5 minutes. If it sees new code, it will pull it and safely restart your Docker containers automatically.
