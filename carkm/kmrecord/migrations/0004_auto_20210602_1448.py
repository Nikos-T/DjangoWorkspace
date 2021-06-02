# Generated by Django 3.2.3 on 2021-06-02 11:48

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('kmrecord', '0003_auto_20210602_0957'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fuelrecord',
            name='fuelType',
            field=models.SmallIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='record',
            name='date',
            field=models.DateTimeField(default=datetime.datetime(2021, 6, 2, 11, 48, 4, 779909, tzinfo=utc)),
        ),
    ]
