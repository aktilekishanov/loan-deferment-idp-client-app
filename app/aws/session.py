import boto3

def get_s3_client(profile: str | None, region: str):
    if profile:
        session = boto3.session.Session(profile_name=profile, region_name=region or None)
        return session.client("s3")
    return boto3.client("s3", region_name=region or None)
