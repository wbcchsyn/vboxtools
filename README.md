# VBosTools

VBoxTools is command line tools compatible with Vagrant.

## Requirements ##

* Python 2.7 or Python 3.x
* Virtual Box

## Tested ##

* Mac OX 10.9

## Commands ##

Every command supports -h or --help option.  

Use eather its name or its UUID to specify VM and snapshot.

### vls ###
List VMs registered in VirtualBox.

Usage:  
vls [-l] [-r] [name1 [name2 [name3 ...]]]

Options:  
-l --long  
List in long format.

-r --running  
List only VMs running

### vup ###
Check ssh port forward is available and start VM(s).

If ssh port forward is not set or the port is using, create a new port forward
rule named 'ssh'.  
Each VM must have at least one nic attached NAT.

Usage:  
vup [-g] VM1 [VM2 [VM3 ...]]

Option:  
-g --gui  
Enable GUI

### vdown ###
Send ACPI signal to VM(s) and shutdown.

Usage:  
vdown [-f] VM1 [VM2 [VM3 ...]]

Option:  
-f --force  
Not send acpi signal but force poweroff.

### vclone ###
Clone existing VM and create a new one.

Usage:  
vclone [-f] VM[:Snapshot] destination

If snapshot is not specified, use current one.

Option:  
-f --full  
Do not use link clone but do copy all VM image.

### vrm ###
Unregister VM(s) and delete all files.

Usage:  
vrm VM1 [VM2 [VM3 ...]]

### vslist ###
Show snapshots of VM.

Usage:  
vslist [-l] VM

Option:  
-l --long  
Show UUID and tree structure as well as snapshot name.

### vstake ###
Take a new snapshot.

Usage:  
vstake VM snapshot_name

### vsrestore ###
Restore VM to snapshot.

Usage:  
vsrestore VM [snapshot]

If snapshot is not specified, restore to current one.

### vsremove ###
Remove snapshot

Usage:  
vsremove VM snapshot


### vssh ###
ssh to guest.

Usage:  
vssh [user_name@]VM [ssh options] [command]

All ssh options and command are passed to ssh command.
