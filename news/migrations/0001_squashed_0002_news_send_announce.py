# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-11-17 20:55
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='News',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('postdate', models.DateTimeField(db_index=True, verbose_name='post date')),
                ('last_modified', models.DateTimeField(db_index=True, editable=False)),
                ('title', models.CharField(max_length=255)),
                ('guid', models.CharField(editable=False, max_length=255)),
                ('content', models.TextField()),
                ('safe_mode', models.BooleanField(default=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='news_author', to=settings.AUTH_USER_MODEL)),
                ('send_announce', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('-postdate',),
                'db_table': 'news',
                'verbose_name_plural': 'news',
                'get_latest_by': 'postdate',
            },
        ),
    ]
