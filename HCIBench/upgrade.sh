#!/bin/bash

VERSION="2.8.3"
echo $VERSION > /etc/hcibench_version
currentversion=`grep Welcome /etc/issue | awk '{print $5}'`
sed "s/$currentversion/$VERSION/g" -i /etc/issue*

# FUNCTIONS
# *******************************
check_command()
{
  command=$1
  if ! [ -x "$(command -v $command)" ]; then
    echo -e "\e[31mCommand is missing: $command\e[0m"
    return 0
  else
    echo "Command is installed: $command"
    return 1
  fi
}

# REQUIRED COMMANDS
# *******************************
# Desc: Check to make sure we have the required commands
#       installed on the system.
CMD_GEM=gem
CMD_GIT=git
CMD_PYTHON=python3
CMD_PYTHON_PIP=pip3
CMD_TAR=tar

echo -e "\e[33mChecking required commands\e[0m"
if ( (check_command $CMD_GEM) ||
     (check_command $CMD_PYTHON) ||
     (check_command $CMD_PYTHON_PIP) ||
     (check_command $CMD_TAR) ); then
  exit 1
fi
echo "All required commands available"
echo ""

# VARIABLES
# *******************************
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PACKAGES="$DIR/misc_pkgs"
GIT_HCIB_BRANCH='master'
BUILD_VERSION='UNKNOWN'
BUILD_DATE=`date`
BUILD_INFO_FILE='/etc/hcibench-build.yml'
INSTALLATION_FOLDER='install'
FIOCONFIG_LOG='fioconfig.log'
FIOCONFIG_TMP="$INSTALLATION_FOLDER/fioconfig"
FIOCONFIG_SRC='src'
PYTHON_SITE_PACKAGES="$(dirname `$CMD_PYTHON -c 'import os as _; print(_.__file__)'`)/site-packages"
PERMISSION_FOLDERS=('/opt/automation' '/opt/automation/lib' '/opt/automation/lib/tests')
PERMISSION_FILES=('*.sh' '*.rb')
CLEANUP_FOLDERS=('/opt/automation' '/opt/output' '/opt/vmware/rvc/')
CLEANUP_FILES=('.git' '.gitignore' '.DS_Store')

# GIT BRANCH
# ***********************************************
# Desc: If git is installed check to see if we are deploying
#       the expected GA branch and prompt whether to continue
#       with the install if it is not.
#

#echo -e "\e[33mDetermining GIT Branch\e[0m"
#if !([ -x "$(command -v $CMD_GIT)" ]); then
#  echo 'Git not installed. Skipping.'
#else
#  echo 'Determining GIT Branch'
#  GIT_CUR_BRANCH=`$CMD_GIT branch | grep "\*" | cut -c3-`
#  echo -e "\e[32mGit Branch is: $GIT_CUR_BRANCH\e[0m"
#  if ([ "$GIT_CUR_BRANCH" != "$GIT_HCIB_BRANCH" ]); then
#    echo -e "\e[33mCurrent GIT branch does not match expected GA Branch:t config --global user.name "Your Name" $GIT_HCIB_BRANCH\e[0m"
#    echo 'Continue with the install?'
#    select yn in Yes No
#    do
#      case $yn in
#        Yes)
#          break
#          ;;
#        No)
#          echo 'Aborting'
#          exit
#          ;;
#      esac
#    done
#  fi
#fi

# SCM VERSION
# ***********************************************
# Desc: This section tries to obtain the current SCM version and
#       writes it to a file to better track what version is installed
#       on the system. There might be a wtive way to get the version
#       using the 'git' command although the python module might be
#       preferable since it provides a bit more intelligence and some
#       flexibility.
#
# It prints the values and stores them in a yaml file
#
# Ref. https://pypi.org/project/setuptools-scm/
#

