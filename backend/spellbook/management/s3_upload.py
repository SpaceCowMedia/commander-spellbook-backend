import os
import json
import gzip
import logging
import humps

ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID', None)
SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
BUCKET = os.environ.get('AWS_S3_BUCKET', None)


def can_upload_to_s3() -> bool:
    try:
        import boto3
        try:
            boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)
        except Exception:
            return False
    except ImportError:
        return False
    return ACCESS_KEY is not None and SECRET_KEY is not None and BUCKET is not None


def upload_json_to_aws(data, s3_file_name):
    data = humps.camelize(data)
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError
        s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)

        string_object = json.dumps(data)

        s3.put_object(
            Body=string_object,
            Bucket=BUCKET,
            Key=s3_file_name,
            ACL='public-read',
            ContentType='application/json'
        )

        gzip_object = gzip.compress(string_object.encode('utf-8'))

        s3.put_object(
            Body=gzip_object,
            Bucket=BUCKET,
            Key=s3_file_name + '.gz',
            ACL='public-read',
            ContentEncoding='gzip',
            ContentType='application/json'
        )
    except NoCredentialsError:
        logging.exception("Credentials not available", stack_info=True)
        raise
    except Exception:
        logging.exception("Amazon S3 client raised an exception", stack_info=True)
        raise
