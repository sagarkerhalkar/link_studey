# GitHub Branch Synchronization

Repository: `sagarkerhalkar/link_studey`

Dedicated branch: `link-analytics-v4.2.0-project-source`

This branch contains the complete non-secret Link Analytics 4.2.0 project source, including:

- Flask dashboard and tracking gateway
- Docker and Windows/Linux launch scripts
- `REBUILD_AND_START_WINDOWS.ps1`
- tests and GitHub Actions CI workflows
- project requirements, issue log, activity log and deployment documentation
- text/HTML/XML test evidence

Excluded intentionally:

- `.env`
- database volumes and runtime databases
- passwords and API keys
- Cloudflare tunnel tokens
- raw private screen recordings and large user-supplied media

The branch is intended for review and controlled deployment. The production Docker volumes remain external to source control.
