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
operate_branch="master"
jail_path="/zroot/iocage/jails/" # /mnt/vol1/iocage/jails
#ip4="172.16.145.135"

mkdir -p "$root_path"
cd "$root_path"
iocage_path_build $create_branch

rm -rf asigra_plugin
git clone --depth 1 https://github.com/miwi-fbsd/iocage-plugin-asigra.git "$root_path/asigra_plugin"

iocage fetch -P "$root_path/asigra_plugin/asigra.json" -n "$jail" vnet=1 dhcp=1

iocage stop "$jail"

jail_root="${jail_path}/${jail}/root"

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

echo "#!/bin/sh" > "$jail_root/usr/local/etc/rc.d/asigra_db_update"
echo '# $FreeBSD$' >> "$jail_root/usr/local/etc/rc.d/asigra_db_update"

cat >> "$jail_root/usr/local/etc/rc.d/asigra_db_update" <<EOL

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
EOL

echo 'run_rc_command "$1"' >> "$jail_root/usr/local/etc/rc.d/asigra_db_update"

chmod +x "$jail_root/usr/local/etc/rc.d/asigra_db_update"

iocage_path_build $operate_branch

iocage export -c lzma "$jail"

