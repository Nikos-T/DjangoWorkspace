# Generated by Django 3.2.3 on 2021-06-04 16:40

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('kmrecord', '0005_auto_20210604_1007'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record',
            name='date',
            field=models.DateTimeField(default=datetime.datetime(2021, 6, 4, 16, 40, 26, 578556, tzinfo=utc)),
        ),
    ]
