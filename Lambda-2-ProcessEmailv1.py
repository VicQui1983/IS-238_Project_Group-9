import boto3
import email
import json
import os
import requests 
import urllib.parse
from email.policy import default
from bs4 import BeautifulSoup

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Get environment variables
DYNAMO_TABLE_NAME = os.environ['DYNAMO_TABLE_NAME']
SECRET_ARN = os.environ['SECRET_ARN']
table = dynamodb.Table(DYNAMO_TABLE_NAME)

def get_secrets():
    """Fetches credentials from AWS Secrets Manager."""
    response = secrets_client.get_secret_value(SecretId=SECRET_ARN)
    return json.loads(response['SecretString'])

def parse_email_address(raw_address):
    """Extracts just the email from a 'Name <email@domain.com>' string."""
    if '<' in raw_address and '>' in raw_address:
        return raw_address.split('<')[1].split('>')[0]
    return raw_address.strip()

def parse_email_body(msg):
    """Parses HTML and plain text, prioritizing HTML."""
    html_body = None
    plain_body = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/html':
                html_body = part.get_payload(decode=True)
            elif ctype == 'text/plain':
                plain_body = part.get_payload(decode=True)
    else:
        ctype = msg.get_content_type()
        if ctype == 'text/html':
            html_body = msg.get_payload(decode=True)
        elif ctype == 'text/plain':
            plain_body = msg.get_payload(decode=True)

    if html_body:
        try:
            charset = msg.get_content_charset() or 'utf-8'
            soup = BeautifulSoup(html_body.decode(charset, errors='replace'), 'html.parser')
            
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            return ' '.join(text.split())
        except Exception as e:
            print(f"HTML parsing error: {e}")
            if plain_body:
                charset = msg.get_content_charset() or 'utf-8'
                return plain_body.decode(charset, errors='replace')
            return "Could not parse email body."
    elif plain_body:
        charset = msg.get_content_charset() or 'utf-8'
        return plain_body.decode(charset, errors='replace')
    
    return "No text content found in email."


def get_summary(subject, body, api_key):
    """Calls the OpenAI API for summarization."""
    print("TODO: Calling AI API...")
    return "This is a placeholder summary. The real AI call is pending."


def send_telegram_message(chat_id, text, reply_markup, bot_token):
    """Sends a formatted message to a Telegram user."""
    print(f"TODO: Sending message to chat_id {chat_id}")
    pass


def lambda_handler(event, context):
    try:
        s3_event = event['Records'][0]['s3']
        bucket_name = s3_event['bucket']['name']
        object_key = urllib.parse.unquote_plus(s3_event['object']['key'])
        
        raw_email_obj = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        raw_email_content = raw_email_obj['Body'].read()
        
        msg = email.message_from_bytes(raw_email_content, policy=default)
        
        to_address_raw = msg.get('To', '')
        to_address = parse_email_address(to_address_raw)
        
        subject, encoding = email.header.decode_header(msg.get('Subject', 'No Subject'))[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or 'utf-8', errors='replace')

        print(f"Processing email for: {to_address}")
        
        response = table.get_item(Key={'email': to_address})
        if 'Item' not in response:
            print(f"No user found for email address: {to_address}. Ignoring.")
            return {'statusCode': 404, 'body': 'User not found.'}
            
        chat_id = int(response['Item']['chat_id'])
        
        body_text = parse_email_body(msg)
        
        secrets = get_secrets()
        bot_token = secrets['TELEGRAM_BOT_TOKEN']
        openai_key = secrets['OPENAI_API_KEY']
        
        summary = get_summary(subject, body_text, openai_key)
        
        print("TODO: Add S3 pre-signed URL generation.")
        message_text = f"Placeholder message for {to_address}: {summary}"
        keyboard = {}
        
        send_telegram_message(chat_id, message_text, keyboard, bot_token)
        
        return {'statusCode': 200, 'body': 'Email processed and sent.'}

    except Exception as e:
        print(f"Unhandled error in processor: {e}")
        import traceback
        traceback.print_exc()
        return {'statusCode': 500, 'body': f'Error: {e}'}