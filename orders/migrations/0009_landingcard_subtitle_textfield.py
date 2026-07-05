from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_landing_cards'),
    ]

    operations = [
        migrations.AlterField(
            model_name='landingcard',
            name='subtitle',
            field=models.TextField(blank=True, default=''),
        ),
    ]
