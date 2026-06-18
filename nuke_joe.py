import sqlite3
import sys

conn = sqlite3.connect("/app/data/joblin.db")
c = conn.cursor()

c.execute("SELECT id FROM users WHERE authentik_username = 'joe'")
row = c.fetchone()
if not row:
    print("User joe not found")
    sys.exit(1)

uid = row[0]
print(f"Found joe: user_id={uid}")

# user_jobs replaces jobs; raw_jobs and company_catalog are shared and must not be deleted
c.execute("DELETE FROM token_usage WHERE run_id IN (SELECT id FROM runs WHERE user_id=?)", (uid,))
c.execute("DELETE FROM run_company_results WHERE run_id IN (SELECT id FROM runs WHERE user_id=?)", (uid,))
c.execute("DELETE FROM matches WHERE job_id IN (SELECT id FROM user_jobs WHERE user_id=?)", (uid,))
c.execute("DELETE FROM job_skills WHERE job_id IN (SELECT id FROM user_jobs WHERE user_id=?)", (uid,))
c.execute("DELETE FROM application_tracking WHERE user_id=?", (uid,))
c.execute("DELETE FROM feedback_examples WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_jobs WHERE user_id=?", (uid,))
c.execute("DELETE FROM runs WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_companies WHERE user_id=?", (uid,))
c.execute("DELETE FROM resume WHERE user_id=?", (uid,))
c.execute("DELETE FROM settings WHERE user_id=?", (uid,))
c.execute("DELETE FROM users WHERE id=?", (uid,))

conn.commit()
conn.close()
print("Done - joe will be a fresh user on next login.")
