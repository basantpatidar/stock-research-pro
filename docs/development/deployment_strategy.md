# Multi-Machine Deployment & Architecture Strategy

**Doc version:** 1.0 · **Last updated:** 2026-05-14

This document outlines the dual-machine architecture used for Stock Research Pro. It provides essential context for any future development, debugging, or database analysis.

## The Architecture
The project is split across two physically distinct machines on the same local network:

1. **The Desktop (Development Environment)**
   * Used strictly for writing code, testing logic, and communicating with the LLM (Claude/Antigravity).
   * Does *not* run the live 24/7 scanners.
   * Connects remotely to the Laptop's database to query historical trading data and W/L statistics.

2. **The Laptop (Production Environment)**
   * Left online 24/7.
   * Runs the Dockerized application (`docker-compose up -d`).
   * Executes the `APScheduler` background jobs (like the MCF Funnel and Dip Scanners) during market hours.
   * Houses the live **PostgreSQL Database** containing the real-world `ScannerAlert` and `StockDataCache` records.

---

## The CI/CD Deployment Pipeline

To prevent the need for complex GitHub Actions or manual code transfers, the project uses a "Pull-based" Continuous Deployment strategy:

* **Trigger:** Code is developed on the Desktop and pushed to the `main` branch on GitHub.
* **Execution:** A PowerShell script (`scripts/auto_deploy.ps1`) runs on the Laptop via Windows Task Scheduler every 5 minutes.
* **Logic:** The script polls GitHub. If `git rev-parse HEAD` differs from `origin/main`, it automatically pulls the code and runs `docker-compose down && docker-compose up --build -d`.

*Note for AI Assistants: If the user pushes a code change and asks why it isn't live on the scanner yet, remind them that the Laptop's auto-pull script operates on a 5-minute interval.*

---

## Database Access & Analysis

Because the Desktop is used for development but the Laptop holds the production data, we bridge the gap using the local Wi-Fi network.

### Live Remote SQL Access
The `docker-compose.yml` on the Laptop exposes the PostgreSQL database on `0.0.0.0:5432`. 
* To analyze live trading data, the Desktop connects directly to the Laptop's local IPv4 address (e.g., `192.168.1.X:5432`) using a SQL client (DBeaver, VS Code, etc.).
* **Credentials:** User: `postgres`, Pass: `postgres`, DB: `stockresearch`.

### End-Of-Day (EOD) Dumps
For offline analysis or sharing logs with the LLM:
* The Laptop executes `local_debugging/eod_dump.py` at the end of the trading day.
* This generates a static JSON file in `local_debugging/eod_signals/`.
* These files are synced to the Desktop (via a shared cloud drive or network share) allowing the LLM to read the `.json` files locally on the Desktop to analyze near-misses and score bands.

---

## Context for AI Assistants (System Prompt Override)
If you are an AI assistant reading this file, you must remember:
1. **Database Queries:** When the user asks you to "look at the database to see why a trade failed," remember that the local database on *this* machine (the Desktop) might not be the live database. You may need to ask the user to pull an EOD dump or run the query against the remote Laptop IP.
2. **Environment:** Assume code modifications apply to the Desktop's working tree, but any logic affecting market hours or 24/7 background tasks will ultimately run on the Laptop.
