"""Add source reference fields to DocumentRecord and damage review fields to AnnotationRecord."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        # Document source reference fields
        migrations.AddField(
            model_name="documentrecord",
            name="source_bucket",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="documentrecord",
            name="source_key",
            field=models.CharField(max_length=500, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="documentrecord",
            name="source_parent_key",
            field=models.CharField(max_length=500, null=True, blank=True),
        ),
        # Annotation damage review fields
        migrations.AddField(
            model_name="annotationrecord",
            name="verification_status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("unverified", "unverified"),
                    ("human_verified", "human_verified"),
                    ("ai_suggested", "ai_suggested"),
                    ("rejected", "rejected"),
                ],
                default="unverified",
            ),
        ),
        migrations.AddField(
            model_name="annotationrecord",
            name="review_value",
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="annotationrecord",
            name="certainty",
            field=models.FloatField(null=True, blank=True),
        ),
    ]
