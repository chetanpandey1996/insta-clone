# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-23 09:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0003_remove_postmodel_interest'),
    ]

    operations = [
        migrations.AddField(
            model_name='postmodel',
            name='interest',
            field=models.CharField(default='others', max_length=50),
            preserve_default=False,
        ),
    ]