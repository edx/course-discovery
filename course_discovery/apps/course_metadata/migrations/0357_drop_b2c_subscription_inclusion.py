from django.db import migrations


def drop_column_if_exists(apps, schema_editor):
    tables = [
        'course_metadata_course',
        'course_metadata_historicalcourse',
    ]
    for table in tables:
        with schema_editor.connection.cursor() as cursor:
            columns = schema_editor.connection.introspection.get_table_description(cursor, table)
        if any(col.name == 'b2c_subscription_inclusion' for col in columns):
            schema_editor.execute(f'ALTER TABLE {table} DROP COLUMN b2c_subscription_inclusion')


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('course_metadata', '0356_add_course_editor_update_bulk_operation'),
    ]

    operations = [
        migrations.RunPython(drop_column_if_exists, migrations.RunPython.noop),
    ]
