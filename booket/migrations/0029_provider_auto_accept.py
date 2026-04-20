from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booket', '0028_server_title_uz'),
    ]

    operations = [
        migrations.AddField(
            model_name='provider',
            name='auto_accept',
            field=models.BooleanField(default=False, help_text='Automatically accept appointments after OTP verification'),
        ),
    ]
