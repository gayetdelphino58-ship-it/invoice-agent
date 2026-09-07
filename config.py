import os

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")

# DynamoDB
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "invoices")

# SNS
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")

# Reminder settings (days before due date)
REMINDER_DAYS_BEFORE = int(os.getenv("REMINDER_DAYS_BEFORE", "3"))

# Expense categories
EXPENSE_CATEGORIES = [
    "Electricité",
    "Eau",
    "Internet",
    "Téléphone",
    "Loyer",
    "Assurance",
    "Abonnement",
    "Courses",
    "Santé",
    "Transport",
    "Autre",
]
