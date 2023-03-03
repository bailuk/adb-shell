#!/bin/sh

# Installs desktop file

app="adb-shell"
app_id="${app}"
target="${HOME}/.local/share/applications/"
desktop="${target}/${app_id}.desktop"
data=$(pwd)

echo "create '${desktop}'"
mkdir -p "${target}"

cat > ${desktop} << EOF
[Desktop Entry]
Name=ADB Shell
Comment=Display connected Android devices with mount options (for android-fuse)
Exec=${data}/${app}.py
Terminal=false
Type=Application
Version=1.0
SingleMainWindow=true  
EOF

chmod 700 ${desktop} || exit 1
exit 0