#echo -e "\e[33mDetermining SCM version\e[0m"
#if !([ -x "$(command -v $CMD_PYTHON)" ] && [ -x "$(command -v $CMD_PYTHON_PIP)" ]); then
#   echo -e "\e[31mpython and/or pip are not installed: Cannot automatically determine the SCM version\e[0m"
#   echo -e "\e[31mSCM version is: $BUILD_VERSION\e[0m"
#else
#   echo 'Checking requirements'
#   $CMD_PYTHON_PIP install --no-cache-dir --upgrade pip
#   $CMD_PYTHON_PIP install --no-cache-dir --upgrade setuptools
#   $CMD_PYTHON_PIP install --no-cache-dir  setuptools_scm
#   BUILD_VERSION=`$CMD_PYTHON -c "from setuptools_scm import get_version;print(get_version(root='.', fallback_version='0.0'))"`
#   echo -e "\e[32mSCM version is: $BUILD_VERSION\e[0m"
#fi
#echo "Build information file: $BUILD_INFO_FILE"
#echo -e "build:\n  scm_version: '${BUILD_VERSION}'\n  date: '${BUILD_DATE}'" > $BUILD_INFO_FILE
#echo ""

#
# BACKUP
# ***********************************************
echo -e "\e[33mRemoving old files and backing up config files...\e[0m"

echo 'Removing gems'
for item in 'rvc' 'rbvmomi'
do
  $CMD_GEM uninstall $item -x
done
echo 'Backing up files'
for item in '/opt/automation/conf/perf-conf.yaml' '/opt/automation/vdbench-param-files/*' '/opt/automation/fio-param-files/*' '/opt/automation/conf/key.bin' '/opt/automation/tmp/*' '/opt/automation/logs/*'
do
  for file in $item
  do
    if [ -f $file ]; then
      FILE_NAME="$(basename $file)"
      PARENT_NAME="$(basename "$(dirname "$file")")"
      BACKUP_DIR="/tmp/$PARENT_NAME"
      mkdir -p $BACKUP_DIR && mv -f $item $BACKUP_DIR
      echo "Copied $file to $BACKUP_DIR"
    fi
  done
done
echo 'Removing files'
for item in '/opt/vmware/rvc' '/usr/bin/rvc' '/opt/automation' '/opt/output/vm-template'
do
  if [ -f $item ] || [ -d $item ]; then
    rm -rf $item
  fi
done
echo ""

#
# WORKER and TVM
# ***********************************************
cat $DIR/pkgs/vm-template/disk-0.vmdk.zip.parta* > $DIR/pkgs/vm-template/disk-0.vmdk.zip
unzip $DIR/pkgs/vm-template/disk-0.vmdk.zip -d $DIR/pkgs/vm-template/
rm -rf $DIR/pkgs/vm-template/*zip*
echo 'Copying new worker VM template'
mv -f $DIR/pkgs/vm-template /opt/output/
echo ""

#
# FIOCONFIG
# ***********************************************
echo -e "\e[33mInstalling fioconfig\e[0m"
echo "Removing previous version(s)"
rm -rf "/usr/bin/fioconfig*"
rm -f "/bin/fioconfigcli"
mkdir -p "$FIOCONFIG_TMP"
mv $DIR/pkgs/fioconfig-* $FIOCONFIG_TMP
pushd "$FIOCONFIG_TMP" &> /dev/null
  FIOCONFIG_LATEST=`basename fioconfig-*`
  mkdir $FIOCONFIG_SRC
  $CMD_TAR -xzf "$FIOCONFIG_LATEST" --strip 1 -C 'src'
  pushd $FIOCONFIG_SRC &> /dev/null
    $CMD_PYTHON setup.py install --record "../installed_files.txt" > "../$FIOCONFIG_LOG"
  popd &> /dev/null
  rm -rf $FIOCONFIG_SRC
  echo -e "\e[32mFioconfig installed\e[0m"
popd &> /dev/null
rm -rf "$INSTALLATION_FOLDER"
echo ""

#
# Appliance Utility
# ***********************************************
echo -e "\e[33mMoving Utility to ~/\e[0m"
mv -f $PACKAGES/vmFacilities/glue.rb ~/
chmod +x ~/glue.rb
mv -f $PACKAGES/vmFacilities/* ~/tmp/
chmod +x ~/tmp/*
echo "Install pip2"
wget https://bootstrap.pypa.io/pip/2.7/get-pip.py
python2.7 get-pip.py
echo "install nfs utils"
tdnf install nfs-utils rpcbind -y
systemctl start nfs-server rpcbind
systemctl enable nfs-server rpcbind
echo "install pip2 pkgs"
pip2 install six requests

#
# RVC
# ***********************************************
echo -e "\e[33mInstalling RVC\e[0m"
mv $DIR/rvc_rvc/rvc /usr/bin
chmod +x /usr/bin/rvc
echo ""

#
# TOMCAT
# ***********************************************
echo -e "\e[33mReplacing tomcat file...\e[0m"
echo 'Stopping Tomcat'
service tomcat stop
echo 'Removing old web app'
rm -rf /var/opt/apache-tomcat-*/webapps/VMtest*
echo 'Copying new web app'
mv "$PACKAGES/vmtest/VMtest.war" /var/opt/apache-tomcat-*/webapps
echo 'Starting Tomcat'
# Tomcat service needs to be started then restarted...
service tomcat start
sleep 5
service tomcat restart
echo ""

