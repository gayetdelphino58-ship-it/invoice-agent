"""
Infrastructure as Code — AWS CDK
Déploie toutes les ressources AWS pour Invoice Agent :
- DynamoDB table
- SNS Topic
- Lambda (scheduler quotidien)
- EventBridge rule (cron 8h00 UTC chaque matin)
- IAM roles & permissions
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    Duration,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class InvoiceAgentStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, email: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------ #
        # 1. DynamoDB — table des factures                                    #
        # ------------------------------------------------------------------ #
        table = dynamodb.Table(
            self, "InvoicesTable",
            table_name="invoices",
            partition_key=dynamodb.Attribute(
                name="invoice_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # ------------------------------------------------------------------ #
        # 2. SNS Topic — rappels par email                                    #
        # ------------------------------------------------------------------ #
        topic = sns.Topic(
            self, "ReminderTopic",
            topic_name="invoice-agent-reminders",
            display_name="Invoice Agent — Rappels de paiement",
        )

        if email:
            topic.add_subscription(subs.EmailSubscription(email))

        # ------------------------------------------------------------------ #
        # 3. IAM Role — Lambda peut accéder à DynamoDB, SNS, Bedrock          #
        # ------------------------------------------------------------------ #
        lambda_role = iam.Role(
            self, "SchedulerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        table.grant_read_write_data(lambda_role)
        topic.grant_publish(lambda_role)

        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "textract:DetectDocumentText",
            ],
            resources=["*"],
        ))

        # ------------------------------------------------------------------ #
        # 4. Lambda — scheduler de rappels                                    #
        # ------------------------------------------------------------------ #
        scheduler_fn = lambda_.Function(
            self, "SchedulerLambda",
            function_name="invoice-agent-scheduler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambda_handler.handler",
            code=lambda_.Code.from_asset("scheduler"),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "AWS_REGION_NAME": self.region,
                "DYNAMODB_TABLE_NAME": "invoices",
                "SNS_TOPIC_ARN": topic.topic_arn,
                "REMINDER_DAYS_BEFORE": "3",
            },
        )

        # ------------------------------------------------------------------ #
        # 5. EventBridge — cron chaque matin à 8h00 UTC                      #
        # ------------------------------------------------------------------ #
        rule = events.Rule(
            self, "DailyScheduler",
            rule_name="invoice-agent-daily-8h",
            description="Déclenche le scheduler Invoice Agent chaque matin à 8h00 UTC",
            schedule=events.Schedule.cron(
                minute="0",
                hour="8",
                month="*",
                week_day="MON-FRI",
                year="*",
            ),
        )
        rule.add_target(targets.LambdaFunction(scheduler_fn))

        # ------------------------------------------------------------------ #
        # 6. Outputs CloudFormation                                           #
        # ------------------------------------------------------------------ #
        CfnOutput(self, "TableName", value=table.table_name, description="DynamoDB Table")
        CfnOutput(self, "TopicArn", value=topic.topic_arn, description="SNS Topic ARN")
        CfnOutput(self, "LambdaArn", value=scheduler_fn.function_arn, description="Scheduler Lambda ARN")
        CfnOutput(self, "EventRuleArn", value=rule.rule_arn, description="EventBridge Rule ARN")


# ------------------------------------------------------------------ #
# App entry point                                                      #
# ------------------------------------------------------------------ #
app = cdk.App()

email = app.node.try_get_context("email") or ""

InvoiceAgentStack(
    app, "InvoiceAgentStack",
    email=email,
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
