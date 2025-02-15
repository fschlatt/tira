#!/bin/bash
#
#    Copyright 2014-today www.webis.de
#
#    Project TIRA
#    Author: Anna Beyer, Steve Göring, Martin Potthast
#

#
#    Load libaries and toolkits.
#
scriptPath=${0%/*}
. "$scriptPath"/core/bashhelper.sh
. "$scriptPath"/libs/shflags

#
#    Define and check needed tools for this script.
#
neededtools="VBoxManage"
debug && check_tools "$neededtools"  # If debug, check that tools are available.

#
#    Define usage screen.
#
usage() {
    echo "
Usage:
    $(basename "$0") <user> <password> <ip>

Description:
    Set user/admin passwords, remote ports and ssh.

Parameters:
    <user>
    <password>
    <ip>
    <adminpw>

Examples:
    $(basename "$0") my_vm (local)

Authors:
    Anna Beyer
    Steve Göring
    Martin Potthast"
    exit 1
}


#
#    Virtual machine configuration
#
main() {

    # Print usage screen if wrong parameter count.
    if [ "$#" -ne 4 ]; then
        logError "[tira-configure-vm-fedora] Missing arguments see:"
        usage
    fi

    # Get arguments.
    user="$1"
    pw="$2"
    ip="$3"
    pwtira="$4"

    usertira="$_CONFIG_tira_default_template_admin_username_fedora"
    pwtiradefault="$_CONFIG_tira_default_template_admin_password"

    # Create password hash.
    pwhash=$(perl -e 'print crypt($ARGV[0], "password")' "$pw")
    pwtirahash=$(perl -e 'print crypt($ARGV[0], "password")' "$pwtira")

    # Add user, change admin pw, change shell to /bin/bash.
    sshpass -p "$pwtiradefault" \
      ssh "$usertira@${ip}00" \
        -o ConnectTimeout=10 \
        -o ConnectionAttempts=100 \
        -o UserKnownHostsFile=/dev/null \
        -o StrictHostKeyChecking=no \
        -o LogLevel=error \
        -t \
        -t "echo $pwtiradefault | sudo -S useradd -m -g wheel -p $pwhash $user; \
            echo $pwtiradefault | sudo -S usermod -aG vboxsf $user; \
            echo $pwtiradefault | sudo -S usermod -s /bin/bash $user; \
            echo $usertira:$pwtirahash | sudo chpasswd -e; \
            exit"

}

#
#    Start programm with parameters.
#
main "$@"
