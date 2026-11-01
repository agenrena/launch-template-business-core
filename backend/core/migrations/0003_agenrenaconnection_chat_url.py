from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_defaults")]

    operations = [
        migrations.AddField(
            model_name="agenrenaconnection",
            name="chat_url",
            field=models.URLField(blank=True, max_length=2048),
        ),
    ]
