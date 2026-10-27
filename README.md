# AI Expense Tracker

A Flask web app to record, edit and categorize daily expenses.

## Features
- Add, edit and delete expenses (amount, category, date, note) with input validation
- Filter by month and category
- Doughnut chart of spending by category (Chart.js)
- Monthly budget with an over-budget alert
- CSV export of the current filter
- Data stored in SQLite

- **AI quick add:** type "spent 250 on lunch yesterday" and it becomes a validated record
- **AI insights:** short monthly observations comparing this month with last month
- **Ask your expenses:** questions in plain English; numbers are computed in SQL, the AI only explains them

## How the AI is kept safe
- AI output is treated as untrusted and goes through the same validation as the manual form
- The API key is read from an environment variable and never committed
- Amounts in answers come from SQL queries, not from the model

## Tech stack
Python, Flask, SQLite, Google Gemini API, Chart.js, HTML/CSS

## Get a free Gemini key
1. Go to aistudio.google.com and sign in, then click Get API key
2. Copy `.env.example` to `.env` and paste your key after `GEMINI_API_KEY=`
3. If you see a model error, set `GEMINI_MODEL` in `.env` to a model listed in AI Studio

## Run locally
```
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Screenshots
Add 2-3 screenshots here.
