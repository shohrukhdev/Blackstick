from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('booket', '0030_provider_auto_accept_default_true'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='comment_by_server',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='AppointmentFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='appointment_files/')),
                ('file_name', models.CharField(blank=True, max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('appointment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='files',
                    to='booket.appointment',
                )),
            ],
        ),
    ]
