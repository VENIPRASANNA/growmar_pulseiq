# Task 17 – PulseIQ Deployment Evidence

## 1. Hosting Platform
Streamlit Community Cloud

## 2. Public Dashboard URL
https://growmarpulseiq-d4fxemusmmdvuuww93pfqd.streamlit.app/

## 3. Deployment Details
- Source: GitHub
- Repository: VENIPRASANNA/growmar_pulseiq
- Branch: main
- Entry point: app.py
- Hosted datasets: 19 curated Parquet datasets

## 4. Functional Testing
- All 11 dashboard pages tested successfully.
- Hosted aggregate data loading verified.
- Privacy disclosures verified.
- Quarterly workforce movement calculations reconciled.

## 5. Mobile Responsiveness
Tested successfully on an iPhone.

## 6. Stranger Usability Test
An independent user successfully located the latest employee headcount without assistance.

## 7. Scheduled Data Refresh
- Monthly aggregate data refresh configured for 9:15 AM IST on the first day of each month.
- The scheduled script regenerates the curated hosted Parquet datasets locally.
- Updated datasets must be committed and pushed to GitHub to publish them to Streamlit Community Cloud.
- The refresh process is documented in `docs/hosted_refresh.md`.

## 8. Conclusion
PulseIQ was successfully deployed on Streamlit Community Cloud. The public dashboard was tested across all 11 pages, mobile usage, and independent user navigation.
