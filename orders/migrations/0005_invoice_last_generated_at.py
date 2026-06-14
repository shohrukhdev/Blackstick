from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_alter_client_latitude_alter_client_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='last_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
