from django.db import migrations, models


def set_auto_accept_true(apps, schema_editor):
    Provider = apps.get_model('booket', 'Provider')
    Provider.objects.all().update(auto_accept=True)


class Migration(migrations.Migration):

    dependencies = [
        ('booket', '0029_provider_auto_accept'),
    ]

    operations = [
        migrations.AlterField(
            model_name='provider',
            name='auto_accept',
            field=models.BooleanField(
                default=True,
                help_text='Automatically accept appointments after OTP verification. Disable to require manual acceptance via dashboard.'
            ),
        ),
        migrations.RunPython(set_auto_accept_true, migrations.RunPython.noop),
    ]
