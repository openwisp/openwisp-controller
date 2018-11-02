from django.db import migrations 

from django.models import Permission 





def assignPerm(apps, schema_editor): 
    Group= apps.get_model('openwisp_user', 'Group')
    admin = Group.objects.get(name="Administrator")
    operator= Group.objects.get(name="Operator")
    operators_and_admins_can_change=["device", "config", "template", "location", "floorplan",]
    operators_read_only_admins_manage=["vpn", "ca", "certificate",]
    manage_operations=["add", "change", "delete"]

    for i in operators_and_admins_can_change:
        for j in manage_operations:
            admin.permissions.add(Permission.objects.get(codename="{}_{}".format(j,i)), bulk=True)
            operator.permissions.add(Permission.objects.get(codename="{}_{}".format(j,i)), bulk=True)
    for i in operators_read_only_admins_manage:

        try:
            permission=Permission.objects.get(codename="view_{}".format(i))
            operator.permissions.add(permission, bulk=True)
        except Permission.DoesNotExist:
            pass   
        

        for j in manage_operations:
            admin.permissions.add(Permission.objects.get(codename="{}_{}".format(j,i)), bulk=True)


    

class PermMigration(migrations.Migration): 
    dependencies=[
        ('openwisp_user', '0004_default_groups'),
        ('config', '0010_auto_20180106_1814'),
    ]

    operations=[
        migrations.RunPython(assignPerm),
    ]



