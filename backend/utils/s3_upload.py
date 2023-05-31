import boto3
from botocore.exceptions import NoCredentialsError
import os
import json
import gzip

ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID', None)
SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
BUCKET = os.environ.get('AWS_S3_BUCKET', None)


def upload_dictionary_aws(data, s3_file_name):
    try:
        s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)
    except Exception as e:
        print(e)
        return False

    try:
        s3.put_object(
            Body=json.dumps(data),
            Bucket=BUCKET,
            Key=s3_file_name,
            ACL='public-read',
            ContentType='application/json'
        )

        gzip_object = gzip.compress(json.dumps(data).encode('utf-8'))

        s3.put_object(
            Body=gzip_object,
            Bucket=BUCKET,
            Key=s3_file_name + '.gz',
            ACL='public-read',
            ContentEncoding='gzip',
            ContentType='application/json'
        )

        return True
    except NoCredentialsError:
        print("Credentials not available")
        return False
