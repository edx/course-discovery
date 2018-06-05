# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-03-22 18:23
from __future__ import unicode_literals

import uuid

import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0079_enable_program_default_true'),
        ('journal', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalBundle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID')),
                ('title', models.CharField(help_text='The user-facing display title for this Journal Bundle', max_length=255, unique=True)),
                ('courses', models.ManyToManyField(blank=True, to='course_metadata.Course')),
            ],
            options={
                'abstract': False,
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
            },
        ),
        migrations.RemoveField(
            model_name='journal',
            name='key',
        ),
        migrations.AlterField(
            model_name='journal',
            name='title',
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='journalbundle',
            name='journals',
            field=models.ManyToManyField(blank=True, to='journal.Journal'),
        ),
    ]