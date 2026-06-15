# Upgrade to 4.0.0 on Windows

Use the detailed procedure in `README.md`, section **Upgrade from version 2.x or 3.x without deleting data**.

Critical rules:

- Do not use `-ResetData`.
- Do not run `docker compose down -v`.
- Back up `.env`.
- Preserve Docker volumes.
- Route both public hostnames to port 2331.
