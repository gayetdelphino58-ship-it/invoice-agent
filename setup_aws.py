"""Script de setup : crée la table DynamoDB et le topic SNS nécessaires."""

import boto3
import sys
from config import AWS_REGION, DYNAMODB_TABLE_NAME, SNS_TOPIC_ARN


def create_dynamodb_table():
    """Crée la table DynamoDB 'invoices' si elle n'existe pas."""
    dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)

    existing = [t["TableName"] for t in dynamodb.list_tables()["TableNames"]]
    if DYNAMODB_TABLE_NAME in existing:
        print(f"✅ Table DynamoDB '{DYNAMODB_TABLE_NAME}' déjà existante.")
        return

    dynamodb.create_table(
        TableName=DYNAMODB_TABLE_NAME,
        KeySchema=[
            {"AttributeName": "invoice_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "invoice_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"✅ Table DynamoDB '{DYNAMODB_TABLE_NAME}' créée avec succès.")


def create_sns_topic():
    """Crée un topic SNS pour les rappels et affiche son ARN."""
    if SNS_TOPIC_ARN:
        print(f"✅ SNS Topic déjà configuré : {SNS_TOPIC_ARN}")
        return

    sns = boto3.client("sns", region_name=AWS_REGION)
    response = sns.create_topic(Name="invoice-agent-reminders")
    arn = response["TopicArn"]
    print(f"✅ Topic SNS créé : {arn}")
    print(f"   → Ajoutez cette ligne dans votre .env :")
    print(f"   SNS_TOPIC_ARN={arn}")
    print(f"   → Puis abonnez votre email : aws sns subscribe --topic-arn {arn} --protocol email --notification-endpoint votre@email.com")


if __name__ == "__main__":
    print("🔧 Setup Invoice Agent...")
    try:
        create_dynamodb_table()
        create_sns_topic()
        print("\n🎉 Setup terminé ! Vous pouvez lancer l'agent avec : python agent.py")
    except Exception as e:
        print(f"❌ Erreur lors du setup : {e}", file=sys.stderr)
        sys.exit(1)
