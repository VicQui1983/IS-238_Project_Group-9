import boto3
import json
import os
import requests
import uuid

DYNAMO_TABLE_NAME = os.environ['DYNAMO_TABLE_NAME']
SECRET_ARN = os.environ['SECRET_ARN']
DOMAIN = os.environ['DOMAIN']

dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
table = dynamodb.Table(DYNAMO_TABLE_NAME)

CACHED_SECRETS = None

def get_secrets():
    """Fetches credentials from AWS Secrets Manager, caching them."""
    global CACHED_SECRETS
    if CACHED_SECRETS:
        return CACHED_SECRETS
    
    response = secrets_client.get_secret_value(SecretId=SECRET_ARN)
    CACHED_SECRETS = json.loads(response['SecretString'])
    return CACHED_SECRETS

def send_telegram_message(chat_id, text, bot_token):
    """Sends a simple text message to Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    requests.post(url, json=payload)

def answer_callback_query(callback_query_id, text, bot_token):
    """Answers a callback query (shows a toast notification)."""
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload = {'callback_query_id': callback_query_id, 'text': text}
    requests.post(url, json=payload)

def edit_message_reply_markup(chat_id, message_id, bot_token):
    """Removes the inline keyboard from a message after an action."""
    url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
    payload = {'chat_id': chat_id, 'message_id': message_id, 'reply_markup': {}}
    requests.post(url, json=payload)


def handle_message(message, secrets):
    """Handles new messages sent to the bot."""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    bot_token = secrets['TELEGRAM_BOT_TOKEN']
    
    if text == '/start' or text == '/new_email':
        send_telegram_message(chat_id, "Generating your new email address, please wait...", bot_token)
        
        new_email = f"{uuid.uuid4().hex[:12]}@{DOMAIN}"
        
        try:
            table.put_item(
                Item={
                    'email': new_email,
                    'chat_id': str(chat_id)
                }
            )
        except Exception as e:
            print(f"DynamoDB Put Error: {e}")
            send_telegram_message(chat_id, "Sorry, a database error occurred. Please try again.", bot_token)
            return
            
        response_text = (
            f"✅ Your new email address is ready!\n\n"
            f"`{new_email}`\n\n"
            f"You can now set up forwarding from your other accounts to this address."
        )
        send_telegram_message(chat_id, response_text, bot_token)
        
    else:
        send_telegram_message(chat_id, "Hi! Use /new_email to generate a new email address.", bot_token)

def handle_callback(callback_query, secrets):
    """Handles button-press callbacks."""
    data = callback_query['data']
    callback_id = callback_query['id']
    message = callback_query['message']
    chat_id = message['chat']['id']
    message_id = message['message_id']
    bot_token = secrets['TELEGRAM_BOT_TOKEN']
    
    if data.startswith('deactivate:'):
        email_to_deactivate = data.split(':', 1)[1]
        
        try:
            table.delete_item(Key={'email': email_to_deactivate})
        except Exception as e:
            print(f"DynamoDB Delete Error: {e}")
            answer_callback_query(callback_id, "Error cleaning database.", bot_token)
            return
            
        answer_callback_query(callback_id, f"Deactivated {email_to_deactivate}", bot_token)
        edit_message_reply_markup(chat_id, message_id, bot_token)


def lambda_handler(event, context):
    try:
        secrets = get_secrets()
        body = json.loads(event.get('body', '{}'))
        
        if 'callback_query' in body:
            print("Handling callback query...")
            handle_callback(body['callback_query'], secrets)
        elif 'message' in body:
            print("Handling new message...")
            handle_message(body['message'], secrets)
        else:
            print("Unknown event type or empty body.")
            
        return {'statusCode': 200, 'body': json.dumps('OK')}
        
    except Exception as e:
        print(f"Unhandled error in webhook: {e}")
        import traceback
        traceback.print_exc()
        return {'statusCode': 200, 'body': json.dumps('Error')}