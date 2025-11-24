import boto3
import imaplib
import email
import json
import os
import uuid

# Get environment variables
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
SECRET_ARN = os.environ['SECRET_ARN']

# Initialize clients
s3 = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

def get_secrets():
    """Fetches credentials from AWS Secrets Manager."""
    response = secrets_client.get_secret_value(SecretId=SECRET_ARN)
    return json.loads(response['SecretString'])

def lambda_handler(event, context):
    try:
        secrets = get_secrets()
        gmail_user = secrets['GMAIL_USER']
        gmail_password = secrets['GMAIL_APP_PASSWORD']
        
        print(f"Connecting to Gmail as {gmail_user}...")
        
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(gmail_user, gmail_password)
        mail.select('inbox')
        
        # Search for all unseen emails
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != 'OK':
            print("No new messages found.")
            mail.logout()
            return {'statusCode': 200, 'body': 'No new messages.'}

        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} new email(s).")
        
        for e_id in email_ids:
            # Fetch the email by ID
            status, msg_data = mail.fetch(e_id, '(RFC822)')
            
            if status == 'OK':
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        raw_email = response_part[1]
                        
                        print(f"Successfully fetched email {e_id}. Upload logic pending.")


        mail.close()
        mail.logout()
        return {'statusCode': 200, 'body': f'Processed {len(email_ids)} emails.'}

    except imaplib.IMAP4.error as e:
        print(f"IMAP Error: {e}")
        return {'statusCode': 500, 'body': f'IMAP Error: {e}'}
    except Exception as e:
        print(f"General Error: {e}")
        return {'statusCode': 500, 'body': f'General Error: {e}'}
