from django.db import migrations


def drop_historical_catalog_if_exists(apps, schema_editor):
    table_name = "catalogs_historicalcatalog"

    with schema_editor.connection.cursor() as cursor:
        existing_tables = set(
            schema_editor.connection.introspection.table_names(cursor)
        )

        if table_name in existing_tables:
            schema_editor.execute(
                "DROP TABLE {}".format(
                    schema_editor.quote_name(table_name)
                )
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("catalogs", "0005_auto_20200804_1401"),
    ]

    operations = [
        migrations.RunPython(
            drop_historical_catalog_if_exists,
            migrations.RunPython.noop,
        ),
    ]
