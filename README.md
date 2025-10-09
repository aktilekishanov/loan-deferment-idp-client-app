# RB Loan Deferment IDP

Streamlit app to upload a single document to Amazon S3.

## Project Structure
- `main.py` — Streamlit app entrypoint
- `requirements.txt` — Python dependencies
- `.streamlit/secrets.toml` — not committed; see template in `.streamlit/secrets.toml.template`

## Quickstart (Local)
1. Create and activate venv
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2. Set AWS credentials via environment or AWS CLI profile.
   - Environment (example):
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```
3. Run the app
```bash
streamlit run main.py
```

## Configuration
`main.py` exposes variables for:
- `AWS_REGION`
- `BUCKET_NAME`, `KEY_PREFIX`

You can keep `AWS_PROFILE` empty to use env vars/role.

## Deployment Options
- Streamlit Community Cloud (easiest): add your secrets and deploy from GitHub.
- AWS App Runner or ECS/EC2: containerize and attach IAM role for S3 access.

## Secrets
Copy `.streamlit/secrets.toml.template` to `.streamlit/secrets.toml` and fill in values (do not commit):
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- `BUCKET_NAME`, `KEY_PREFIX`
