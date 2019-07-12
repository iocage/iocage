#!/bin/sh

iocage_path_build()
{
	branch="$1"
	root_path="/root/asigra_image_build"
	rm -rf "$root_path/iocage"
	cd "$root_path"
	git clone --depth 1 https://github.com/iocage/iocage.git -b "$branch"
	cd iocage
	git checkout "$branch"
	rm -rf /usr/local/lib/python3.7/site-packages/iocage*
	python -m pip install -U .
}

root_path="/root/asigra_image_build"
jail="asigra_migration_image_9b5802df"
create_branch="asigra_migration"
operate_branch="NAS-102494"
ip4="192.168.0.25"

mkdir -p "$root_path"
cd "$root_path"
iocage_path_build $create_branch

echo '''
{
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
                "official": true,
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
            }
''' > "$root_path/asigra.json"

rm -rf iocage-plugin-asigra
git clone --depth 1 https://github.com/miwi-fbsd/iocage-plugin-asigra.git "$root_path/asigra_plugin"

iocage fetch -P "$root_path/asigra_plugin/asigra.json" -n "$jail" vnet=1 ip4_addr="$ip4"

iocage stop "$jail"

jail_root="/mnt/vol1/iocage/jails/${jail}/root"

rm -rf "$jail_root/usr/src"
rm -rf "$jail_root/usr/local/man"
rm -rf "$jail_root/usr/local/share/doc"
rm -rf "$jail_root/usr/local/share/icu"
rm -rf "$jail_root/usr/local/share/locale"
rm -rf "$jail_root/usr/lib32"
rm -rf "$jail_root/usr/share/games"
rm -rf "$jail_root/usr/share/doc"
rm -rf "$jail_root/usr/share/dict"
rm -rf "$jail_root/usr/share/examples"
rm -rf "$jail_root/usr/share/man"
rm -rf "$jail_root/usr/share/misc"
rm -rf "$jail_root/var/cache/pkg"
rm -rf "$jail_root/rescue"
rm -rf "$jail_root/var/db/freebsd-update"

mkdir "$jail_root/var/db/freebsd-update"
mkdir "$jail_root/var/cache/pkg"
mkdir "$jail_root/rescue"

echo '''
#!/bin/sh
# $FreeBSD$

# PROVIDE: asigra_db_update
# REQUIRE: postgresql
# BEFORE: dssystem

. /etc/rc.subr

update_db()
{
	/usr/local/bin/psql -U pgsql -d dssystem -c "UPDATE ds_config SET cfg_value = '/zdata/root/dump/' WHERE cfg_name ~ 'DBDumpPath';"
	/usr/local/bin/psql -U pgsql -d dssystem -c "UPDATE storage_locations SET path = '/zdata/root/' WHERE id=1;"
}

name='asigra_db_update'
start_cmd='update_db'
stop_cmd=':'

load_rc_config $name
run_rc_command "$1"
''' > "$jail_root/usr/local/etc/rc.d/asigra_db_update"

chmod +x "$jail_root/usr/local/etc/rc.d/asigra_db_update"

iocage_path_build $operate_branch

iocage export -c lzma "$jail"

