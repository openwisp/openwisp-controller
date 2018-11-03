from django.db import migrations 
from django.contrib.auth.models import Permission 



def assignPerm(apps, schema_editor): 
    Group= apps.get_model('openwisp_users', 'Group')
    admin = Group.objects.get(name="Administrator")
    operator= Group.objects.get(name="Operator")
    operators_and_admins_can_change=["device", "config", "template", "location", "floorplan",]
    operators_read_only_admins_manage=["vpn", "ca", "certificate",]
    manage_operations=["add", "change", "delete"]

    for i in operators_and_admins_can_change:
        for j in manage_operations:
            permission=Permission.objects.get(codename="{}_{}".format(j,i))
            admin.permissions.add(permission)
            operator.permissions.add(permission) 
    for i in operators_read_only_admins_manage:
        try:
            permission=Permission.objects.get(codename="view_{}".format(i))
            operator.permissions.add(permission, )
        except Permission.DoesNotExist:
            pass   
        
        for j in manage_operations: 
            admin.permissions.add(Permissions.objects.get(codename="{}_{}".format(j,i)), )
    

class Migration(migrations.Migration): 
    dependencies=[
        ('openwisp_users', '__first__'),
        ('openwisp_users', '0004_default_groups'),
        ('pki', '__first__'),
        ('config', '0010_auto_20180106_1814'),
        
    ]

    operations=[
        migrations.RunPython(assignPerm),
    ]




