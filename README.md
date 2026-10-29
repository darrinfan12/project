# Expert Pipeline — Darrin Fan

A week-one growth operations work sample: identify qualified experts without a first-task event, investigate the cause, and size a pilot. Built by Darrin Fan, drawing on Deloitte experience building Alteryx data pipelines. Contact: darrinfan@gmail.com.

**All bundled records, costs, and outcomes are invented. This is not AfterQuery data or measured business impact.**

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8502
```

## Two-minute review

1. Start on Overview; play the 30-second walkthrough.
2. Review the first five stalled qualified records, then open the full queue.
3. Select a row, inspect event gaps, record a verified reason, and export notes.
4. Compare channels and weekly cohorts. Percentages include their denominators.
5. Explore observed, conservative, optimistic, and custom capacity scenarios.
6. Compare ranked opportunities and export a pilot proposal. Copy or export a draft; the app cannot send email.

Default analysis date: October 28, 2026. The seeded sample has 1,803 input rows, 1,799 valid records, 425 qualified records, 234 activations, and 153 qualified records waiting at least 14 days. Four input rows are held, including both copies of a duplicate ID. Six channels span 17 contact weeks. These numbers describe a fictional dataset, not results.

The observed end-to-end rate is 234 / 1,799 (13.0%). A target of 100 implies 769 contacts and about 143 staff hours under the default effort assumptions. Capacity and cost estimates are illustrative.

## Data contract

Required columns: `record_id,channel,contacted_at,responded_at,qualified_at,activated_at`. Optional: `acquisition_cost_usd` (nonnegative accrued acquisition cost per record). Dates use YYYY-MM-DD. Later stages may be blank but require all previous stages; dates must be chronological and no later than the selected analysis date. All copies of duplicate IDs are excluded. One journey per ID; repeated campaigns are unsupported.

Definitions: contacted = invitation sent; responded = any reply; qualified = meets a documented project rubric; activated = first task completed. Missing events are a reason to investigate, not proof of disengagement. Cost per activation divides all recorded channel acquisition cost by channel activations; it is unavailable when costs are missing. Median time to activation uses completed activations only.

## Privacy and integrations

Uploads and review notes live in the Streamlit session. Export notes before leaving or switching datasets. No names or email addresses are needed in the pipeline CSV. Public discovery sends only the entered search query to Crossref when Search is clicked. Crossref covers publication metadata, not verified practitioner availability. Drafts are template-based and export-only. There is no SMTP adapter, live ATS connection, Slack delivery, or automatic outreach.

## Daily digest

`daily_digest.py` validates an export and produces a digest of newly stalled qualified IDs relative to a previous run:

```bash
python daily_digest.py pipeline.csv --as-of 2026-10-28 --threshold 14 --state-out state.json --digest-out digest.md
python daily_digest.py pipeline.csv --as-of 2026-10-29 --threshold 14 --previous state.json --state-out state.json --digest-out digest.md
```

Scheduling the job and routing the digest into an existing Slack workflow remain deployment integration steps. The script does not send anything. Keep previous-run state scoped to the same pipeline and threshold.

## Model limitations

Planning defaults are calculated from the loaded funnel, including when it is dummy data. Sensitivity presets change each rate by ±20% relative, capped at 100%. Required contacts = ceiling(target / product of sequential rates). Work hours sum stage counts × minutes per stage / 60. Costs include modeled labor and per-contact tooling, excluding expert pay, fixed overhead, and project delivery. Capacity is calendar weeks until the deadline × available weekly hours. This does not model response lag or uncertainty.

Opportunity rankings change one stage at a time and hold other rates fixed; overlapping gains cannot be summed. Channel comparisons are not causal or adjusted for cohort maturity. A 37% to 55% lift needs approximately 120 per arm under a normal approximation (80% power, two-sided 5% alpha, equal allocation). A small stalled cohort supports a feasibility pilot, not a powered efficacy claim.

## Deploy on Streamlit Community Cloud

1. Publish these source files in a GitHub repository, including `.streamlit/config.toml` and `requirements.txt`. Exclude local uploads, run state, credentials, and virtual environments.
2. Sign in at https://share.streamlit.io/ and create an app from that repository, branch, and `app.py`.
3. Select Python 3.12 in advanced settings. Set the environment variable `PUBLIC_REPO_URL` to the repository URL if the hosting environment supports it; otherwise the app offers a source-code ZIP download.
4. Verify the deployed app at desktop and approximately 390px width; check the walkthrough, queue selection, exports, icons, and preset changes. Share the resulting `streamlit.app` URL, not saved HTML.

Local checks used Python 3.9, Streamlit 1.50, pandas 2.3.3, and Altair 5.5. A public deployment has not yet been verified.

## Tests

```bash
python -m unittest discover -s tests -v
```