#
# RESTORE
# ***********************************************
echo -e "\e[33mCreating automation part and restoring config files...\e[0m"
mkdir -p /opt/vmware
mv $DIR/automation /opt
mv -f $DIR/misc_pkgs/graphites /opt/output/vm-template/
chmod 755 /opt/output/vm-template/graphites/*
for subdir in 'conf' 'vdbench-param-files' 'fio-param-files' 'tmp' 'logs'
do
  if [ -d /tmp/${subdir} ]; then
    mkdir -p /opt/automation/$subdir
    mv -f /tmp/${subdir}/* /opt/automation/$subdir/
  fi
done
echo ""

#
# GEMS
# ***********************************************
echo -e "\e[33mDeploying gems...\e[0m"
gem install ipaddress
unzip -q $DIR/rvc_rvc/gems.zip -d $DIR/rvc_rvc/ && mv $DIR/rvc_rvc /opt/vmware/rvc
echo ""

#
#  PERMISSIONS
# ***********************************************
echo -e "\e[33mSetting file permissions\e[0m"
for folder in "${PERMISSION_FOLDERS[@]}"
do
   if ! [ -d $folder ]; then
      echo -e "\e[31m[WARNING] Cannot set permission in non existant directory: $folder\e[0m"
   else
      echo "  Folder: $folder"
      for file in "${PERMISSION_FILES[@]}"
      do
         find $folder/* -maxdepth 0 -type f -name "$file" -exec echo "      Setting: " {} \; -exec chmod a+x {} \;
      done
   fi
done
echo ""

# CLEANUP
# ***********************************************
echo -e "\e[33mRemoving unecessary files\e[0m"
for folder in "${CLEANUP_FOLDERS[@]}"
do
   if ! [ -d $folder ]; then
      echo -e "\e[31mCannot cleanup non existant directory: $folder\e[0m"
   else
      echo "  Folder: $folder"
      for file in "${CLEANUP_FILES[@]}"
      do
         find $folder -type f -name $file -exec echo "      Deleting: " {} \; -exec rm -f {} \;
      done
   fi
done
echo "Removing git repository"
rm -rf "/opt/vmware/rvc/.git"
echo ""

# START SERVICES
# **********************************************
echo -e "\e[33mStarting services...\e[0m"

# UPDATE GOVC
# **********************************************
rm -rf /usr/local/bin/govc
mv $DIR/pkgs/govc /usr/local/bin
chmod +x /usr/local/bin/govc

# Update Container
# **********************************************
echo 'reseting containers'
sh ~/tmp/reset-containers

# UPDATE REPOS
# ***********************************************

rm -rf /etc/pki/rpm-gpg/VMWARE-RPM-GPG-KEY
mv $DIR/repo/VMWARE-RPM-GPG-KEY /etc/pki/rpm-gpg/

rm -rf /etc/yum.repos.d/*.repo
mv $DIR/repo/*.repo /etc/yum.repos.d/


rm -rf $DIR
#
# Done
# ***********************************************
echo -e "\e[32m[OK] Installation Successful\e[0m"
