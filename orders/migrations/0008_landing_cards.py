import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_landing_slide'),
    ]

    operations = [
        migrations.DeleteModel(name='LandingSlide'),
        migrations.CreateModel(
            name='LandingCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120)),
                ('subtitle', models.CharField(blank=True, default='', max_length=255)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='orders.item',
                )),
                ('supplier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='landing_cards', to='orders.supplier',
                )),
            ],
            options={
                'verbose_name': 'Landing karta',
                'verbose_name_plural': 'Landing kartalar',
                'ordering': ['display_order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='LandingCardImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='landing_cards/%Y/%m/')),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('card', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images', to='orders.landingcard',
                )),
            ],
            options={
                'verbose_name': 'Landing karta rasm',
                'verbose_name_plural': 'Landing karta rasmlar',
                'ordering': ['display_order', 'created_at'],
            },
        ),
    ]
