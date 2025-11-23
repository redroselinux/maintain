#!/bin/bash

sudo mv src/main.py /usr/bin/redrose-maintain
sudo mv src/coreutils.py /usr/bin/coreutils
sudo mv src/bash.py /usr/bin/build-bash
sudo mv src/curl.py /usr/bin/build-curl

read -r -p "Make desktop shortcuts for the commands? [y/N] " response
case "$response" in
    [yY][eE][sS]|[yY]) 
        echo "Creating desktop shortcuts..."

        DIR="$HOME/.local/share/applications"
        mkdir -p "$DIR"

        cat > "$DIR/Build Bash.desktop" <<EOF
[Desktop Entry]
Name=Build Bash
Exec=build-bash
Comment=
Terminal=true
PrefersNonDefaultGPU=false
Icon=terminal
Type=Application
EOF

        cat > "$DIR/Build Coreutils.desktop" <<EOF
[Desktop Entry]
Name=Build Coreutils
Exec=coreutils
Comment=
Terminal=true
PrefersNonDefaultGPU=false
Icon=terminal
Type=Application
EOF

        cat > "$DIR/Build Curl.desktop" <<EOF
[Desktop Entry]
Name=Build Curl
Exec=build-curl
Comment=
Terminal=true
PrefersNonDefaultGPU=false
Icon=terminal
Type=Application
EOF

        cat > "$DIR/Build Manager.desktop" <<EOF
[Desktop Entry]
Name=Build Manager
Exec=redrose-maintain
Comment=
Terminal=false
PrefersNonDefaultGPU=false
Icon=update-manager
Type=Application
EOF

        echo "Desktop shortcuts created in $DIR"
        ;;

    *)
        echo "Skipping desktop shortcut creation."
        ;;
esac
