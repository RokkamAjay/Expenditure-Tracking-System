# SpendWise — Expenditure Tracker

A beginner-friendly full-stack expenditure tracker built with Flask, SQLite, HTML, CSS, JavaScript, and Chart.js.

## Features
- User registration and login with hashed passwords
- User-specific transactions
- Income and expense tracking
- Monthly dashboard and balance
- Monthly spending budget with a progress indicator
- Category doughnut chart and monthly income-vs-expenses bar chart
- Delete transactions
- Search transactions by description/category and filter by type/category
- Export the selected month to a CSV spreadsheet
- Personal savings goal with target, current saved amount, optional deadline, and progress bar
- Budget warning at 80% and over-budget status at 100%+
- Responsive dark theme
- Basic CSRF tokens for form submissions

## Run on Windows (VS Code)

1. Install Python 3.10+ and VS Code.
2. Open this folder in VS Code.
3. Open Terminal → New Terminal.
4. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt and run:

   ```bat
   .venv\Scripts\activate.bat
   ```

5. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open http://127.0.0.1:5000 in your browser and create an account.

The SQLite database `expenditure.db` is created automatically the first time the app starts.

## Quick manual test
1. Register a new account.
2. Add income of ₹20,000 with category Salary.
3. Add an expense of ₹250 with category Food.
4. Check that income is ₹20,000, expenses are ₹250, and balance is ₹19,750.
5. Set a monthly budget of ₹5,000.
6. Add more expenses and confirm the budget progress updates.
7. Change the reporting month and verify the dashboard changes.
8. Log out, log in again, and confirm your transactions remain.
9. Create a second account and confirm it cannot see the first account's transactions.
10. Search for a transaction and filter by type/category.
11. Click Export CSV and open the downloaded file in Excel.
12. Create or update a savings goal and check the progress percentage.

## Notes
- Chart.js and Google Fonts are loaded from CDNs, so those parts need internet access.
- This starter project is intended for local learning. Before public deployment, set a strong random `SECRET_KEY`, turn off debug mode, use HTTPS, and review production security settings.
- Do not enter real bank credentials or sensitive financial information into a learning/demo app.
