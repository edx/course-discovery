# Generated by Django 1.11.3 on 2017-12-07 19:07


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20171004_1133'),
        ('course_metadata', '0071_auto_20171128_1945'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseentitlement',
            name='partner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='core.Partner'),
        ),
    ]
