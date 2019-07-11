from middlewared.client import Client
from iocage_lib.iocage import IOCage
from iocage_lib.ioc_plugin import IOCPlugin


import json
import os
import uuid
import tempfile
import subprocess


def create_plugin():
    IOCage(silent=False).fetch(**{
        'accept': True,
        'name': '',
        'plugin_name': 'asigra',
        'props': ['vnet=1', 'ip4_addr="192.168.0.25"'],
    })


def install_iocage(branch='asigra_migration'):
    with tempfile.TemporaryDirectory() as td:
        IOCPlugin._clone_repo(branch, 'https://github.com/iocage/iocage.git', td)
        print(td)
        print(os.listdir(td))
        subprocess.Popen(['rm', '-r', '-f', '/usr/local/lib/python3.7/site-packages/iocage*']).communicate()
        os.chdir(td)
        #subprocess.Popen(['cd', td]).communicate()
        subprocess.Popen(['python', '-m', 'pip', 'install', '-U', '.']).communicate()
        #subprocess.Popen(['service', 'middlewared', 'restart']).communicate()
        os.chdir('/')


def install_plugin(jail_name=None):
    jail_name = jail_name or f'asigra_migration_image_{str(uuid.uuid4())[:4]}'
    asigra_path = '/root/asigra.json'
    with open(asigra_path, 'w') as f:
        f.write(
            json.dumps({
                "artifact": "https://github.com/miwi-fbsd/iocage-plugin-asigra.git",
                "fingerprints": {
                    "iocage-plugins": [
                        {
                            "fingerprint": "226efd3a126fb86e71d60a37353d17f57af816d1c7ecad0623c21f0bf73eb0c7",
                            "function": "sha256"
                        }
                    ]
                },
                "name": "asigra",
                "official": True,
                "packagesite": "http://pkg.cdn.trueos.org/iocage/unstable",
                "pkgs": [
                    "ca_root_nss",
                    "nss_ldap",
                    "pam_ldap",
                    "nginx",
                    "dsoperator",
                    "dssystem"
                ],
                "properties": {
                    "allow_raw_sockets": "1",
                    "allow_set_hostname": "1",
                    "allow_sysvipc": "1",
                    "mount_devfs": "1",
                    "mount_fdescfs": "1",
                    "mount_procfs": "1",
                    "sysvmsg": "new",
                    "sysvsem": "new",
                    "sysvshm": "new"
                },
                "release": "11.2-RELEASE"
            })
        )
    p = subprocess.Popen(
        ['iocage', 'fetch', '-P', asigra_path, '-n', jail_name, 'vnet=1',
         'ip4_addr=192.168.0.25'])
    p.communicate()




if __name__ == '__main__':
    #install_iocage()
    print('\n\nNEW IOCAGE INSTALLED')
    jail_name = f'asigra_migration_image_{str(uuid.uuid4())[:4]}'
    jail_name = f'asigra_migration_image_671c'
    #install_plugin(jail_name)

    subprocess.Popen(['iocage', 'stop', jail_name]).communicate()

    with Client() as cl:
        iocroot = cl.call('jail.get_iocroot')

    jail_root_dataset = os.path.join(iocroot, 'jails', jail_name, 'root')

    for path in (
        os.path.join(jail_root_dataset, 'usr/src'),
        os.path.join(jail_root_dataset, 'usr/local/man'),
        os.path.join(jail_root_dataset, 'usr/local/share/doc'),
        os.path.join(jail_root_dataset, 'usr/local/share/icu'),
        os.path.join(jail_root_dataset, 'usr/local/share/locale'),
        os.path.join(jail_root_dataset, 'usr/lib32'),
        os.path.join(jail_root_dataset, 'usr/share/games'),
        os.path.join(jail_root_dataset, 'usr/share/doc'),
        os.path.join(jail_root_dataset, 'usr/share/dict'),
        os.path.join(jail_root_dataset, 'usr/share/examples'),
        os.path.join(jail_root_dataset, 'usr/share/man'),
        os.path.join(jail_root_dataset, 'usr/share/misc'),
        os.path.join(jail_root_dataset, 'var/cache/pkg'),
        os.path.join(jail_root_dataset, 'rescue'),
    ):
        print('destroying ', path)
        subprocess.Popen(['rm', '-r', path]).communicate()

    with open(os.path.join(jail_root_dataset, 'usr/local/etc/rc.d/asigra_db_update'), 'w') as f:
        f.write(
            '''
#!/bin/sh
# $FreeBSD$

# PROVIDE: asigra_db_update
# REQUIRE: postgresql
# BEFORE: nginx

. /etc/rc.subr

update_db()
{
	psql -U pgsql -d dssystem -c "UPDATE ds_config SET cfg_value = '/zdata/root/dump/' WHERE cfg_name ~ 'DBDumpPath';"
	psql -U pgsql -d dssystem -c "UPDATE storage_locations SET path='/zdata/root/' WHERE id=1;"
}

name='asigra_db_update'
start_cmd='update_db'
stop_cmd=':'

load_rc_config $name
run_rc_command "$1"
            '''
        )

    os.chmod(os.path.join(jail_root_dataset, 'usr/local/etc/rc.d/asigra_db_update'), 0o755)

    #subprocess.Popen(['iocage', 'export', jail_name]).communicate()
    #with Client() as cl:
    #    cl.call('jail.export', jail_name, job=True)
