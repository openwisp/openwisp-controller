from django.db import migrations, models


def set_blank_emails_to_none(apps, schema_editor):
    User = apps.get_model("openwisp_users", "User")
    # if there is any user with blank email address
    # set its email address to None, otherwise the
    # unique constraint will be triggered by the empty string
    for user in User.objects.filter(email=""):
        user.email = None
        user.save()


class Migration(migrations.Migration):
    dependencies = [("openwisp_users", "0006_id_email_index_together")]

    operations = [
        # allow NULL
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                blank=True, max_length=254, null=True, verbose_name="email address"
            ),
        ),
        # data migration to change empty strings to NULL
        migrations.RunPython(
            set_blank_emails_to_none, reverse_code=migrations.RunPython.noop
        ),
        # add unique constraint
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True,
                unique=True,
                verbose_name="email address",
            ),
        ),
    ]
