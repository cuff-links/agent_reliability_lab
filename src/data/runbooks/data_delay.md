# Data Delay Investigation

Use this playbook when dashboards lag by more than 30 minutes.

Checklist:

- Confirm upstream source is emitting events.
- Validate Airflow scheduler has available slots.
- Inspect dag metadata for recent code changes.
- Communicate delays in #data-ops channel.
