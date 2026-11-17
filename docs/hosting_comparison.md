# PulseIQ Hosting Platform Comparison

**Evaluation date:** 17 November 2026
**Selected platform:** Streamlit Community Cloud

## 1. Platform comparison

| Criteria | Streamlit Community Cloud | Render Free | Hugging Face Spaces |
|---|---|---|---|
| Free availability | Yes | Yes | Static Spaces are free |
| Resources | Approx. 2 CPU cores, 2.7 GB RAM | 512 MB RAM | Depends on hardware and plan |
| Storage | Platform resource limits apply | Ephemeral filesystem | Default disk is non-persistent |
| Sleeping | After 12 hours without traffic | After 15 minutes idle | Depends on Space configuration |
| Paid option | Paid plans available | Paid plans from approximately $7/month | Paid compute available |
| Git integration | Direct GitHub deployment | Git-based deployment | Git repository-based deployment |
| Streamlit support | Native | Python web service | Requires suitable configuration |

*Limits and prices are indicative and may change.*

## 2. Selected platform

Streamlit Community Cloud is selected because:

- PulseIQ is already developed using Streamlit.
- It supports direct deployment from GitHub.
- It requires minimal hosting configuration.
- The 19 curated Parquet datasets occupy approximately 61 KB.
- No separate database server is required for the public demonstration.

## 3. Deployment configuration

| Setting | Value |
|---|---|
| Repository | PulseIQ GitHub repository |
| Branch | main |
| Main file | app.py |
| Dependencies | 05_Starter/requirements.txt |
| Hosted data | data/hosted/ |
| Data format | Parquet |
| Hosted mode | Automatic when local DuckDB is unavailable |

## 4. Platform limitations

- Community Cloud apps can sleep after 12 hours without traffic.
- Resource limits may change.
- The application must be tested after deployment.
- Streamlit Community Cloud does not provide a built-in scheduled data refresh.

## 5. Official references

- Streamlit: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- Render: https://render.com/docs/free
- Render pricing: https://render.com/pricing
- Hugging Face Spaces: https://huggingface.co/docs/hub/spaces-overview
- Hugging Face pricing: https://huggingface.co/pricing
