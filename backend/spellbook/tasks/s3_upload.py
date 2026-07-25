import os
import logging

BUCKET = os.environ.get('AWS_S3_BUCKET', None)


def can_upload_to_s3() -> bool:
    try:
        import boto3
        try:
            boto3.client('s3')
        except Exception:
            return False
    except ImportError:
        return False
    return BUCKET is not None


def _put_object(body: bytes, s3_file_name: str, **extra_args) -> None:
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError
    except ImportError:
        logging.exception('Could not import boto3', stack_info=True)
        raise
    try:
        s3 = boto3.client('s3')
        s3.put_object(
            Body=body,
            Bucket=BUCKET,
            Key=s3_file_name,
            ACL='public-read',
            ContentType='application/json',
            **extra_args,
        )
    except NoCredentialsError:
        logging.exception('Credentials not available', stack_info=True)
        raise
    except Exception:
        logging.exception('Amazon S3 client raised an exception', stack_info=True)
        raise


def upload_json_to_aws(json_string: str, s3_file_name: str) -> None:
    '''Uploads an already encoded JSON document to the S3 bucket.'''
    _put_object(json_string.encode('utf-8'), s3_file_name)


def upload_gzipped_json_to_aws(gzipped_json: bytes, s3_file_name: str) -> None:
    '''Uploads an already encoded and compressed JSON document to the S3 bucket.'''
    _put_object(gzipped_json, s3_file_name, ContentEncoding='gzip')
